"""Shared type aliases for JSON-like payloads."""

from __future__ import annotations

from typing import TypeAlias

JsonValue: TypeAlias = object
JsonObject: TypeAlias = dict[str, JsonValue]
JsonArray: TypeAlias = list[JsonValue]
