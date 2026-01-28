"""Helpers for parsing and validating AI JSON responses."""

from __future__ import annotations

import json
import logging
import re
from typing import TypeVar

from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)

ModelT = TypeVar("ModelT", bound=BaseModel)


def _strip_code_fences(text: str) -> str:
    content = text.strip()
    if content.startswith("```"):
        lines = content.splitlines()
        if lines:
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        content = "\n".join(lines).strip()
    return content


def parse_json_object(text: str) -> dict | None:
    content = _strip_code_fences(text)
    try:
        data = json.loads(content)
    except json.JSONDecodeError as exc:
        match = re.search(r"\{[\s\S]*\}", content)
        if not match:
            logger.warning(f"Failed to parse JSON object: {exc}")
            return None
        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError as inner_exc:
            logger.warning(f"Failed to parse JSON object: {inner_exc}")
            return None
    return data if isinstance(data, dict) else None


def parse_json_array(text: str) -> list | None:
    content = _strip_code_fences(text)
    try:
        data = json.loads(content)
    except json.JSONDecodeError as exc:
        match = re.search(r"\[[\s\S]*\]", content)
        if not match:
            logger.warning(f"Failed to parse JSON array: {exc}")
            return None
        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError as inner_exc:
            logger.warning(f"Failed to parse JSON array: {inner_exc}")
            return None
    return data if isinstance(data, list) else None


def validate_model(model_cls: type[ModelT], data: dict | None) -> ModelT | None:
    if data is None:
        return None
    try:
        return model_cls.model_validate(data)
    except ValidationError as exc:
        logger.warning(f"Model validation failed: {exc}")
        return None


def validate_model_list(model_cls: type[ModelT], items: list | None) -> list[ModelT]:
    if not items:
        return []
    validated: list[ModelT] = []
    for item in items:
        if isinstance(item, dict):
            model = validate_model(model_cls, item)
            if model:
                validated.append(model)
    return validated
