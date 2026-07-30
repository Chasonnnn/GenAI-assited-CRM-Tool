"""Shared type aliases for JSON-like payloads."""

from __future__ import annotations

type JsonValue = object
type JsonObject = dict[str, JsonValue]
type JsonArray = list[JsonValue]
