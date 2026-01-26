"""Form-related enums."""

from enum import Enum


class FormStatus(str, Enum):
    """Status of a form configuration."""

    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class FormSubmissionStatus(str, Enum):
    """Status of a submitted form response."""

    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"
