"""Dated medical and insurance records for surrogates and donors."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    TIMESTAMP,
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Integer,
    String,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.types import EncryptedDate, EncryptedString

MEDICAL_RECORD_SECTIONS = (
    "insurance",
    "pcp",
    "lab_clinic",
    "clinic",
    "monitoring_clinic",
    "ob",
    "delivery_hospital",
)
MEDICAL_RECORD_SOURCES = ("manual", "import", "form", "restore")


class MedicalRecord(Base):
    """One dated state of a medical or insurance section.

    A section's current record is the latest record whose effective date is
    unknown or not in the future, unless that record was archived. Effective
    date NULL marks a record imported from the former flat profile columns.
    """

    __tablename__ = "medical_records"
    __table_args__ = (
        CheckConstraint(
            "num_nonnulls(surrogate_id, donor_id) = 1",
            name="ck_medical_records_exactly_one_owner",
        ),
        CheckConstraint(
            "section IN ('insurance', 'pcp', 'lab_clinic', 'clinic', "
            "'monitoring_clinic', 'ob', 'delivery_hospital')",
            name="ck_medical_records_section",
        ),
        CheckConstraint(
            "source IN ('manual', 'import', 'form', 'restore')",
            name="ck_medical_records_source",
        ),
        CheckConstraint("revision >= 1", name="ck_medical_records_revision_positive"),
        Index(
            "idx_medical_records_surrogate_section",
            "organization_id",
            "surrogate_id",
            "section",
        ),
        Index("idx_medical_records_donor_section", "organization_id", "donor_id", "section"),
        Index(
            "uq_medical_records_idempotency",
            "organization_id",
            "idempotency_key",
            unique=True,
            postgresql_where=text("idempotency_key IS NOT NULL"),
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
    section: Mapped[str] = mapped_column(String(32), nullable=False)
    effective_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    source: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'manual'"))

    # Contact fields shared by every section. Insurance stores the company in `name`.
    provider_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    address_line1: Mapped[str | None] = mapped_column(EncryptedString, nullable=True)
    address_line2: Mapped[str | None] = mapped_column(EncryptedString, nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    state: Mapped[str | None] = mapped_column(String(2), nullable=True)
    postal: Mapped[str | None] = mapped_column(String(20), nullable=True)
    phone: Mapped[str | None] = mapped_column(EncryptedString, nullable=True)
    fax: Mapped[str | None] = mapped_column(EncryptedString, nullable=True)
    email: Mapped[str | None] = mapped_column(EncryptedString, nullable=True)

    # Insurance-only fields.
    plan_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    policy_number: Mapped[str | None] = mapped_column(EncryptedString, nullable=True)
    member_id: Mapped[str | None] = mapped_column(EncryptedString, nullable=True)
    group_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    subscriber_name: Mapped[str | None] = mapped_column(EncryptedString, nullable=True)
    subscriber_dob: Mapped[date | None] = mapped_column(EncryptedDate, nullable=True)

    archived_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    archived_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    archived_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    revision: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    idempotency_key: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()"), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()"), nullable=False
    )

    corrections: Mapped[list[MedicalRecordCorrection]] = relationship(
        back_populates="record",
        cascade="all, delete-orphan",
        order_by="MedicalRecordCorrection.corrected_at",
        passive_deletes=True,
    )


class MedicalRecordCorrection(Base):
    """One field correction within a medical record.

    Values are encrypted. Redacted corrections (member ID, policy number,
    subscriber date of birth) store no values.
    """

    __tablename__ = "medical_record_corrections"
    __table_args__ = (
        Index("idx_medical_record_corrections_record", "record_id", "corrected_at"),
        Index("idx_medical_record_corrections_org", "organization_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    record_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("medical_records.id", ondelete="CASCADE"), nullable=False
    )
    field: Mapped[str] = mapped_column(String(64), nullable=False)
    old_value: Mapped[str | None] = mapped_column(EncryptedString, nullable=True)
    new_value: Mapped[str | None] = mapped_column(EncryptedString, nullable=True)
    redacted: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    source: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'manual'"))
    corrected_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    corrected_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()"), nullable=False
    )

    record: Mapped[MedicalRecord] = relationship(back_populates="corrections")
