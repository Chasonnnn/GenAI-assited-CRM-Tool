"""Runtime guard for protobuf JSON parsing depth."""

from typing import Any


DEFAULT_MAX_RECURSION_DEPTH = 100


def _exceeds_depth(value: Any, limit: int) -> bool:
    stack: list[tuple[Any, int]] = [(value, 1)]
    while stack:
        current, depth = stack.pop()
        if depth > limit:
            return True
        if isinstance(current, dict):
            stack.extend((child, depth + 1) for child in current.values())
        elif isinstance(current, list):
            stack.extend((child, depth + 1) for child in current)
    return False


def apply_protobuf_json_depth_guard() -> None:
    try:
        from google.protobuf import json_format
    except Exception:
        return

    if getattr(json_format, "_sf_depth_guard_applied", False):
        return

    max_depth = getattr(json_format, "_MAX_RECURSION_DEPTH", DEFAULT_MAX_RECURSION_DEPTH)
    original_parse_dict = json_format.ParseDict

    def guarded_parse_dict(
        js_dict: Any,
        message: Any,
        ignore_unknown_fields: bool = False,
        descriptor_pool: Any | None = None,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        if _exceeds_depth(js_dict, max_depth):
            raise json_format.ParseError("Protobuf JSON exceeds maximum recursion depth")
        try:
            return original_parse_dict(
                js_dict,
                message,
                ignore_unknown_fields=ignore_unknown_fields,
                descriptor_pool=descriptor_pool,
                *args,
                **kwargs,
            )
        except TypeError:
            return original_parse_dict(
                js_dict,
                message,
                ignore_unknown_fields=ignore_unknown_fields,
                *args,
                **kwargs,
            )

    json_format.ParseDict = guarded_parse_dict
    json_format._sf_depth_guard_applied = True
