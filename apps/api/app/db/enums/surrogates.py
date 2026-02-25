"""Surrogate-related enums."""

from enum import Enum


class SurrogateStatus(str, Enum):
    """
    Surrogate status enum covering Intake (Stage A) and Post-approval (Stage B).

    Stage A (Intake Pipeline):
        new_unread → contacted → qualified → interview_scheduled
        → application_submitted → under_review → approved → lost/disqualified

    Stage B (Post-Approval, Case Manager only):
        ready_to_match → matched → medical_clearance_passed → legal_clearance_passed
        → transfer_cycle → second_hcg_confirmed → heartbeat_confirmed
        → ob_care_established → anatomy_scanned → delivered
    """

    # Stage A: Intake Pipeline
    NEW_UNREAD = "new_unread"
    CONTACTED = "contacted"
    QUALIFIED = "qualified"  # Intake confirmed info, applicant is qualified
    INTERVIEW_SCHEDULED = "interview_scheduled"  # Interview scheduled with applicant
    APPLICATION_SUBMITTED = "application_submitted"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    LOST = "lost"
    DISQUALIFIED = "disqualified"

    # Stage B: Post-Approval (Case Manager only)
    READY_TO_MATCH = "ready_to_match"  # Ready for matching with intended parents
    MATCHED = "matched"
    MEDICAL_CLEARANCE_PASSED = "medical_clearance_passed"  # Medical exams completed
    LEGAL_CLEARANCE_PASSED = "legal_clearance_passed"  # Legal contracts finalized
    TRANSFER_CYCLE = "transfer_cycle"  # Embryo transfer cycle
    SECOND_HCG_CONFIRMED = "second_hcg_confirmed"  # Second HCG test confirmed
    HEARTBEAT_CONFIRMED = "heartbeat_confirmed"  # Fetal heartbeat confirmed
    OB_CARE_ESTABLISHED = "ob_care_established"  # OB care established
    ANATOMY_SCANNED = "anatomy_scanned"  # Anatomy scan completed
    DELIVERED = "delivered"

    # Archive pseudo-status (for history tracking)
    ARCHIVED = "archived"
    RESTORED = "restored"

    @classmethod
    def intake_visible(cls) -> list[str]:
        """Statuses visible to intake specialists (Stage A)."""
        return [
            cls.NEW_UNREAD.value,
            cls.CONTACTED.value,
            cls.QUALIFIED.value,
            cls.INTERVIEW_SCHEDULED.value,
            cls.APPLICATION_SUBMITTED.value,
            cls.UNDER_REVIEW.value,
            cls.APPROVED.value,
            cls.LOST.value,
            cls.DISQUALIFIED.value,
        ]

    @classmethod
    def surrogate_manager_only(cls) -> list[str]:
        """Statuses only accessible by case_manager+ (Stage B)."""
        return [
            cls.READY_TO_MATCH.value,
            cls.MATCHED.value,
            cls.MEDICAL_CLEARANCE_PASSED.value,
            cls.LEGAL_CLEARANCE_PASSED.value,
            cls.TRANSFER_CYCLE.value,
            cls.SECOND_HCG_CONFIRMED.value,
            cls.HEARTBEAT_CONFIRMED.value,
            cls.OB_CARE_ESTABLISHED.value,
            cls.ANATOMY_SCANNED.value,
            cls.DELIVERED.value,
        ]


class SurrogateSource(str, Enum):
    """How the surrogate record was created."""

    MANUAL = "manual"
    META = "meta"
    TIKTOK = "tiktok"
    GOOGLE = "google"
    WEBSITE = "website"
    REFERRAL = "referral"
    IMPORT = "import"  # CSV bulk import
    AGENCY = "agency"  # Created by agency staff
    OTHER = "other"


class SurrogateActivityType(str, Enum):
    """Types of activities logged in surrogate history."""

    SURROGATE_CREATED = "surrogate_created"
    INFO_EDITED = "info_edited"
    STATUS_CHANGED = "status_changed"
    ASSIGNED = "assigned"
    UNASSIGNED = "unassigned"
    SURROGATE_ASSIGNED_TO_QUEUE = "surrogate_assigned_to_queue"
    SURROGATE_CLAIMED = "surrogate_claimed"
    SURROGATE_RELEASED = "surrogate_released"
    PRIORITY_CHANGED = "priority_changed"
    ARCHIVED = "archived"
    RESTORED = "restored"
    NOTE_ADDED = "note_added"
    NOTE_DELETED = "note_deleted"
    ATTACHMENT_ADDED = "attachment_added"
    ATTACHMENT_DELETED = "attachment_deleted"
    EMAIL_SENT = "email_sent"  # Email sent to surrogate contact
    EMAIL_BOUNCED = "email_bounced"  # Email delivery failed (bounce)
    TASK_CREATED = "task_created"  # Task created for surrogate
    TASK_DELETED = "task_deleted"  # Task deleted for surrogate
    MATCH_PROPOSED = "match_proposed"  # New match proposed
    MATCH_REVIEWING = "match_reviewing"  # Match entered review
    MATCH_ACCEPTED = "match_accepted"  # Match accepted
    MATCH_REJECTED = "match_rejected"  # Match rejected
    MATCH_CANCELLED = "match_cancelled"  # Match cancelled/withdrawn
    APPLICATION_EDITED = "application_edited"
    PROFILE_EDITED = "profile_edited"
    PROFILE_HIDDEN = "profile_hidden"
    CONTACT_ATTEMPT = "contact_attempt"  # Contact attempt logged
    INTERVIEW_OUTCOME_LOGGED = "interview_outcome_logged"  # Interview outcome recorded
    WORKFLOW_APPROVAL_RESOLVED = (
        "workflow_approval_resolved"  # Workflow approval approved/denied/expired
    )
    WORKFLOW_APPROVAL_INVALIDATED = (
        "workflow_approval_invalidated"  # Approval invalidated (owner change)
    )
    # Medical/Insurance/Pregnancy updates (no PHI logged, just audit trail)
    MEDICAL_INFO_UPDATED = "medical_info_updated"
    INSURANCE_INFO_UPDATED = "insurance_info_updated"
    PREGNANCY_DATES_UPDATED = "pregnancy_dates_updated"
    # Journey featured images
    JOURNEY_IMAGE_SET = "journey_image_set"
    JOURNEY_IMAGE_CLEARED = "journey_image_cleared"


class OwnerType(str, Enum):
    """Owner type for surrogates - Salesforce-style single owner model."""

    USER = "user"
    QUEUE = "queue"


class ContactMethod(str, Enum):
    """Contact methods - can select multiple per attempt."""

    PHONE = "phone"
    EMAIL = "email"
    SMS = "sms"


class ContactOutcome(str, Enum):
    """Outcome of a contact attempt."""

    REACHED = "reached"
    NO_ANSWER = "no_answer"
    VOICEMAIL = "voicemail"
    WRONG_NUMBER = "wrong_number"
    EMAIL_BOUNCED = "email_bounced"


class ContactStatus(str, Enum):
    """Surrogate-level contact status for reminder logic."""

    UNREACHED = "unreached"
    REACHED = "reached"
