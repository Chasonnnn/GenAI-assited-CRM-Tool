import json

import pytest
from google.protobuf import json_format, struct_pb2

from app.core.protobuf_guard import DEFAULT_MAX_RECURSION_DEPTH, apply_protobuf_json_depth_guard


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


def test_parse_json_preserves_positional_parser_arguments():
    apply_protobuf_json_depth_guard()

    message = struct_pb2.Struct()
    json_format.Parse('{"status": "ok"}', message)

    assert message["status"] == "ok"


@pytest.mark.parametrize("positional", [False, True])
def test_parse_dict_honors_a_lower_caller_depth_limit(positional):
    apply_protobuf_json_depth_guard()
    payload = _nested_dict(5)

    with pytest.raises(json_format.ParseError, match="maximum recursion depth"):
        if positional:
            json_format.ParseDict(payload, struct_pb2.Struct(), False, None, 3)
        else:
            json_format.ParseDict(payload, struct_pb2.Struct(), max_recursion_depth=3)


def test_parse_json_cannot_raise_the_application_depth_limit():
    apply_protobuf_json_depth_guard()
    payload = json.dumps(_nested_dict(DEFAULT_MAX_RECURSION_DEPTH + 1))

    with pytest.raises(json_format.ParseError, match="maximum recursion depth"):
        json_format.Parse(
            payload, struct_pb2.Struct(), max_recursion_depth=DEFAULT_MAX_RECURSION_DEPTH + 10
        )
