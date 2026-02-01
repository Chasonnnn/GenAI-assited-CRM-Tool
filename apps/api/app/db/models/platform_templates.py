"""Platform-level templates managed by ops console."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, Integer, String, Text, TIMESTAMP, text, ForeignKey, Index
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class PlatformEmailTemplate(Base):
    """Platform-managed email templates with draft + published snapshots."""

    __tablename__ = "platform_email_templates"
    __table_args__ = (Index("idx_platform_email_templates_status", "status"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )

    # Draft fields
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    subject: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    from_email: Mapped[str | None] = mapped_column(String(200), nullable=True)
    category: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Published snapshot
    published_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    published_subject: Mapped[str | None] = mapped_column(String(200), nullable=True)
    published_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    published_from_email: Mapped[str | None] = mapped_column(String(200), nullable=True)
    published_category: Mapped[str | None] = mapped_column(String(50), nullable=True)

    status: Mapped[str] = mapped_column(String(20), server_default=text("'draft'"), nullable=False)
    current_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    published_version: Mapped[int] = mapped_column(
        Integer, server_default=text("0"), nullable=False
    )
    is_published_globally: Mapped[bool] = mapped_column(
        Boolean, server_default=text("false"), nullable=False
    )
    published_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()"), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=text("now()"),
        onupdate=text("now()"),
        nullable=False,
    )


class PlatformEmailTemplateTarget(Base):
    """Target orgs for platform email templates when not published globally."""

    __tablename__ = "platform_email_template_targets"
    __table_args__ = (Index("idx_platform_email_template_targets_org", "organization_id"),)

    template_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("platform_email_templates.id", ondelete="CASCADE"),
        primary_key=True,
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        primary_key=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()"), nullable=False
    )

    template: Mapped["PlatformEmailTemplate"] = relationship()


class PlatformFormTemplate(Base):
    """Platform-managed form templates with draft + published snapshots."""

    __tablename__ = "platform_form_templates"
    __table_args__ = (Index("idx_platform_form_templates_status", "status"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )

    # Draft fields
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    schema_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    settings_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Published snapshot
    published_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    published_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    published_schema_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    published_settings_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    status: Mapped[str] = mapped_column(String(20), server_default=text("'draft'"), nullable=False)
    current_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    published_version: Mapped[int] = mapped_column(
        Integer, server_default=text("0"), nullable=False
    )
    is_published_globally: Mapped[bool] = mapped_column(
        Boolean, server_default=text("false"), nullable=False
    )
    published_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()"), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=text("now()"),
        onupdate=text("now()"),
        nullable=False,
    )


class PlatformFormTemplateTarget(Base):
    """Target orgs for platform form templates when not published globally."""

    __tablename__ = "platform_form_template_targets"
    __table_args__ = (Index("idx_platform_form_template_targets_org", "organization_id"),)

    template_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("platform_form_templates.id", ondelete="CASCADE"),
        primary_key=True,
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        primary_key=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()"), nullable=False
    )

    template: Mapped["PlatformFormTemplate"] = relationship()
