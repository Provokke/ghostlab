import cv2
import numpy as np

from ghostlab.ingest import SHAKE_LIMIT, prepare


def write_clip(path, shake_px=0, n=60, fps=30):
    rng = np.random.default_rng(0)
    background = rng.integers(0, 255, (760, 1280 + n * 2, 3), dtype=np.uint8)
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (1280, 720))
    for i in range(n):
        dx = i * shake_px
        frame = background[20:740, dx:dx + 1280].copy()
        cv2.circle(frame, (100 + 15 * i, 300), 25, (0, 255, 255), -1)
        writer.write(frame)
    writer.release()


def test_prepare_normalises_and_grabs_key_frames(tmp_path):
    src = tmp_path / "raw.mp4"
    write_clip(src)
    clip = prepare(src, tmp_path / "work")
    assert clip.path.exists() and clip.path.suffix == ".mp4"
    assert abs(clip.fps - 30) < 0.5
    assert 58 <= clip.n_frames <= 61
    assert clip.height == 720
    assert len(clip.key_frames) == 3 and all(f[:2] == b"\xff\xd8" for f in clip.key_frames)
    assert clip.camera_shift < SHAKE_LIMIT


def test_moving_background_reads_as_shaky(tmp_path):
    src = tmp_path / "shaky.mp4"
    write_clip(src, shake_px=1)  # frames 6 and 54 differ by 48 px, 3.75% of the width
    assert prepare(src, tmp_path / "work").camera_shift > SHAKE_LIMIT
