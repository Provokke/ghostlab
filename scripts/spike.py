"""Day-1 probe: one SAM 3.1 video call and one Muse Spark image call; saves the raw SAM output."""
import json
import re
import sys
import time
from pathlib import Path

import cv2

from ghostlab import meta_api

SCHEMA = {"type": "object", "properties": {"object": {"type": "string"}, "size_m": {"type": "number"}},
          "required": ["object", "size_m"], "additionalProperties": False}


def main(clip: Path, prompt: str) -> None:
    c = meta_api.client()
    cap = cv2.VideoCapture(str(clip))
    fps, n = cap.get(cv2.CAP_PROP_FPS), int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    _, frame = cap.read()
    cap.release()
    t0 = time.time()
    file_id = meta_api.upload_video(c, clip)
    t1 = time.time()
    text = meta_api.sam_track(c, file_id, prompt)
    t2 = time.time()
    out = Path("tests/fixtures/sam_real.txt")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    tags = [int(m) for m in re.findall(r"<(\d+)f>", text)]
    print(json.dumps({"fps": fps, "frames": n, "frame_tags": len(tags), "first_tags": tags[:5],
                      "upload_s": round(t1 - t0, 1), "sam_s": round(t2 - t1, 1), "chars": len(text)}, indent=2))
    jpg = cv2.imencode(".jpg", frame)[1].tobytes()
    t3 = time.time()
    reply = meta_api.spark_json(c, "Name the moving object and its real longest side in metres.", [jpg], "probe", SCHEMA)
    print(json.dumps({"spark": reply, "spark_s": round(time.time() - t3, 1)}, indent=2))


if __name__ == "__main__":
    main(Path(sys.argv[1]), sys.argv[2] if len(sys.argv) > 2 else "tennis ball")
