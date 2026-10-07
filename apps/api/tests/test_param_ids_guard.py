"""The collection guard rejects large parameters that became test ids."""

from types import SimpleNamespace

from tests.support.param_ids import oversized_param_ids


def _item(nodeid: str, params: dict, callspec_id: str) -> SimpleNamespace:
    return SimpleNamespace(nodeid=nodeid, callspec=SimpleNamespace(params=params, id=callspec_id))


def test_flags_large_bytes_param_with_auto_generated_id() -> None:
    payload = b"x" * 2048
    item = _item("tests/test_x.py::test_upload[" + "x" * 2048 + "]", {"body": payload}, "x" * 2048)
    assert oversized_param_ids([item]) == [item.nodeid[:200]]


def test_allows_large_param_with_explicit_id_and_plain_tests() -> None:
    explicit = _item("tests/test_x.py::test_upload[1mb]", {"body": b"x" * 2048}, "1mb")
    long_small = _item("tests/test_x.py::test_text[...]", {"text": "y" * 300}, "y" * 300)
    plain = SimpleNamespace(nodeid="tests/test_x.py::test_plain")
    assert oversized_param_ids([explicit, long_small, plain]) == []
