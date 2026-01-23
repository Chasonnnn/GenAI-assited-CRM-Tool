from google.protobuf import json_format, struct_pb2
import pytest

from app.core.protobuf_guard import apply_protobuf_json_depth_guard


def _nested_dict(depth: int) -> dict:
    root: dict = {}
    current = root
    for index in range(depth):
        child: dict = {}
        current[f"k{index}"] = child
        current = child
    return root


def test_parse_dict_rejects_excess_depth():
    apply_protobuf_json_depth_guard()
    limit = getattr(json_format, "_MAX_RECURSION_DEPTH", 100)
    payload = _nested_dict(limit + 1)
    message = struct_pb2.Struct()
    with pytest.raises(json_format.ParseError):
        json_format.ParseDict(payload, message)


def test_parse_dict_allows_within_depth():
    apply_protobuf_json_depth_guard()
    limit = getattr(json_format, "_MAX_RECURSION_DEPTH", 100)
    payload = _nested_dict(min(3, max(1, limit)))
    message = struct_pb2.Struct()
    json_format.ParseDict(payload, message)
    assert message.fields
