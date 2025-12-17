import pytest

from stellwerk.planner import _extract_json_object


def test_extract_json_object_plain():
    obj = _extract_json_object('{"a": 1, "b": {"c": 2}}')
    assert obj["a"] == 1
    assert obj["b"]["c"] == 2


def test_extract_json_object_fenced():
    obj = _extract_json_object("""```json
{"x": true}
```""")
    assert obj["x"] is True


def test_extract_json_object_with_extra_text():
    obj = _extract_json_object("Here you go:\n{\n  \"k\": \"v\"\n}\nThanks!")
    assert obj["k"] == "v"


def test_extract_json_object_raises_when_missing():
    with pytest.raises(ValueError):
        _extract_json_object("no json here")
