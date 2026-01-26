"""Polymorphic entity enums."""

from enum import Enum


class EntityType(str, Enum):
    """Entity types for polymorphic relationships (e.g., notes)."""

    SURROGATE = "surrogate"
    INTENDED_PARENT = "intended_parent"
