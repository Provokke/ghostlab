from ghostlab.cache import cached


def test_computes_once_per_key(tmp_path):
    calls = []

    def compute():
        calls.append(1)
        return {"n": len(calls)}

    assert cached("sam", b"a", compute, tmp_path) == {"n": 1}
    assert cached("sam", b"a", compute, tmp_path) == {"n": 1}
    assert cached("sam", b"b", compute, tmp_path) == {"n": 2}
    assert len(list((tmp_path / "sam").glob("*.json"))) == 2


def test_kinds_do_not_collide(tmp_path):
    assert cached("a", b"k", lambda: {"v": "a"}, tmp_path) == {"v": "a"}
    assert cached("b", b"k", lambda: {"v": "b"}, tmp_path) == {"v": "b"}
