"""SQLAlchemy ORM models."""

from __future__ import annotations

from typing import TYPE_CHECKING

import uuid
from datetime import datetime

from sqlalchemy import (
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.enums import (
    DEFAULT_JOB_STATUS,
)

if TYPE_CHECKING:
    from app.db.models import Organization, User


class Job(Base):
    """
    Background job for async processing.

    Used for: email sending, scheduled reminders, webhook retries.
    Worker polls for pending jobs and processes them.
    """

    __tablename__ = "jobs"
    __table_args__ = (
        Index(
            "idx_jobs_pending",
            "status",
            "run_at",
            postgresql_where=text("status = 'pending'"),
        ),
        Index("idx_jobs_org", "organization_id", "created_at"),
        Index(
            "uq_job_idempotency",
            "idempotency_key",
            unique=True,
            postgresql_where=text("idempotency_key IS NOT NULL"),
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

    job_type: Mapped[str] = mapped_column(String(50), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    run_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), server_default=text(f"'{DEFAULT_JOB_STATUS.value}'"), nullable=False
    )
    attempts: Mapped[int] = mapped_column(Integer, server_default=text("0"), nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, server_default=text("3"), nullable=False)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)

    # Idempotency key for deduplication (unique constraint in migration)
    idempotency_key: Mapped[str | None] = mapped_column(String(255), nullable=True)


class ExportJob(Base):
    """
    Asynchronous export job for compliance/audit data.

    Files are stored in external storage (S3 or local dev) and accessed via
    short-lived signed URLs generated on demand.
    """

    __tablename__ = "export_jobs"
    __table_args__ = (
        Index("idx_export_jobs_org_created", "organization_id", "created_at"),
        Index("idx_export_jobs_org_status", "organization_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    status: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # pending, processing, completed, failed
    export_type: Mapped[str] = mapped_column(String(30), nullable=False)  # audit, cases, analytics
    format: Mapped[str] = mapped_column(String(10), nullable=False)  # csv, json
    redact_mode: Mapped[str] = mapped_column(String(10), nullable=False)  # redacted, full

    date_range_start: Mapped[datetime] = mapped_column(nullable=False)
    date_range_end: Mapped[datetime] = mapped_column(nullable=False)

    record_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    file_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    acknowledgment: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)

    # Relationships
    organization: Mapped["Organization"] = relationship()
    created_by: Mapped["User | None"] = relationship()
