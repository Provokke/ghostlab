import pytest
from pathlib import Path

import numpy as np

from ghostlab.sam_parse import parse, pick_object, to_pixel_track

DOC_EXAMPLE = ("<0f>0<|box;x1=211;y1=228;x2=270;y2=254;w=320;h=334|><|mask;x=0;y=0;data=27,60,~!!<3f>!M|>,"
               "1<|box;x1=10;y1=10;x2=20;y2=20;w=320;h=334;c=0.4|>\n"
               "<1f>0<|box;x1=221;y1=238;x2=280;y2=264;w=320;h=334|>\n"
               "<3f>0<|box;x1=241;y1=258;x2=300;y2=284;w=320;h=334|>\n")


def test_parse_doc_example():
    frames = parse(DOC_EXAMPLE)
    assert sorted(frames) == [0, 1, 3]  # the "<3f>" inside the mask is not a frame
    assert frames[0][0].x1 == 211 and frames[0][1].conf == 0.4
    assert frames[1][0].conf is None


def test_pick_object_prefers_most_frames():
    assert pick_object(parse(DOC_EXAMPLE)) == 0
    assert pick_object({}) is None


def test_pixel_track_marks_missing_frames():
    track = to_pixel_track(parse(DOC_EXAMPLE), n_frames=4, fps=2.0, frame_w=320, frame_h=334)
    assert track.cx[0] == 240.5 and track.cy[0] == 241.0 and track.w[0] == 59
    assert np.isnan(track.cx[2])
    assert track.t[3] == 1.5


@pytest.mark.skipif(not Path("tests/fixtures/sam_real.txt").exists(), reason="live-only: needs a real SAM output fixture at tests/fixtures/sam_real.txt")
def test_real_fixture():
    text = Path("tests/fixtures/sam_real.txt").read_text(encoding="utf-8")
    frames = parse(text)
    assert len(frames) >= 10
    oid = pick_object(frames)
    assert oid is not None
    hits = sum(oid in objs for objs in frames.values())
    assert hits >= 0.8 * len(frames)


def test_malformed_boxes_are_skipped_not_fatal():
    text = ("<0f>0<|box;x1=1;y1=2;x2=3|>,1<|box;x1=a;y1=2;x2=3;y2=4|>,2<|box;x1=1;y1=2;x2=nan;y2=4|>,"
            "3<|box;x1=5;y1=5;x2=9;y2=9;c=0.9|>\n<1f>3<|box;x1=6;y1=6;x2=10;y2=10|>\n")
    frames = parse(text)
    assert list(frames[0]) == [3] and frames[0][3].conf == 0.9
    assert list(frames[1]) == [3]


def test_all_boxes_bad_keeps_the_frame_empty():
    assert parse("<0f>0<|box;x1=1|>\n") == {0: {}}


def test_inverted_box_is_skipped():
    assert parse("<0f>0<|box;x1=9;y1=9;x2=1;y2=1|>") == {0: {}}
