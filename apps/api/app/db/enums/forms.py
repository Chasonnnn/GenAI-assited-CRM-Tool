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


class FormLinkMode(str, Enum):
    """How an application link is distributed."""

    DEDICATED = "dedicated"
    SHARED = "shared"


class FormSubmissionMatchStatus(str, Enum):
    """Identity matching outcome for shared-link submissions."""

    LINKED = "linked"
    AMBIGUOUS_REVIEW = "ambiguous_review"
    LEAD_CREATED = "lead_created"


class IntakeLeadStatus(str, Enum):
    """Lifecycle of provisional intake leads."""

    PENDING_REVIEW = "pending_review"
    PROMOTED = "promoted"
