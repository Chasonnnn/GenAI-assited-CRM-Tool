"""SQLAlchemy ORM models."""

from __future__ import annotations

from typing import TYPE_CHECKING

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    Numeric,
    String,
    TIMESTAMP,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TSVECTOR, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.enums import (
    DEFAULT_SURROGATE_SOURCE,
)
from app.db.types import EncryptedDate, EncryptedString

if TYPE_CHECKING:
    from app.db.models import (
        Attachment,
        DataRetentionPolicy,
        Organization,
        PipelineStage,
        Queue,
        User,
    )


class Surrogate(Base):
    """
    Primary entity for surrogate applicants.

    Includes soft-delete (is_archived) for data safety.
    Hard delete requires is_archived=true and admin+ role.

    Ownership model (Salesforce-style):
    - owner_type: "user" or "queue"
    - owner_id: UUID of user or queue
    - When in queue, any case_manager+ can claim
    - Claiming sets owner_type="user", owner_id=claimer
    """

    __tablename__ = "surrogates"
    __table_args__ = (
        # Surrogate number unique per org (even archived)
        UniqueConstraint("organization_id", "surrogate_number", name="uq_surrogate_number"),
        # Email unique per org for active surrogates only
        Index(
            "uq_surrogate_email_hash_active",
            "organization_id",
            "email_hash",
            unique=True,
            postgresql_where=text("is_archived = FALSE"),
        ),
        # Query optimization indexes
        Index("idx_surrogates_stage", "stage_id"),  # Single-column for FK lookups
        Index("idx_surrogates_org_stage", "organization_id", "stage_id"),
        Index("idx_surrogates_org_owner", "organization_id", "owner_type", "owner_id"),
        Index("idx_surrogates_org_status_label", "organization_id", "status_label"),
        Index("idx_surrogates_org_created", "organization_id", "created_at"),
        Index("idx_surrogates_org_updated", "organization_id", "updated_at"),
        Index(
            "idx_surrogates_org_active",
            "organization_id",
            postgresql_where=text("is_archived = FALSE"),
        ),
        Index(
            "idx_surrogates_meta_ad",
            "organization_id",
            "meta_ad_external_id",
            postgresql_where=text("meta_ad_external_id IS NOT NULL"),
        ),
        Index(
            "idx_surrogates_meta_form",
            "organization_id",
            "meta_form_id",
            postgresql_where=text("meta_form_id IS NOT NULL"),
        ),
        # GIN index for full-text search
        Index(
            "ix_surrogates_search_vector",
            "search_vector",
            postgresql_using="gin",
        ),
        # PII hash index for phone lookups
        Index("idx_surrogates_org_phone_hash", "organization_id", "phone_hash"),
        # Contact reminder check index for efficient daily job queries
        Index(
            "idx_surrogates_reminder_check",
            "organization_id",
            "owner_type",
            "contact_status",
            "stage_id",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    surrogate_number: Mapped[str] = mapped_column(String(10), nullable=False)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Workflow (v2: pipeline stages)
    stage_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("pipeline_stages.id", ondelete="RESTRICT"),
        nullable=False,
    )
    status_label: Mapped[str] = mapped_column(String(100), nullable=False)

    source: Mapped[str] = mapped_column(
        String(20),
        server_default=text(f"'{DEFAULT_SURROGATE_SOURCE.value}'"),
        nullable=False,
    )
    is_priority: Mapped[bool] = mapped_column(Boolean, server_default=text("FALSE"), nullable=False)

    # Ownership (Salesforce-style single owner model)
    # owner_type="user" + owner_id=user_id, or owner_type="queue" + owner_id=queue_id
    owner_type: Mapped[str] = mapped_column(String(10), nullable=False)
    owner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)

    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    meta_lead_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("meta_leads.id", ondelete="SET NULL"),
        nullable=True,
    )
    # Campaign tracking (denormalized from meta_leads for easy filtering)
    meta_ad_external_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    meta_form_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # Additional campaign hierarchy tracking (captured at conversion time)
    meta_campaign_external_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    meta_adset_external_id: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Import metadata (tracking junk from CSV - ad_id, campaign_id, form_id, etc.)
    # NOT for business data - business data goes to custom fields
    import_metadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Contact (normalized: E.164 phone, 2-letter state)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(EncryptedString, nullable=False)
    email_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    phone: Mapped[str | None] = mapped_column(EncryptedString, nullable=True)
    phone_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    state: Mapped[str | None] = mapped_column(String(2), nullable=True)

    # Demographics
    date_of_birth: Mapped[date | None] = mapped_column(EncryptedDate, nullable=True)
    race: Mapped[str | None] = mapped_column(String(100), nullable=True)
    height_ft: Mapped[Decimal | None] = mapped_column(Numeric(3, 1), nullable=True)
    weight_lb: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Eligibility
    is_age_eligible: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    is_citizen_or_pr: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    has_child: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    is_non_smoker: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    has_surrogate_experience: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    num_deliveries: Mapped[int | None] = mapped_column(Integer, nullable=True)
    num_csections: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # ============================================
    # INSURANCE INFO
    # ============================================
    insurance_company: Mapped[str | None] = mapped_column(String(255), nullable=True)
    insurance_plan_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    insurance_phone: Mapped[str | None] = mapped_column(EncryptedString, nullable=True)
    insurance_policy_number: Mapped[str | None] = mapped_column(EncryptedString, nullable=True)
    insurance_member_id: Mapped[str | None] = mapped_column(EncryptedString, nullable=True)
    insurance_group_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    insurance_subscriber_name: Mapped[str | None] = mapped_column(EncryptedString, nullable=True)
    insurance_subscriber_dob: Mapped[date | None] = mapped_column(EncryptedDate, nullable=True)

    # ============================================
    # IVF CLINIC
    # ============================================
    clinic_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    clinic_address_line1: Mapped[str | None] = mapped_column(EncryptedString, nullable=True)
    clinic_address_line2: Mapped[str | None] = mapped_column(EncryptedString, nullable=True)
    clinic_city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    clinic_state: Mapped[str | None] = mapped_column(String(2), nullable=True)
    clinic_postal: Mapped[str | None] = mapped_column(String(20), nullable=True)
    clinic_phone: Mapped[str | None] = mapped_column(EncryptedString, nullable=True)
    clinic_email: Mapped[str | None] = mapped_column(EncryptedString, nullable=True)

    # ============================================
    # MONITORING CLINIC
    # ============================================
    monitoring_clinic_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    monitoring_clinic_address_line1: Mapped[str | None] = mapped_column(
        EncryptedString, nullable=True
    )
    monitoring_clinic_address_line2: Mapped[str | None] = mapped_column(
        EncryptedString, nullable=True
    )
    monitoring_clinic_city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    monitoring_clinic_state: Mapped[str | None] = mapped_column(String(2), nullable=True)
    monitoring_clinic_postal: Mapped[str | None] = mapped_column(String(20), nullable=True)
    monitoring_clinic_phone: Mapped[str | None] = mapped_column(EncryptedString, nullable=True)
    monitoring_clinic_email: Mapped[str | None] = mapped_column(EncryptedString, nullable=True)

    # ============================================
    # OB PROVIDER
    # ============================================
    ob_provider_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ob_clinic_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ob_address_line1: Mapped[str | None] = mapped_column(EncryptedString, nullable=True)
    ob_address_line2: Mapped[str | None] = mapped_column(EncryptedString, nullable=True)
    ob_city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    ob_state: Mapped[str | None] = mapped_column(String(2), nullable=True)
    ob_postal: Mapped[str | None] = mapped_column(String(20), nullable=True)
    ob_phone: Mapped[str | None] = mapped_column(EncryptedString, nullable=True)
    ob_email: Mapped[str | None] = mapped_column(EncryptedString, nullable=True)

    # ============================================
    # DELIVERY HOSPITAL
    # ============================================
    delivery_hospital_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    delivery_hospital_address_line1: Mapped[str | None] = mapped_column(
        EncryptedString, nullable=True
    )
    delivery_hospital_address_line2: Mapped[str | None] = mapped_column(
        EncryptedString, nullable=True
    )
    delivery_hospital_city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    delivery_hospital_state: Mapped[str | None] = mapped_column(String(2), nullable=True)
    delivery_hospital_postal: Mapped[str | None] = mapped_column(String(20), nullable=True)
    delivery_hospital_phone: Mapped[str | None] = mapped_column(EncryptedString, nullable=True)
    delivery_hospital_email: Mapped[str | None] = mapped_column(EncryptedString, nullable=True)

    # ============================================
    # PREGNANCY TRACKING
    # ============================================
    pregnancy_start_date: Mapped[date | None] = mapped_column(EncryptedDate, nullable=True)
    pregnancy_due_date: Mapped[date | None] = mapped_column(EncryptedDate, nullable=True)
    actual_delivery_date: Mapped[date | None] = mapped_column(EncryptedDate, nullable=True)

    # Soft delete
    is_archived: Mapped[bool] = mapped_column(Boolean, server_default=text("FALSE"), nullable=False)
    archived_at: Mapped[datetime | None] = mapped_column(nullable=True)
    archived_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # Last contact tracking
    last_contacted_at: Mapped[datetime | None] = mapped_column(nullable=True)
    last_contact_method: Mapped[str | None] = mapped_column(
        String(20), nullable=True
    )  # email, phone, note

    # Contact attempts tracking
    assigned_at: Mapped[datetime | None] = mapped_column(
        nullable=True
    )  # When assigned to current owner
    contact_status: Mapped[str] = mapped_column(
        String(20), server_default=text("'unreached'"), nullable=False
    )
    contacted_at: Mapped[datetime | None] = mapped_column(
        nullable=True
    )  # When first successful contact

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        server_default=text("now()"), onupdate=text("now()"), nullable=False
    )

    # Full-text search vector (managed by trigger)
    search_vector = mapped_column(TSVECTOR, nullable=True)

    # Relationships
    organization: Mapped["Organization"] = relationship(back_populates="surrogates")
    created_by: Mapped["User | None"] = relationship(foreign_keys=[created_by_user_id])
    archived_by: Mapped["User | None"] = relationship(foreign_keys=[archived_by_user_id])
    stage: Mapped["PipelineStage"] = relationship(foreign_keys=[stage_id])

    # Owner relationships for eager loading (fixes N+1 query)
    # These use custom join conditions since owner_id can point to either User or Queue
    # Using selectin loading to avoid LEFT OUTER JOIN conflicts with FOR UPDATE
    owner_user: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[owner_id],
        primaryjoin="and_(Surrogate.owner_id==User.id, Surrogate.owner_type=='user')",
        viewonly=True,
        lazy="selectin",
    )
    owner_queue: Mapped["Queue | None"] = relationship(
        "Queue",
        foreign_keys=[owner_id],
        primaryjoin="and_(Surrogate.owner_id==Queue.id, Surrogate.owner_type=='queue')",
        viewonly=True,
        lazy="selectin",
    )

    # Notes use EntityNote with entity_type='surrogate' - no direct relationship
    status_history: Mapped[list["SurrogateStatusHistory"]] = relationship(
        back_populates="surrogate", cascade="all, delete-orphan"
    )
    contact_attempts: Mapped[list["SurrogateContactAttempt"]] = relationship(
        back_populates="surrogate",
        cascade="all, delete-orphan",
        order_by="desc(SurrogateContactAttempt.attempted_at)",
    )


