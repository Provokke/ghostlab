"""Thin wrappers over the Meta Model API (OpenAI-compatible)."""
from __future__ import annotations

import base64
import json
import os
from pathlib import Path

import httpx
from openai import OpenAI

BASE_URL = "https://api.meta.ai/v1"
SPARK = "muse-spark-1.3"
SAM = "sam-3.1"


LONG_TIMEOUT = 300.0  # video upload and SAM tracking legitimately take a while


class MissingKeyError(RuntimeError):
    """MODEL_API_KEY is not set."""


def client() -> OpenAI:
    """Meta API client. No silent retries (a retry would re-upload a video); a stalled call fails after 120 s."""
    key = os.environ.get("MODEL_API_KEY")
    if not key:
        raise MissingKeyError("Set MODEL_API_KEY (see README).")
    return OpenAI(api_key=key, base_url=BASE_URL, timeout=httpx.Timeout(120, connect=10), max_retries=0)


def _slow(c):
    """Client with the long timeout; test doubles without with_options pass through."""
    with_options = getattr(c, "with_options", None)
    return with_options(timeout=LONG_TIMEOUT) if with_options else c


def upload_video(c, path: Path) -> str:
    with open(path, "rb") as f:
        return _slow(c).files.create(file=f, purpose="user_data").id


def sam_track(c, file_id: str, prompt: str) -> str:
    content = [{"type": "input_text", "text": prompt}, {"type": "input_video", "file_id": file_id}]
    response = _slow(c).responses.create(model=SAM, input=[{"type": "message", "role": "user", "content": content}])
    return response.output_text


def spark_json(c, prompt: str, images: list[bytes], name: str, schema: dict) -> dict:
    parts = [{"type": "text", "text": prompt}]
    for img in images:
        url = "data:image/jpeg;base64," + base64.b64encode(img).decode()
        parts.append({"type": "image_url", "image_url": {"url": url}})
    response = c.chat.completions.create(
        model=SPARK,
        messages=[{"role": "user", "content": parts}],
        response_format={"type": "json_schema", "json_schema": {"name": name, "schema": schema, "strict": True}},
    )
    return json.loads(response.choices[0].message.content)
