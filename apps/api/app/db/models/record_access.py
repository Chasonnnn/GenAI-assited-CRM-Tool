"""Organization-scoped record rules and retained Intake relationships."""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class RoleRecordScope(Base):
    __tablename__ = "role_record_scopes"
    __table_args__ = (
        Index("uq_role_record_scope", "organization_id", "role", "module", unique=True),
        CheckConstraint(
            "module IN ('surrogates', 'donors', 'intended_parents')", name="ck_role_scope_module"
        ),
        CheckConstraint(
            "assignment IN ('all', 'assigned', 'none')", name="ck_role_scope_assignment"
        ),
        CheckConstraint(
            "phase IN ('all', 'pre_approval', 'post_approval')", name="ck_role_scope_phase"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(50), nullable=False)
    module: Mapped[str] = mapped_column(String(30), nullable=False)
    assignment: Mapped[str] = mapped_column(String(12), nullable=False)
    phase: Mapped[str] = mapped_column(String(20), nullable=False)
    stage_ids: Mapped[list[str]] = mapped_column(
        JSONB, server_default=text("'[]'::jsonb"), default=list, nullable=False
    )


class UserRecordScopeAddition(Base):
    __tablename__ = "user_record_scope_additions"
    __table_args__ = (
        Index("idx_user_record_scope", "organization_id", "user_id", "module"),
        CheckConstraint(
            "module IN ('surrogates', 'donors', 'intended_parents')", name="ck_user_scope_module"
        ),
        CheckConstraint("assignment IN ('all', 'assigned')", name="ck_user_scope_assignment"),
        CheckConstraint(
            "phase IN ('all', 'pre_approval', 'post_approval')", name="ck_user_scope_phase"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    membership_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("memberships.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    module: Mapped[str] = mapped_column(String(30), nullable=False)
    assignment: Mapped[str] = mapped_column(String(12), nullable=False)
    phase: Mapped[str] = mapped_column(String(20), nullable=False)
    stage_ids: Mapped[list[str]] = mapped_column(
        JSONB, server_default=text("'[]'::jsonb"), default=list, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )


class RecordCollaborator(Base):
    __tablename__ = "record_collaborators"
    __table_args__ = (
        CheckConstraint(
            "(surrogate_id IS NOT NULL AND donor_id IS NULL) OR (surrogate_id IS NULL AND donor_id IS NOT NULL)",
            name="ck_record_collaborator_subject",
        ),
        Index(
            "uq_surrogate_collaborator",
            "organization_id",
            "surrogate_id",
            "user_id",
            unique=True,
            postgresql_where=text("surrogate_id IS NOT NULL"),
        ),
        Index(
            "uq_donor_collaborator",
            "organization_id",
            "donor_id",
            "user_id",
            unique=True,
            postgresql_where=text("donor_id IS NOT NULL"),
        ),
        Index("idx_record_collaborator_user", "organization_id", "user_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    membership_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("memberships.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    surrogate_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("surrogates.id", ondelete="CASCADE"), nullable=True
    )
    donor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("donors.id", ondelete="CASCADE"), nullable=True
    )
    granted_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )


class RecordScopeMigrationReview(Base):
    __tablename__ = "record_scope_migration_reviews"
    __table_args__ = (
        CheckConstraint(
            "resolved_phase IS NULL OR resolved_phase IN ('pre_approval', 'post_approval')",
            name="ck_record_scope_review_phase",
        ),
        CheckConstraint(
            "(surrogate_id IS NOT NULL AND donor_id IS NULL) OR (surrogate_id IS NULL AND donor_id IS NOT NULL)",
            name="ck_record_scope_review_subject",
        ),
        CheckConstraint(
            "decision IN ('retain_verified_owner', 'no_verified_owner')",
            name="ck_record_scope_review_decision",
        ),
        Index(
            "uq_surrogate_scope_review",
            "organization_id",
            "surrogate_id",
            unique=True,
            postgresql_where=text("surrogate_id IS NOT NULL"),
        ),
        Index(
            "uq_donor_scope_review",
            "organization_id",
            "donor_id",
            unique=True,
            postgresql_where=text("donor_id IS NOT NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    surrogate_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("surrogates.id", ondelete="CASCADE"), nullable=True
    )
    donor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("donors.id", ondelete="CASCADE"), nullable=True
    )
    reviewed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    retained_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    decision: Mapped[str] = mapped_column(String(30), nullable=False)
    resolved_phase: Mapped[str | None] = mapped_column(String(20), nullable=True)
    reviewed_stage_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pipeline_stages.id", ondelete="SET NULL"), nullable=True
    )
    evidence_reference: Mapped[str | None] = mapped_column(String(500), nullable=True)
    record_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    reviewed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