class SurrogateStatusHistory(Base):
    """
    Tracks all status changes on surrogates for audit and timeline.

    Also records archive/restore operations.

    Dual timestamps for backdating support:
    - effective_at: When the change actually occurred (user-provided or now)
    - recorded_at: When it was recorded in the system (always server-generated)
    - changed_at: Derived from effective_at for backward compatibility
    """

    __tablename__ = "surrogate_status_history"
    __table_args__ = (
        Index("idx_surrogate_history_surrogate", "surrogate_id", "changed_at"),
        Index("idx_surrogate_history_org_changed", "organization_id", "changed_at"),
        Index(
            "idx_surrogate_history_org_stage_changed",
            "organization_id",
            "to_stage_id",
            "changed_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    surrogate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("surrogates.id", ondelete="CASCADE"), nullable=False
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    # v2: Stage references with label snapshots
    from_stage_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("pipeline_stages.id", ondelete="SET NULL"),
        nullable=True,
    )
    to_stage_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("pipeline_stages.id", ondelete="SET NULL"),
        nullable=True,
    )
    from_label_snapshot: Mapped[str | None] = mapped_column(String(100), nullable=True)
    to_label_snapshot: Mapped[str | None] = mapped_column(String(100), nullable=True)

    changed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    changed_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)

    # Dual timestamps for backdating support
    effective_at: Mapped[datetime | None] = mapped_column(
        nullable=True
    )  # When it actually happened
    recorded_at: Mapped[datetime] = mapped_column(
        server_default=text("now()"), nullable=False
    )  # When recorded

    # Audit fields for approval flow
    requested_at: Mapped[datetime | None] = mapped_column(
        nullable=True
    )  # For regressions: when requested
    approved_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(nullable=True)  # When admin approved
    is_undo: Mapped[bool] = mapped_column(
        server_default=text("false"), nullable=False
    )  # Undo within grace period
    request_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("status_change_requests.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Relationships
    surrogate: Mapped["Surrogate"] = relationship(back_populates="status_history")


class SurrogateActivityLog(Base):
    """
    Comprehensive activity log for all surrogate changes.

    Tracks: create, edit, status change, assign, archive, notes, etc.
    Stores new values for changed fields. Actor names resolved at read-time.
    """

    __tablename__ = "surrogate_activity_log"
    __table_args__ = (
        Index("idx_surrogate_activity_surrogate_time", "surrogate_id", "created_at"),
        Index("idx_surrogate_activity_org_time", "organization_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    surrogate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("surrogates.id", ondelete="CASCADE"), nullable=False
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    activity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    details: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)

    # Relationships
    surrogate: Mapped["Surrogate"] = relationship()
    actor: Mapped["User | None"] = relationship(foreign_keys=[actor_user_id])


# NOTE: SurrogateNote model removed (migrated to EntityNote with entity_type='surrogate')
# See migration 0013_migrate_casenotes.py


class SurrogateContactAttempt(Base):
    """
    Track individual contact attempts for surrogates.

    Supports:
    - Multi-method attempts per entry
    - Back-dated entries with audit trail
    - Assignment tracking for reminder logic
    """

    __tablename__ = "surrogate_contact_attempts"
    __table_args__ = (
        Index("idx_contact_attempts_surrogate", "surrogate_id", "attempted_at"),
        Index(
            "idx_contact_attempts_org_pending",
            "organization_id",
            "outcome",
            "attempted_at",
            postgresql_where=text("outcome != 'reached'"),
        ),
        Index(
            "idx_contact_attempts_surrogate_owner",
            "surrogate_id",
            "surrogate_owner_id_at_attempt",
            "attempted_at",
        ),
        CheckConstraint(
            "array_length(contact_methods, 1) > 0", name="ck_contact_methods_not_empty"
        ),
        CheckConstraint(
            "contact_methods <@ ARRAY['phone', 'email', 'sms']::VARCHAR[]",
            name="ck_contact_methods_valid",
        ),
        CheckConstraint(
            "attempted_at <= (now() + interval '5 minutes')",
            name="ck_attempted_at_not_future",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    surrogate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("surrogates.id", ondelete="CASCADE"), nullable=False
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    attempted_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # Multi-method support: store as array
    contact_methods: Mapped[list[str]] = mapped_column(
        ARRAY(String), nullable=False, server_default=text("'{}'")
    )

    outcome: Mapped[str] = mapped_column(String(30), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Audit trail: distinguish when logged vs when it actually happened
    attempted_at: Mapped[datetime] = mapped_column(
        nullable=False
    )  # When the attempt actually occurred
    created_at: Mapped[datetime] = mapped_column(
        server_default=text("now()"), nullable=False
    )  # When it was logged

    # Denormalized for performance: which assignment does this attempt belong to?
    surrogate_owner_id_at_attempt: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False
    )  # surrogates.owner_id at time of attempt

    # Relationships
    surrogate: Mapped["Surrogate"] = relationship(back_populates="contact_attempts")
    attempted_by: Mapped["User | None"] = relationship()

    @property
    def is_backdated(self) -> bool:
        """Check if this attempt was logged after it occurred."""
        return self.attempted_at < self.created_at


class SurrogateImport(Base):
    """
    Tracks CSV import jobs for surrogates.

    Flow: upload → preview → confirm (async job) → complete

    Dedupe:
    - Matches by email against all surrogates (including archived)
    - Also checks for duplicates within the CSV itself
    """

    __tablename__ = "surrogate_imports"
    __table_args__ = (Index("idx_surrogate_imports_org_created", "organization_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # File info
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_content: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)

    # Status: pending, processing, completed, failed
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)

    # Counts
    total_rows: Mapped[int] = mapped_column(default=0, nullable=False)
    imported_count: Mapped[int] = mapped_column(default=0, nullable=False)
    skipped_count: Mapped[int] = mapped_column(default=0, nullable=False)
    error_count: Mapped[int] = mapped_column(default=0, nullable=False)

    # Error details (list of {row: int, errors: list[str]})
    errors: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)

    # Enhanced detection & mapping (v2)
    template_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("import_templates.id", ondelete="SET NULL"),
        nullable=True,
    )
    detected_encoding: Mapped[str | None] = mapped_column(String(20), nullable=True)
    detected_delimiter: Mapped[str | None] = mapped_column(String(5), nullable=True)
    column_mapping_snapshot: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    date_ambiguity_warnings: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    unknown_column_behavior: Mapped[str] = mapped_column(
        String(20), default="ignore", nullable=False
    )

    # Admin approval workflow
    # Status values: 'pending', 'awaiting_approval', 'approved', 'processing', 'completed', 'rejected', 'failed'
    approved_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    deduplication_stats: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Relationships
    organization: Mapped["Organization"] = relationship()
    created_by: Mapped["User | None"] = relationship(foreign_keys=[created_by_user_id])
    approved_by: Mapped["User | None"] = relationship(foreign_keys=[approved_by_user_id])
    template: Mapped["ImportTemplate | None"] = relationship(back_populates="imports")


# =============================================================================
# Import Templates & Custom Fields
# =============================================================================


class ImportTemplate(Base):
    """
    Reusable CSV import configuration.

    Stores column mappings, transformations, and import settings.
    One template per org can be is_default=true (enforced via partial index).
    """

    __tablename__ = "import_templates"
    __table_args__ = (
        Index("idx_import_templates_org", "organization_id"),
        Index(
            "uq_import_template_default",
            "organization_id",
            unique=True,
            postgresql_where=text("is_default = TRUE"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_default: Mapped[bool] = mapped_column(default=False, nullable=False)

    # File format settings
    encoding: Mapped[str] = mapped_column(
        String(20), default="auto", nullable=False
    )  # 'auto', 'utf-8', 'utf-16'
    delimiter: Mapped[str] = mapped_column(
        String(5), default="auto", nullable=False
    )  # 'auto', ',', '\t'
    has_header: Mapped[bool] = mapped_column(default=True, nullable=False)

    # Column mappings: [{csv_column: str, surrogate_field: str, transformation: str|null}]
    column_mappings: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    # Transformations config: {field: {transformer: str, options: dict}}
    transformations: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # What to do with unmapped columns: 'ignore', 'metadata', 'warn'
    unknown_column_behavior: Mapped[str] = mapped_column(
        String(20), default="ignore", nullable=False
    )

    # Usage stats
    usage_count: Mapped[int] = mapped_column(default=0, nullable=False)
    last_used_at: Mapped[datetime | None] = mapped_column(nullable=True)

    # Audit
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)

    # Relationships
    organization: Mapped["Organization"] = relationship()
    created_by: Mapped["User | None"] = relationship()
    imports: Mapped[list["SurrogateImport"]] = relationship(back_populates="template")


class CustomField(Base):
    """
    Org-scoped custom field definition.

    Allows organizations to define additional fields for surrogates
    to capture data that doesn't fit in standard schema fields.
    """

    __tablename__ = "custom_fields"
    __table_args__ = (
        UniqueConstraint("organization_id", "key", name="uq_custom_field_key"),
        Index("idx_custom_fields_org", "organization_id"),
        Index("idx_custom_fields_org_active", "organization_id", "is_active"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Field definition
    key: Mapped[str] = mapped_column(String(100), nullable=False)  # e.g., "criminal_history"
    label: Mapped[str] = mapped_column(String(255), nullable=False)  # e.g., "Criminal History"
    field_type: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # 'text', 'number', 'boolean', 'date', 'select'
    options: Mapped[list | None] = mapped_column(
        JSONB, nullable=True
    )  # For select type: ["option1", "option2"]

    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)

    # Audit
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)

    # Relationships
    organization: Mapped["Organization"] = relationship()
    created_by: Mapped["User | None"] = relationship()
    values: Mapped[list["CustomFieldValue"]] = relationship(
        back_populates="custom_field",
        cascade="all, delete-orphan",
    )


class CustomFieldValue(Base):
    """
    Custom field value for a surrogate.

    Stores the actual value for a custom field on a specific surrogate.
    """

    __tablename__ = "custom_field_values"
    __table_args__ = (
        UniqueConstraint("surrogate_id", "custom_field_id", name="uq_custom_field_value"),
        Index("idx_custom_field_values_surrogate", "surrogate_id"),
        Index("idx_custom_field_values_field", "custom_field_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    surrogate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("surrogates.id", ondelete="CASCADE"),
        nullable=False,
    )
    custom_field_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("custom_fields.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Store any type as JSONB
    value_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Relationships
    surrogate: Mapped["Surrogate"] = relationship()
    custom_field: Mapped["CustomField"] = relationship(back_populates="values")


# =============================================================================
# Org-Configurable Pipelines (v2 - Full CRUD)
# =============================================================================


class SurrogateProfileOverride(Base):
    """
    Override values for profile card (independent of submission/surrogate fields).

    Used by case_manager+ to customize profile view without modifying
    the original submission or surrogate fields.
    """

    __tablename__ = "surrogate_profile_overrides"
    __table_args__ = (
        UniqueConstraint("surrogate_id", "field_key", name="uq_surrogate_profile_override_field"),
        Index("idx_profile_overrides_surrogate", "surrogate_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    surrogate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("surrogates.id", ondelete="CASCADE"), nullable=False
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    field_key: Mapped[str] = mapped_column(String(255), nullable=False)
    value: Mapped[dict] = mapped_column(JSONB, nullable=False)
    updated_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)

    # Relationships
    surrogate: Mapped["Surrogate"] = relationship()
    organization: Mapped["Organization"] = relationship()
    updated_by: Mapped["User | None"] = relationship()


class SurrogateProfileState(Base):
    """
    Tracks the base submission used for a surrogate profile card.

    Allows Sync + Save to pin the profile base to a new submission.
    """

    __tablename__ = "surrogate_profile_states"
    __table_args__ = (
        UniqueConstraint("surrogate_id", name="uq_surrogate_profile_state_surrogate"),
        Index("idx_profile_state_surrogate", "surrogate_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    surrogate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("surrogates.id", ondelete="CASCADE"), nullable=False
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    base_submission_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("form_submissions.id", ondelete="SET NULL"),
        nullable=True,
    )
    updated_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)

    surrogate: Mapped["Surrogate"] = relationship()
    organization: Mapped["Organization"] = relationship()
    updated_by: Mapped["User | None"] = relationship()


class SurrogateProfileHiddenField(Base):
    """
    Tracks hidden fields in surrogate profile card.

    Hidden fields show as masked values ('*' or '-') in profile exports.
    case_manager+ can toggle visibility.
    """

    __tablename__ = "surrogate_profile_hidden_fields"
    __table_args__ = (
        UniqueConstraint("surrogate_id", "field_key", name="uq_surrogate_profile_hidden_field"),
        Index("idx_profile_hidden_surrogate", "surrogate_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    surrogate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("surrogates.id", ondelete="CASCADE"), nullable=False
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    field_key: Mapped[str] = mapped_column(String(255), nullable=False)
    hidden_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    hidden_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)

    # Relationships
    surrogate: Mapped["Surrogate"] = relationship()
    organization: Mapped["Organization"] = relationship()
    hidden_by: Mapped["User | None"] = relationship()


# =============================================================================
# Appointments & Scheduling Models
# =============================================================================


class SurrogateInterview(Base):
    """
    Interview record for a surrogate.

    Supports multiple interviews per surrogate with versioned transcripts.
    Transcripts > 100KB are offloaded to S3 (text kept inline for search).
    """

    __tablename__ = "surrogate_interviews"
    __table_args__ = (
        Index("ix_surrogate_interviews_surrogate_id", "surrogate_id"),
        Index("ix_surrogate_interviews_org_conducted", "organization_id", "conducted_at"),
        Index(
            "ix_surrogate_interviews_search_vector",
            "search_vector",
            postgresql_using="gin",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    surrogate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("surrogates.id", ondelete="CASCADE"),
        nullable=False,
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Metadata
    interview_type: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # 'phone', 'video', 'in_person'
    conducted_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    conducted_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    duration_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Current transcript (denormalized for quick reads)
    transcript_json: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True
    )  # TipTap JSON (canonical format)
    transcript_text: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )  # Always stored for search/diff
    transcript_storage_key: Mapped[str | None] = mapped_column(
        String(500), nullable=True
    )  # S3 key if offloaded
    transcript_version: Mapped[int] = mapped_column(
        Integer, server_default=text("1"), nullable=False
    )
    transcript_hash: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )  # SHA256 for no-change guard
    transcript_size_bytes: Mapped[int] = mapped_column(
        Integer, server_default=text("0"), nullable=False
    )

    # Status
    status: Mapped[str] = mapped_column(
        String(20), server_default=text("'completed'"), nullable=False
    )  # 'draft', 'completed'

    # Retention
    retention_policy_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("data_retention_policies.id"),
        nullable=True,
    )
    expires_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)

    # Full-text search vector (managed by trigger)
    search_vector = mapped_column(TSVECTOR, nullable=True)

    # Relationships
    surrogate: Mapped["Surrogate"] = relationship()
    organization: Mapped["Organization"] = relationship()
    conducted_by: Mapped["User"] = relationship()
    versions: Mapped[list["InterviewTranscriptVersion"]] = relationship(
        back_populates="interview", cascade="all, delete-orphan"
    )
    notes: Mapped[list["InterviewNote"]] = relationship(
        back_populates="interview", cascade="all, delete-orphan"
    )
    interview_attachments: Mapped[list["InterviewAttachment"]] = relationship(
        back_populates="interview", cascade="all, delete-orphan"
    )
    retention_policy: Mapped["DataRetentionPolicy | None"] = relationship()


class InterviewTranscriptVersion(Base):
    """
    Version history for interview transcripts.

    Created automatically when transcript changes (with no-change guard via hash).
    Supports restore to any previous version.
    """

    __tablename__ = "interview_transcript_versions"
    __table_args__ = (
        UniqueConstraint("interview_id", "version", name="uq_interview_version"),
        Index("ix_interview_versions_interview", "interview_id", "version"),
        Index("ix_interview_versions_org", "organization_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    interview_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("surrogate_interviews.id", ondelete="CASCADE"),
        nullable=False,
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)

    # Content
    content_html: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_storage_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    content_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)

    # Metadata
    author_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    source: Mapped[str] = mapped_column(
        String(30), nullable=False
    )  # 'manual', 'ai_transcription', 'restore'

    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)

    # Relationships
    interview: Mapped["SurrogateInterview"] = relationship(back_populates="versions")
    organization: Mapped["Organization"] = relationship()
    author: Mapped["User"] = relationship()


class InterviewNote(Base):
    """
    Shared notes on interviews, optionally anchored to transcript selections.

    Supports:
    - General notes (no anchor)
    - Anchored comments (with comment_id + anchor_text)
    - Reply threads (parent_id links to parent note)
    - Resolve functionality (resolved_at/resolved_by_user_id)

    Anchors are tied to a specific transcript version.
    """

    __tablename__ = "interview_notes"
    __table_args__ = (
        Index("ix_interview_notes_interview", "interview_id"),
        Index("ix_interview_notes_org", "organization_id"),
        Index("ix_interview_notes_parent", "parent_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    interview_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("surrogate_interviews.id", ondelete="CASCADE"),
        nullable=False,
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )

    # Content (sanitized HTML)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # Anchor to specific version (prevents drift)
    transcript_version: Mapped[int] = mapped_column(Integer, nullable=False)

    # TipTap comment mark ID (preferred - stable anchor)
    comment_id: Mapped[str | None] = mapped_column(
        String(36), nullable=True, index=True
    )  # UUID format

    anchor_text: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Metadata
    author_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )

    # Thread support (for replies)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("interview_notes.id", ondelete="CASCADE"),
        nullable=True,
    )

    # Resolve support
    resolved_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    resolved_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)

    # Relationships
    interview: Mapped["SurrogateInterview"] = relationship(back_populates="notes")
    organization: Mapped["Organization"] = relationship()
    author: Mapped["User"] = relationship(foreign_keys=[author_user_id])
    resolved_by: Mapped["User | None"] = relationship(foreign_keys=[resolved_by_user_id])
    parent: Mapped["InterviewNote | None"] = relationship(
        "InterviewNote",
        remote_side="InterviewNote.id",
        back_populates="replies",
        foreign_keys=[parent_id],
    )
    replies: Mapped[list["InterviewNote"]] = relationship(
        "InterviewNote",
        back_populates="parent",
        foreign_keys="InterviewNote.parent_id",
        order_by="InterviewNote.created_at",
    )


class InterviewAttachment(Base):
    """
    Links attachments to interviews.

    Reuses the existing Attachment model. Supports AI transcription
    for audio/video files.
    """

    __tablename__ = "interview_attachments"
    __table_args__ = (
        UniqueConstraint("interview_id", "attachment_id", name="uq_interview_attachment"),
        Index("ix_interview_attachments_interview", "interview_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    interview_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("surrogate_interviews.id", ondelete="CASCADE"),
        nullable=False,
    )
    attachment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("attachments.id", ondelete="CASCADE"),
        nullable=False,
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )

    # AI transcription (for audio/video only)
    transcription_status: Mapped[str | None] = mapped_column(
        String(20), nullable=True
    )  # 'pending', 'processing', 'completed', 'failed'
    transcription_job_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    transcription_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    transcription_completed_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)

    # Relationships
    interview: Mapped["SurrogateInterview"] = relationship(back_populates="interview_attachments")
    attachment: Mapped["Attachment"] = relationship()
    organization: Mapped["Organization"] = relationship()


# =============================================================================
# Journey Featured Images
# =============================================================================


class JourneyFeaturedImage(Base):
    """
    Featured image selection for journey milestones.

    Allows case managers to select from surrogate attachments
    as the featured image for each milestone in the journey timeline.
    """

    __tablename__ = "journey_featured_images"
    __table_args__ = (
        UniqueConstraint("surrogate_id", "milestone_slug", name="uq_journey_featured_image"),
        Index("ix_journey_featured_images_surrogate", "surrogate_id"),
        Index("ix_journey_featured_images_org", "organization_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    surrogate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("surrogates.id", ondelete="CASCADE"),
        nullable=False,
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    milestone_slug: Mapped[str] = mapped_column(String(100), nullable=False)
    attachment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("attachments.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Audit fields
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    updated_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        server_default=text("now()"), onupdate=text("now()"), nullable=False
    )

    # Relationships
    surrogate: Mapped["Surrogate"] = relationship()
    organization: Mapped["Organization"] = relationship()
    attachment: Mapped["Attachment"] = relationship()
    created_by: Mapped["User | None"] = relationship(foreign_keys=[created_by_user_id])
    updated_by: Mapped["User | None"] = relationship(foreign_keys=[updated_by_user_id])
