"""Donor profile contracts using the same field validation as surrogate profiles."""

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.schemas.surrogate import MaritalStatus, normalize_ssn
from app.utils.height import canonicalize_height_ft
from app.utils.normalization import normalize_phone, normalize_state


class DonorProfileFields(BaseModel):
    model_config = ConfigDict(from_attributes=True, str_strip_whitespace=True)

    marital_status: MaritalStatus | None = None
    address_line1: str | None = None
    address_line2: str | None = None
    address_city: str | None = Field(None, max_length=100)
    address_state: str | None = None
    address_postal: str | None = Field(None, max_length=20)
    partner_name: str | None = Field(None, max_length=255)
    partner_date_of_birth: date | None = None
    partner_email: EmailStr | None = None
    partner_phone: str | None = None
    partner_address_line1: str | None = None
    partner_address_line2: str | None = None
    partner_city: str | None = Field(None, max_length=100)
    partner_state: str | None = None
    partner_postal: str | None = Field(None, max_length=20)
    date_of_birth: date | None = None
    race: str | None = Field(None, max_length=100)
    height_ft: Decimal | None = Field(None, ge=0, le=10)
    weight_lb: int | None = Field(None, ge=0, le=1000)
    education: str | None = Field(None, max_length=255)
    college: str | None = Field(None, max_length=255)
    nicotine: str | None = Field(None, max_length=255)
    cannabis: str | None = Field(None, max_length=255)
    infectious_disease: str | None = Field(None, max_length=255)
    previous_donation: str | None = Field(None, max_length=255)

    @field_validator("height_ft")
    @classmethod
    def validate_height(cls, value: Decimal | None) -> Decimal | None:
        return canonicalize_height_ft(value)

    @field_validator(
        "partner_phone",
    )
    @classmethod
    def validate_phone(cls, value: str | None) -> str | None:
        return normalize_phone(value) if value else None

    @field_validator(
        "address_state",
        "partner_state",
    )
    @classmethod
    def validate_state(cls, value: str | None) -> str | None:
        return normalize_state(value) if value else None


class DonorProfileUpdate(DonorProfileFields):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    ssn: str | None = None
    partner_ssn: str | None = None

    @field_validator("ssn", "partner_ssn")
    @classmethod
    def validate_ssn(cls, value: str | None) -> str | None:
        return normalize_ssn(value)


class DonorChecklistOption(BaseModel):
    value: str
    label: str


class DonorChecklistItem(BaseModel):
    key: str
    label: str
    question: str
    value: str | None
    options: list[DonorChecklistOption] = Field(default_factory=list)


class DonorProfileRead(DonorProfileFields):
    ssn_masked: str | None = None
    partner_ssn_masked: str | None = None
    eligibility_checklist: list[DonorChecklistItem] = Field(default_factory=list)


class DonorSensitiveInfoRead(BaseModel):
    ssn: str | None = None
    partner_ssn: str | None = None
