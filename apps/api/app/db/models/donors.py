"""Donor persistence models."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.types import EncryptedDate, EncryptedString

if TYPE_CHECKING:
    from app.db.models import Organization, PipelineStage


class Donor(Base):
    """Organization-owned egg or sperm donor."""

    __tablename__ = "donors"
    __table_args__ = (
        CheckConstraint("donor_type IN ('egg', 'sperm')", name="ck_donors_type"),
        CheckConstraint(
            "donor_number ~ '^D[0-9]{5,9}$' AND "
            "CAST(substring(donor_number from '^D([0-9]{5,9})$') AS BIGINT) >= 10001",
            name="ck_donors_number",
        ),
        CheckConstraint(
            "(owner_type IS NULL AND owner_id IS NULL) OR "
            "(owner_type IN ('user', 'queue') AND owner_id IS NOT NULL)",
            name="ck_donors_owner",
        ),
        Index("idx_donors_org_type", "organization_id", "donor_type"),
        Index("idx_donors_org_stage", "organization_id", "stage_id"),
        Index("idx_donors_org_owner", "organization_id", "owner_type", "owner_id"),
        Index("idx_donors_org_created", "organization_id", "created_at"),
        Index(
            "uq_donors_org_number",
            "organization_id",
            "donor_number",
            unique=True,
        ),
        Index(
            "uq_donors_active_email_hash",
            "organization_id",
            "email_hash",
            unique=True,
            postgresql_where=text("is_archived = FALSE"),
        ),
        Index("idx_donors_org_phone_hash", "organization_id", "phone_hash"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    donor_number: Mapped[str] = mapped_column(String(10), nullable=False)
    donor_type: Mapped[str] = mapped_column(String(10), nullable=False)

    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(EncryptedString, nullable=False)
    email_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    phone: Mapped[str | None] = mapped_column(EncryptedString, nullable=True)
    phone_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    state: Mapped[str | None] = mapped_column(String(100), nullable=True)
    education: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source: Mapped[str | None] = mapped_column(String(100), nullable=True)

    marital_status: Mapped[str | None] = mapped_column(
        String(100), nullable=True, deferred=True, deferred_group="donor_profile"
    )
    ssn: Mapped[str | None] = mapped_column(
        EncryptedString, nullable=True, deferred=True, deferred_group="donor_profile"
    )
    ssn_last4: Mapped[str | None] = mapped_column(
        String(4), nullable=True, deferred=True, deferred_group="donor_profile"
    )
    address_line1: Mapped[str | None] = mapped_column(
        EncryptedString, nullable=True, deferred=True, deferred_group="donor_profile"
    )
    address_line2: Mapped[str | None] = mapped_column(
        EncryptedString, nullable=True, deferred=True, deferred_group="donor_profile"
    )
    address_city: Mapped[str | None] = mapped_column(
        String(100), nullable=True, deferred=True, deferred_group="donor_profile"
    )
    address_state: Mapped[str | None] = mapped_column(
        String(2), nullable=True, deferred=True, deferred_group="donor_profile"
    )
    address_postal: Mapped[str | None] = mapped_column(
        String(20), nullable=True, deferred=True, deferred_group="donor_profile"
    )
    partner_name: Mapped[str | None] = mapped_column(
        String(255), nullable=True, deferred=True, deferred_group="donor_profile"
    )
    partner_date_of_birth: Mapped[date | None] = mapped_column(
        EncryptedDate, nullable=True, deferred=True, deferred_group="donor_profile"
    )
    partner_email: Mapped[str | None] = mapped_column(
        EncryptedString, nullable=True, deferred=True, deferred_group="donor_profile"
    )
    partner_phone: Mapped[str | None] = mapped_column(
        EncryptedString, nullable=True, deferred=True, deferred_group="donor_profile"
    )
    partner_ssn: Mapped[str | None] = mapped_column(
        EncryptedString, nullable=True, deferred=True, deferred_group="donor_profile"
    )
    partner_ssn_last4: Mapped[str | None] = mapped_column(
        String(4), nullable=True, deferred=True, deferred_group="donor_profile"
    )
    partner_address_line1: Mapped[str | None] = mapped_column(
        EncryptedString, nullable=True, deferred=True, deferred_group="donor_profile"
    )
    partner_address_line2: Mapped[str | None] = mapped_column(
        EncryptedString, nullable=True, deferred=True, deferred_group="donor_profile"
    )
    partner_city: Mapped[str | None] = mapped_column(
        String(100), nullable=True, deferred=True, deferred_group="donor_profile"
    )
    partner_state: Mapped[str | None] = mapped_column(
        String(2), nullable=True, deferred=True, deferred_group="donor_profile"
    )
    partner_postal: Mapped[str | None] = mapped_column(
        String(20), nullable=True, deferred=True, deferred_group="donor_profile"
    )
    date_of_birth: Mapped[date | None] = mapped_column(
        EncryptedDate, nullable=True, deferred=True, deferred_group="donor_profile"
    )
    race: Mapped[str | None] = mapped_column(
        String(100), nullable=True, deferred=True, deferred_group="donor_profile"
    )
    height_ft: Mapped[Decimal | None] = mapped_column(
        Numeric(4, 2), nullable=True, deferred=True, deferred_group="donor_profile"
    )
    weight_lb: Mapped[int | None] = mapped_column(
        Integer, nullable=True, deferred=True, deferred_group="donor_profile"
    )
    insurance_company: Mapped[str | None] = mapped_column(
        String(255), nullable=True, deferred=True, deferred_group="donor_profile"
    )
    insurance_plan_name: Mapped[str | None] = mapped_column(
        String(255), nullable=True, deferred=True, deferred_group="donor_profile"
    )
    insurance_phone: Mapped[str | None] = mapped_column(
        EncryptedString, nullable=True, deferred=True, deferred_group="donor_profile"
    )
    insurance_policy_number: Mapped[str | None] = mapped_column(
        EncryptedString, nullable=True, deferred=True, deferred_group="donor_profile"
    )
    insurance_member_id: Mapped[str | None] = mapped_column(
        EncryptedString, nullable=True, deferred=True, deferred_group="donor_profile"
    )
    insurance_group_number: Mapped[str | None] = mapped_column(
        String(100), nullable=True, deferred=True, deferred_group="donor_profile"
    )
    insurance_subscriber_name: Mapped[str | None] = mapped_column(
        EncryptedString, nullable=True, deferred=True, deferred_group="donor_profile"
    )
    insurance_subscriber_dob: Mapped[date | None] = mapped_column(
        EncryptedDate, nullable=True, deferred=True, deferred_group="donor_profile"
    )
    insurance_fax: Mapped[str | None] = mapped_column(
        EncryptedString, nullable=True, deferred=True, deferred_group="donor_profile"
    )
    clinic_name: Mapped[str | None] = mapped_column(
        String(255), nullable=True, deferred=True, deferred_group="donor_profile"
    )
    clinic_address_line1: Mapped[str | None] = mapped_column(
        EncryptedString, nullable=True, deferred=True, deferred_group="donor_profile"
    )
    clinic_address_line2: Mapped[str | None] = mapped_column(
        EncryptedString, nullable=True, deferred=True, deferred_group="donor_profile"
    )
    clinic_city: Mapped[str | None] = mapped_column(
        String(100), nullable=True, deferred=True, deferred_group="donor_profile"
    )
    clinic_state: Mapped[str | None] = mapped_column(
        String(2), nullable=True, deferred=True, deferred_group="donor_profile"
    )
    clinic_postal: Mapped[str | None] = mapped_column(
        String(20), nullable=True, deferred=True, deferred_group="donor_profile"
    )
    clinic_phone: Mapped[str | None] = mapped_column(
        EncryptedString, nullable=True, deferred=True, deferred_group="donor_profile"
    )
    clinic_email: Mapped[str | None] = mapped_column(
        EncryptedString, nullable=True, deferred=True, deferred_group="donor_profile"
    )
    clinic_fax: Mapped[str | None] = mapped_column(
        EncryptedString, nullable=True, deferred=True, deferred_group="donor_profile"
    )
    monitoring_clinic_name: Mapped[str | None] = mapped_column(
        String(255), nullable=True, deferred=True, deferred_group="donor_profile"
    )
    monitoring_clinic_address_line1: Mapped[str | None] = mapped_column(
        EncryptedString, nullable=True, deferred=True, deferred_group="donor_profile"
    )
    monitoring_clinic_address_line2: Mapped[str | None] = mapped_column(
        EncryptedString, nullable=True, deferred=True, deferred_group="donor_profile"
    )
    monitoring_clinic_city: Mapped[str | None] = mapped_column(
        String(100), nullable=True, deferred=True, deferred_group="donor_profile"
    )
    monitoring_clinic_state: Mapped[str | None] = mapped_column(
        String(2), nullable=True, deferred=True, deferred_group="donor_profile"
    )
    monitoring_clinic_postal: Mapped[str | None] = mapped_column(
        String(20), nullable=True, deferred=True, deferred_group="donor_profile"
    )
    monitoring_clinic_phone: Mapped[str | None] = mapped_column(
        EncryptedString, nullable=True, deferred=True, deferred_group="donor_profile"
    )
    monitoring_clinic_email: Mapped[str | None] = mapped_column(
        EncryptedString, nullable=True, deferred=True, deferred_group="donor_profile"
    )
    monitoring_clinic_fax: Mapped[str | None] = mapped_column(
        EncryptedString, nullable=True, deferred=True, deferred_group="donor_profile"
    )
    ob_provider_name: Mapped[str | None] = mapped_column(
        String(255), nullable=True, deferred=True, deferred_group="donor_profile"
    )
    ob_clinic_name: Mapped[str | None] = mapped_column(
        String(255), nullable=True, deferred=True, deferred_group="donor_profile"
    )
    ob_address_line1: Mapped[str | None] = mapped_column(
        EncryptedString, nullable=True, deferred=True, deferred_group="donor_profile"
    )
    ob_address_line2: Mapped[str | None] = mapped_column(
        EncryptedString, nullable=True, deferred=True, deferred_group="donor_profile"
    )
    ob_city: Mapped[str | None] = mapped_column(
        String(100), nullable=True, deferred=True, deferred_group="donor_profile"
    )
    ob_state: Mapped[str | None] = mapped_column(
        String(2), nullable=True, deferred=True, deferred_group="donor_profile"
    )
    ob_postal: Mapped[str | None] = mapped_column(
        String(20), nullable=True, deferred=True, deferred_group="donor_profile"
    )
    ob_phone: Mapped[str | None] = mapped_column(
        EncryptedString, nullable=True, deferred=True, deferred_group="donor_profile"
    )
    ob_email: Mapped[str | None] = mapped_column(
        EncryptedString, nullable=True, deferred=True, deferred_group="donor_profile"
    )
    ob_fax: Mapped[str | None] = mapped_column(
        EncryptedString, nullable=True, deferred=True, deferred_group="donor_profile"
    )
    delivery_hospital_name: Mapped[str | None] = mapped_column(
        String(255), nullable=True, deferred=True, deferred_group="donor_profile"
    )
    delivery_hospital_address_line1: Mapped[str | None] = mapped_column(
        EncryptedString, nullable=True, deferred=True, deferred_group="donor_profile"
    )
    delivery_hospital_address_line2: Mapped[str | None] = mapped_column(
        EncryptedString, nullable=True, deferred=True, deferred_group="donor_profile"
    )
    delivery_hospital_city: Mapped[str | None] = mapped_column(
        String(100), nullable=True, deferred=True, deferred_group="donor_profile"
    )
    delivery_hospital_state: Mapped[str | None] = mapped_column(
        String(2), nullable=True, deferred=True, deferred_group="donor_profile"
    )
    delivery_hospital_postal: Mapped[str | None] = mapped_column(
        String(20), nullable=True, deferred=True, deferred_group="donor_profile"
    )
    delivery_hospital_phone: Mapped[str | None] = mapped_column(
        EncryptedString, nullable=True, deferred=True, deferred_group="donor_profile"
    )
    delivery_hospital_email: Mapped[str | None] = mapped_column(
        EncryptedString, nullable=True, deferred=True, deferred_group="donor_profile"
    )
    delivery_hospital_fax: Mapped[str | None] = mapped_column(
        EncryptedString, nullable=True, deferred=True, deferred_group="donor_profile"
    )
    pcp_provider_name: Mapped[str | None] = mapped_column(
        String(255), nullable=True, deferred=True, deferred_group="donor_profile"
    )
    pcp_name: Mapped[str | None] = mapped_column(
        String(255), nullable=True, deferred=True, deferred_group="donor_profile"
    )
    pcp_address_line1: Mapped[str | None] = mapped_column(
        EncryptedString, nullable=True, deferred=True, deferred_group="donor_profile"
    )
    pcp_address_line2: Mapped[str | None] = mapped_column(
        EncryptedString, nullable=True, deferred=True, deferred_group="donor_profile"
    )
    pcp_city: Mapped[str | None] = mapped_column(
        String(100), nullable=True, deferred=True, deferred_group="donor_profile"
    )
    pcp_state: Mapped[str | None] = mapped_column(
        String(2), nullable=True, deferred=True, deferred_group="donor_profile"
    )
    pcp_postal: Mapped[str | None] = mapped_column(
        String(20), nullable=True, deferred=True, deferred_group="donor_profile"
    )
    pcp_phone: Mapped[str | None] = mapped_column(
        EncryptedString, nullable=True, deferred=True, deferred_group="donor_profile"
    )
    pcp_fax: Mapped[str | None] = mapped_column(
        EncryptedString, nullable=True, deferred=True, deferred_group="donor_profile"
    )
    pcp_email: Mapped[str | None] = mapped_column(
        EncryptedString, nullable=True, deferred=True, deferred_group="donor_profile"
    )
    lab_clinic_name: Mapped[str | None] = mapped_column(
        String(255), nullable=True, deferred=True, deferred_group="donor_profile"
    )
    lab_clinic_address_line1: Mapped[str | None] = mapped_column(
        EncryptedString, nullable=True, deferred=True, deferred_group="donor_profile"
    )
    lab_clinic_address_line2: Mapped[str | None] = mapped_column(
        EncryptedString, nullable=True, deferred=True, deferred_group="donor_profile"
    )
    lab_clinic_city: Mapped[str | None] = mapped_column(
        String(100), nullable=True, deferred=True, deferred_group="donor_profile"
    )
    lab_clinic_state: Mapped[str | None] = mapped_column(
        String(2), nullable=True, deferred=True, deferred_group="donor_profile"
    )
    lab_clinic_postal: Mapped[str | None] = mapped_column(
        String(20), nullable=True, deferred=True, deferred_group="donor_profile"
    )
    lab_clinic_phone: Mapped[str | None] = mapped_column(
        EncryptedString, nullable=True, deferred=True, deferred_group="donor_profile"
    )
    lab_clinic_fax: Mapped[str | None] = mapped_column(
        EncryptedString, nullable=True, deferred=True, deferred_group="donor_profile"
    )
    lab_clinic_email: Mapped[str | None] = mapped_column(
        EncryptedString, nullable=True, deferred=True, deferred_group="donor_profile"
    )
    college: Mapped[str | None] = mapped_column(
        EncryptedString, nullable=True, deferred=True, deferred_group="donor_profile"
    )
    nicotine: Mapped[str | None] = mapped_column(
        EncryptedString, nullable=True, deferred=True, deferred_group="donor_profile"
    )
    cannabis: Mapped[str | None] = mapped_column(
        EncryptedString, nullable=True, deferred=True, deferred_group="donor_profile"
    )
    infectious_disease: Mapped[str | None] = mapped_column(
        EncryptedString, nullable=True, deferred=True, deferred_group="donor_profile"
    )
    previous_donation: Mapped[str | None] = mapped_column(
        EncryptedString, nullable=True, deferred=True, deferred_group="donor_profile"
    )
    profile_updated_fields: Mapped[list[str]] = mapped_column(
        JSONB, server_default=text("'[]'::jsonb"), nullable=False
    )

    owner_type: Mapped[str | None] = mapped_column(String(10), nullable=True)
    owner_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)

    stage_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("pipeline_stages.id", ondelete="RESTRICT"),
        nullable=False,
    )
    profile_photo_attachment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("attachments.id", ondelete="SET NULL", use_alter=True),
        nullable=True,
    )

    is_archived: Mapped[bool] = mapped_column(Boolean, server_default=text("FALSE"), nullable=False)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    organization: Mapped[Organization] = relationship()
    stage: Mapped[PipelineStage] = relationship(foreign_keys=[stage_id])
    status_history: Mapped[list[DonorStatusHistory]] = relationship(
        back_populates="donor",
        cascade="all, delete-orphan",
        order_by="DonorStatusHistory.recorded_at.desc()",
    )

    @property
    def pipeline_entity_type(self) -> str:
        return f"{self.donor_type}_donor"

    @property
    def stage_key(self) -> str:
        return self.stage.stage_key

    @property
    def stage_slug(self) -> str:
        return self.stage.slug

    @property
    def status(self) -> str:
        return self.stage_key

    @property
    def status_label(self) -> str:
        return self.stage.label


class DonorStatusHistory(Base):
    """Append-only donor stage history."""

    __tablename__ = "donor_status_history"
    __table_args__ = (
        Index("idx_donor_history_donor_recorded", "donor_id", "recorded_at"),
        Index("idx_donor_history_org_recorded", "organization_id", "recorded_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    donor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("donors.id", ondelete="CASCADE"), nullable=False
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    changed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    old_stage_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pipeline_stages.id", ondelete="SET NULL"), nullable=True
    )
    new_stage_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pipeline_stages.id", ondelete="SET NULL"), nullable=True
    )
    old_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    new_status: Mapped[str] = mapped_column(String(50), nullable=False)
    old_label_snapshot: Mapped[str | None] = mapped_column(String(100), nullable=True)
    new_label_snapshot: Mapped[str] = mapped_column(String(100), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    effective_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
    requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_undo: Mapped[bool] = mapped_column(Boolean, server_default=text("false"), nullable=False)
    request_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("status_change_requests.id", ondelete="SET NULL"),
        nullable=True,
    )

    donor: Mapped[Donor] = relationship(back_populates="status_history")
