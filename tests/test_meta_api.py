import base64

from ghostlab import meta_api
from tests.fakes import FakeMeta


def test_sam_track_sends_prompt_and_video(tmp_path):
    fake = FakeMeta(sam_text="<0f>0<|box;x1=1;y1=2;x2=3;y2=4;w=10;h=10|>")
    clip = tmp_path / "clip.mp4"
    clip.write_bytes(b"video")
    file_id = meta_api.upload_video(fake, clip)
    text = meta_api.sam_track(fake, file_id, "tennis ball")
    assert text.startswith("<0f>")
    content = fake.calls[1][1][0]["content"]
    assert content[0] == {"type": "input_text", "text": "tennis ball"}
    assert content[1] == {"type": "input_video", "file_id": file_id}


def test_spark_json_sends_images_and_schema():
    fake = FakeMeta(chat_replies=[{"object": "ball"}])
    schema = {"type": "object", "properties": {"object": {"type": "string"}},
              "required": ["object"], "additionalProperties": False}
    reply = meta_api.spark_json(fake, "what is it?", [b"img1", b"img2"], "probe", schema)
    assert reply == {"object": "ball"}
    _, messages, fmt = fake.calls[0]
    parts = messages[0]["content"]
    assert parts[0] == {"type": "text", "text": "what is it?"}
    assert parts[2]["image_url"]["url"] == "data:image/jpeg;base64," + base64.b64encode(b"img2").decode()
    assert fmt["json_schema"]["name"] == "probe" and fmt["json_schema"]["schema"] == schema
