"""Donor domain enums."""

from enum import Enum


class DonorType(str, Enum):
    """Supported donor subtypes."""

    EGG = "egg"
    SPERM = "sperm"
