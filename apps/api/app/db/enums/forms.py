"""Form-related enums."""

from enum import Enum


class FormStatus(str, Enum):
    """Status of a form configuration."""

    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class FormPurpose(str, Enum):
    """Business intent of a form."""

    SURROGATE_APPLICATION = "surrogate_application"
    LEAD_CAPTURE = "lead_capture"
    EVENT_INTAKE = "event_intake"
    OTHER = "other"


class FieldSensitivity(str, Enum):
    """Privacy classification for public form fields."""

    IDENTITY = "identity"
    CONTACT = "contact"
    CAMPAIGN_SAFE = "campaign_safe"
    OPERATIONAL = "operational"
    SENSITIVE_HEALTH = "sensitive_health"
    SENSITIVE_REPRODUCTIVE = "sensitive_reproductive"
    SENSITIVE_FINANCIAL = "sensitive_financial"
    SENSITIVE_LEGAL = "sensitive_legal"
    FREE_TEXT_UNCLASSIFIED = "free_text_unclassified"
    FILE = "file"


class TrackingMode(str, Enum):
    """Outbound tracking policy for public intake surfaces."""

    INTERNAL_ONLY = "internal_only"
    PRIVACY_SAFE_LEAD = "privacy_safe_lead"
    DISABLED = "disabled"
    ADVANCED = "advanced"


class FormSubmissionStatus(str, Enum):
    """Status of a submitted form response."""

    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"


class FormLinkMode(str, Enum):
    """How an application link is distributed."""

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
