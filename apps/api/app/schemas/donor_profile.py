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
    insurance_company: str | None = Field(None, max_length=255)
    insurance_plan_name: str | None = Field(None, max_length=255)
    insurance_phone: str | None = None
    insurance_policy_number: str | None = None
    insurance_member_id: str | None = None
    insurance_group_number: str | None = Field(None, max_length=100)
    insurance_subscriber_name: str | None = None
    insurance_subscriber_dob: date | None = None
    insurance_fax: str | None = None
    clinic_name: str | None = Field(None, max_length=255)
    clinic_address_line1: str | None = None
    clinic_address_line2: str | None = None
    clinic_city: str | None = Field(None, max_length=100)
    clinic_state: str | None = None
    clinic_postal: str | None = Field(None, max_length=20)
    clinic_phone: str | None = None
    clinic_email: EmailStr | None = None
    clinic_fax: str | None = None
    monitoring_clinic_name: str | None = Field(None, max_length=255)
    monitoring_clinic_address_line1: str | None = None
    monitoring_clinic_address_line2: str | None = None
    monitoring_clinic_city: str | None = Field(None, max_length=100)
    monitoring_clinic_state: str | None = None
    monitoring_clinic_postal: str | None = Field(None, max_length=20)
    monitoring_clinic_phone: str | None = None
    monitoring_clinic_email: EmailStr | None = None
    monitoring_clinic_fax: str | None = None
    ob_provider_name: str | None = Field(None, max_length=255)
    ob_clinic_name: str | None = Field(None, max_length=255)
    ob_address_line1: str | None = None
    ob_address_line2: str | None = None
    ob_city: str | None = Field(None, max_length=100)
    ob_state: str | None = None
    ob_postal: str | None = Field(None, max_length=20)
    ob_phone: str | None = None
    ob_email: EmailStr | None = None
    ob_fax: str | None = None
    delivery_hospital_name: str | None = Field(None, max_length=255)
    delivery_hospital_address_line1: str | None = None
    delivery_hospital_address_line2: str | None = None
    delivery_hospital_city: str | None = Field(None, max_length=100)
    delivery_hospital_state: str | None = None
    delivery_hospital_postal: str | None = Field(None, max_length=20)
    delivery_hospital_phone: str | None = None
    delivery_hospital_email: EmailStr | None = None
    delivery_hospital_fax: str | None = None
    pcp_provider_name: str | None = Field(None, max_length=255)
    pcp_name: str | None = Field(None, max_length=255)
    pcp_address_line1: str | None = None
    pcp_address_line2: str | None = None
    pcp_city: str | None = Field(None, max_length=100)
    pcp_state: str | None = None
    pcp_postal: str | None = Field(None, max_length=20)
    pcp_phone: str | None = None
    pcp_fax: str | None = None
    pcp_email: EmailStr | None = None
    lab_clinic_name: str | None = Field(None, max_length=255)
    lab_clinic_address_line1: str | None = None
    lab_clinic_address_line2: str | None = None
    lab_clinic_city: str | None = Field(None, max_length=100)
    lab_clinic_state: str | None = None
    lab_clinic_postal: str | None = Field(None, max_length=20)
    lab_clinic_phone: str | None = None
    lab_clinic_fax: str | None = None
    lab_clinic_email: EmailStr | None = None
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
        "insurance_phone",
        "insurance_fax",
        "clinic_phone",
        "clinic_fax",
        "monitoring_clinic_phone",
        "monitoring_clinic_fax",
        "ob_phone",
        "ob_fax",
        "delivery_hospital_phone",
        "delivery_hospital_fax",
        "pcp_phone",
        "pcp_fax",
        "lab_clinic_phone",
        "lab_clinic_fax",
    )
    @classmethod
    def validate_phone(cls, value: str | None) -> str | None:
        return normalize_phone(value) if value else None

    @field_validator(
        "address_state",
        "partner_state",
        "clinic_state",
        "monitoring_clinic_state",
        "ob_state",
        "delivery_hospital_state",
        "pcp_state",
        "lab_clinic_state",
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
