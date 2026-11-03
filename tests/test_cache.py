import pytest

from ghostlab.cache import cached, key_of


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


def test_corrupt_entry_is_a_miss_and_is_repaired(tmp_path):
    cached("sam", b"k", lambda: {"v": 1}, tmp_path)
    (entry,) = (tmp_path / "sam").glob("*.json")
    entry.write_text('{"a"', encoding="utf-8")
    assert cached("sam", b"k", lambda: {"v": 2}, tmp_path) == {"v": 2}
    assert cached("sam", b"k", lambda: {"v": 3}, tmp_path) == {"v": 2}


def test_no_temp_files_are_left_behind(tmp_path):
    cached("sam", b"k", lambda: {"v": 1}, tmp_path)
    assert [p.suffix for p in (tmp_path / "sam").iterdir()] == [".json"]


def test_failed_compute_stores_nothing(tmp_path):
    def boom():
        raise RuntimeError("api down")
    with pytest.raises(RuntimeError):
        cached("sam", b"k", boom, tmp_path)
    assert cached("sam", b"k", lambda: {"v": 1}, tmp_path) == {"v": 1}


def test_concurrent_callers_compute_once(tmp_path):
    import threading
    import time
    calls = []

    def slow():
        calls.append(1)
        time.sleep(0.1)
        return {"v": 1}

    threads = [threading.Thread(target=cached, args=("sam", b"k", slow, tmp_path)) for _ in range(4)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert len(calls) == 1


def test_key_of_cannot_be_confused_by_concatenation():
    assert key_of("ab", "c") != key_of("a", "bc")
    assert key_of("a", b"b") == key_of(b"a", "b")
