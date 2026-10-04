"""Schemas for dated medical and insurance records."""

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.utils.normalization import normalize_phone, normalize_state

MedicalRecordSection = Literal[
    "insurance",
    "pcp",
    "lab_clinic",
    "clinic",
    "monitoring_clinic",
    "ob",
    "delivery_hospital",
]
MedicalRecordSource = Literal["manual", "import", "form", "restore"]
MedicalRecordStatus = Literal["current", "past", "scheduled"]

CONTACT_FIELDS = (
    "name",
    "address_line1",
    "address_line2",
    "city",
    "state",
    "postal",
    "phone",
    "fax",
    "email",
)
SECTION_FIELDS: dict[str, tuple[str, ...]] = {
    "insurance": (
        "name",
        "plan_name",
        "policy_number",
        "member_id",
        "group_number",
        "subscriber_name",
        "subscriber_dob",
        "phone",
        "fax",
    ),
    "pcp": ("provider_name", *CONTACT_FIELDS),
    "lab_clinic": CONTACT_FIELDS,
    "clinic": CONTACT_FIELDS,
    "monitoring_clinic": CONTACT_FIELDS,
    "ob": ("provider_name", *CONTACT_FIELDS),
    "delivery_hospital": CONTACT_FIELDS,
}
# Corrections to these fields record that they changed, never their values.
REDACTED_FIELDS = frozenset({"member_id", "policy_number", "subscriber_dob"})
RECORD_FIELDS = tuple(dict.fromkeys(f for fields in SECTION_FIELDS.values() for f in fields))


def _legacy_names(section: str, prefix: str) -> dict[str, tuple[str, str]]:
    return {f"{prefix}_{field}": (section, field) for field in SECTION_FIELDS[section]}


# Former flat surrogate/donor column names that forms may still map answers to,
# keyed to (section, record field). Insurance and OB used their own naming.
LEGACY_MEDICAL_FIELDS: dict[str, tuple[str, str]] = {
    **{
        f"insurance_{'company' if field == 'name' else field}": ("insurance", field)
        for field in SECTION_FIELDS["insurance"]
    },
    **_legacy_names("pcp", "pcp"),
    **_legacy_names("lab_clinic", "lab_clinic"),
    **_legacy_names("clinic", "clinic"),
    **_legacy_names("monitoring_clinic", "monitoring_clinic"),
    **{
        ("ob_clinic_name" if field == "name" else f"ob_{field}"): ("ob", field)
        for field in SECTION_FIELDS["ob"]
    },
    **_legacy_names("delivery_hospital", "delivery_hospital"),
}


class MedicalRecordFields(BaseModel):
    """Editable record fields. Blank strings clear a field."""

    model_config = ConfigDict(extra="forbid")

    provider_name: str | None = Field(default=None, max_length=255)
    name: str | None = Field(default=None, max_length=255)
    address_line1: str | None = Field(default=None, max_length=255)
    address_line2: str | None = Field(default=None, max_length=255)
    city: str | None = Field(default=None, max_length=100)
    state: str | None = None
    postal: str | None = Field(default=None, max_length=20)
    phone: str | None = None
    fax: str | None = None
    email: EmailStr | None = None
    plan_name: str | None = Field(default=None, max_length=255)
    policy_number: str | None = Field(default=None, max_length=100)
    member_id: str | None = Field(default=None, max_length=100)
    group_number: str | None = Field(default=None, max_length=100)
    subscriber_name: str | None = Field(default=None, max_length=255)
    subscriber_dob: date | None = None

    @field_validator("*", mode="before")
    @classmethod
    def blank_to_none(cls, value: object) -> object:
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value

    @field_validator("phone", "fax")
    @classmethod
    def validate_phone(cls, value: str | None) -> str | None:
        return normalize_phone(value) if value else None

    @field_validator("state")
    @classmethod
    def validate_state(cls, value: str | None) -> str | None:
        return normalize_state(value) if value else None

    def provided_fields(self) -> dict[str, object]:
        return {field: getattr(self, field) for field in self.model_fields_set}


def _check_section_fields(section: str, fields: set[str]) -> None:
    unknown = sorted(fields - set(SECTION_FIELDS[section]))
    if unknown:
        raise ValueError(f"Fields not used by {section}: {', '.join(unknown)}")


class MedicalRecordCreate(MedicalRecordFields):
    section: MedicalRecordSection
    effective_date: date
    idempotency_key: str | None = Field(default=None, min_length=8, max_length=100)

    @model_validator(mode="after")
    def validate_section(self) -> MedicalRecordCreate:
        provided = self.model_fields_set - {"section", "effective_date", "idempotency_key"}
        _check_section_fields(self.section, provided)
        if not (self.name or self.provider_name):
            raise ValueError("Enter a name")
        return self


class MedicalRecordUpdate(MedicalRecordFields):
    expected_revision: int = Field(ge=1)

    @model_validator(mode="after")
    def validate_fields(self) -> MedicalRecordUpdate:
        if not self.model_fields_set - {"expected_revision"}:
            raise ValueError("No fields to update")
        return self

    def provided_fields(self) -> dict[str, object]:
        fields = super().provided_fields()
        fields.pop("expected_revision", None)
        return fields


class MedicalRecordArchive(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_revision: int = Field(ge=1)


class MedicalRecordRestore(BaseModel):
    model_config = ConfigDict(extra="forbid")

    idempotency_key: str | None = Field(default=None, min_length=8, max_length=100)


class MedicalRecordCorrectionRead(BaseModel):
    id: UUID
    field: str
    old_value: str | None
    new_value: str | None
    redacted: bool
    source: MedicalRecordSource
    corrected_by_name: str | None
    corrected_at: datetime


class MedicalRecordRead(BaseModel):
    id: UUID
    section: MedicalRecordSection
    status: MedicalRecordStatus
    effective_date: date | None
    end_date: date | None
    source: MedicalRecordSource
    provider_name: str | None
    name: str | None
    address_line1: str | None
    address_line2: str | None
    city: str | None
    state: str | None
    postal: str | None
    phone: str | None
    fax: str | None
    email: str | None
    plan_name: str | None
    policy_number: str | None
    member_id: str | None
    group_number: str | None
    subscriber_name: str | None
    subscriber_dob: date | None
    archived_on: date | None
    archived_by_name: str | None
    revision: int
    created_by_name: str | None
    created_at: datetime
    corrections: list[MedicalRecordCorrectionRead]


class MedicalRecordListResponse(BaseModel):
    today: date
    records: list[MedicalRecordRead]
