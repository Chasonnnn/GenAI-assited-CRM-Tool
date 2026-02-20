"""SQLAlchemy ORM models."""

from __future__ import annotations

from typing import TYPE_CHECKING

import uuid
from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, Index, Integer, String, text
from sqlalchemy.dialects.postgresql import TSVECTOR, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


if TYPE_CHECKING:
    from app.db.models import EmailLogAttachment, Organization, Surrogate, User


class Attachment(Base):
    """
    File attachments for cases (and future: intended parents).

    Security features:
    - SHA-256 checksum for integrity verification
    - Virus scan status with quarantine until clean
    - Soft-delete with audit trail
    - Access control via case ownership
    """

    __tablename__ = "attachments"
    __table_args__ = (
        Index("idx_attachments_surrogate", "surrogate_id"),
        Index("idx_attachments_org_scan", "organization_id", "scan_status"),
        Index(
            "idx_attachments_active",
            "surrogate_id",
            postgresql_where=text("deleted_at IS NULL AND quarantined = FALSE"),
        ),
        Index("idx_attachments_intended_parent", "intended_parent_id"),
        # GIN index for full-text search
        Index(
            "ix_attachments_search_vector",
            "search_vector",
            postgresql_using="gin",
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
    surrogate_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("surrogates.id", ondelete="CASCADE"), nullable=True
    )
    intended_parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("intended_parents.id", ondelete="CASCADE"),
        nullable=True,
    )
    uploaded_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # File metadata
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False)

    # Security / Virus scan (infected or failed scans are quarantined)
    scan_status: Mapped[str] = mapped_column(
        String(20), server_default=text("'pending'"), nullable=False
    )  # pending | clean | infected | error
    scanned_at: Mapped[datetime | None] = mapped_column(nullable=True)
    quarantined: Mapped[bool] = mapped_column(Boolean, server_default=text("FALSE"), nullable=False)

    # Soft-delete
    deleted_at: Mapped[datetime | None] = mapped_column(nullable=True)
    deleted_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(server_default=text("now()"), nullable=False)

    # Full-text search vector (managed by trigger)
    search_vector = mapped_column(TSVECTOR, nullable=True)

    # Relationships
    organization: Mapped["Organization"] = relationship()
    surrogate: Mapped["Surrogate"] = relationship()
    uploaded_by: Mapped["User | None"] = relationship(foreign_keys=[uploaded_by_user_id])
    deleted_by: Mapped["User | None"] = relationship(foreign_keys=[deleted_by_user_id])
    email_log_links: Mapped[list["EmailLogAttachment"]] = relationship(back_populates="attachment")
