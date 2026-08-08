"""API schemas for organization-level Twilio messaging configuration."""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints, field_validator

from app.utils.normalization import normalize_phone

MessagingPurpose = Literal["operational", "promotional"]
TwilioReadinessStatus = Literal[
    "ready",
    "degraded",
    "blocked",
    "not_configured",
    "action_required",
    "unknown",
]
TwilioAccountSid = Annotated[str, StringConstraints(pattern=r"^AC[0-9a-fA-F]{32}$")]
TwilioApiKeySid = Annotated[str, StringConstraints(pattern=r"^SK[0-9a-fA-F]{32}$")]
TwilioMessagingServiceSid = Annotated[str, StringConstraints(pattern=r"^MG[0-9a-fA-F]{32}$")]


class TwilioRouteResponse(BaseModel):
    purpose: MessagingPurpose
    enabled: bool
    messaging_service_sid_masked: str | None
    sender_phone_masked: str | None
    a2p_status: str
    advanced_opt_out_status: str
    consent_management_status: str
    capability_evidence: dict = Field(default_factory=dict)
    webhook_id: str
    inbound_webhook_url: str
    status_callback_url: str


class TwilioSettingsResponse(BaseModel):
    enabled: bool
    account_sid_masked: str | None
    api_key_sid_masked: str | None
    api_secret_configured: bool
    auth_token_configured: bool
    legal_messaging_brand: str | None
    operational_disclosure: str | None
    promotional_disclosure: str | None
    sms_terms_url: str | None
    privacy_policy_url: str | None
    support_contact: str | None
    expected_frequency: str | None
    counsel_approved_at: str | None
    compliance_toolkit_enabled: bool
    twilio_edition: str | None
    baa_verified_at: str | None
    compliance_approved_at: str | None
    phi_enabled: bool
    current_version: int
    routes: dict[MessagingPurpose, TwilioRouteResponse]


class TwilioRouteUpdate(BaseModel):
    enabled: bool | None = None
    messaging_service_sid: TwilioMessagingServiceSid | None = None
    sender_phone_e164: str | None = None
    a2p_status: Literal["unconfigured", "pending", "approved", "rejected"] | None = None
    advanced_opt_out_status: Literal["unconfigured", "enabled", "verified"] | None = None
    consent_management_status: Literal["unknown", "available", "unavailable"] | None = None
    capability_evidence: dict | None = None

    @field_validator("messaging_service_sid", mode="before")
    @classmethod
    def blank_service_sid_clears(cls, value: str | None) -> str | None:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("sender_phone_e164")
    @classmethod
    def normalize_sender_phone(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        return normalize_phone(value)


class TwilioSettingsUpdate(BaseModel):
    expected_version: int = Field(ge=1)
    enabled: bool | None = None
    account_sid: TwilioAccountSid | None = None
    api_key_sid: TwilioApiKeySid | None = None
    api_secret: str | None = Field(default=None, max_length=255)
    auth_token: str | None = Field(default=None, max_length=255)
    legal_messaging_brand: str | None = Field(default=None, max_length=160)
    operational_disclosure: str | None = Field(default=None, max_length=4000)
    promotional_disclosure: str | None = Field(default=None, max_length=4000)
    sms_terms_url: str | None = Field(default=None, max_length=1000)
    privacy_policy_url: str | None = Field(default=None, max_length=1000)
    support_contact: str | None = Field(default=None, max_length=255)
    expected_frequency: str | None = Field(default=None, max_length=255)
    counsel_approved_at: datetime | None = None
    compliance_toolkit_enabled: bool | None = None
    twilio_edition: str | None = Field(default=None, max_length=40)
    baa_verified_at: datetime | None = None
    compliance_approved_at: datetime | None = None
    phi_enabled: bool | None = None
    routes: dict[MessagingPurpose, TwilioRouteUpdate] | None = None

    @field_validator("account_sid", "api_key_sid", mode="before")
    @classmethod
    def blank_sid_clears(cls, value: str | None) -> str | None:
        if isinstance(value, str) and not value.strip():
            return None
        return value


class TwilioSettingsTestResponse(BaseModel):
    valid: bool
    account_status: str | None
    twilio_edition: str | None
    capabilities: dict[str, bool]
    error: str | None
    warning: str | None


class TwilioSettingsTestRoute(BaseModel):
    messaging_service_sid: TwilioMessagingServiceSid | None = None

    @field_validator("messaging_service_sid", mode="before")
    @classmethod
    def blank_service_sid_clears(cls, value: str | None) -> str | None:
        if isinstance(value, str) and not value.strip():
            return None
        return value


class TwilioSettingsTestRequest(BaseModel):
    account_sid: TwilioAccountSid | None = None
    api_key_sid: TwilioApiKeySid | None = None
    api_secret: str | None = Field(default=None, max_length=255)
    auth_token: str | None = Field(default=None, max_length=255)
    routes: dict[MessagingPurpose, TwilioSettingsTestRoute] | None = None


class TwilioWebhookRotateRequest(BaseModel):
    purpose: MessagingPurpose
    expected_version: int = Field(ge=1)


class TwilioProviderCapabilities(BaseModel):
    send_sms: bool = False
    send_mms: bool = False
    receive_sms: bool = False
    receive_mms: bool = False
    status_callbacks: bool = False


class TwilioRouteReadiness(BaseModel):
    status: TwilioReadinessStatus
    can_send_sms: bool
    can_send_mms: bool
    can_receive: bool
    issues: list[str] = Field(default_factory=list)


class TwilioProviderReadiness(BaseModel):
    status: TwilioReadinessStatus
    credentials_valid: bool
    account_status: str | None
    checked_at: str | None
    capabilities: TwilioProviderCapabilities
    routes: dict[MessagingPurpose, TwilioRouteReadiness]


class TwilioQueueReadiness(BaseModel):
    status: TwilioReadinessStatus
    queued_count: int
    processing_count: int
    failed_count: int
    oldest_queued_at: str | None


class TwilioReconciliationReadiness(BaseModel):
    status: TwilioReadinessStatus
    action_required_count: int
    unresolved_event_count: int
    last_reconciled_at: str | None


class TwilioLocalReadiness(BaseModel):
    queue: TwilioQueueReadiness
    reconciliation: TwilioReconciliationReadiness


class TwilioReadinessIssue(BaseModel):
    code: str
    severity: Literal["info", "warning", "error"]
    message: str
    route: MessagingPurpose | None


class TwilioReadinessResponse(BaseModel):
    overall_status: TwilioReadinessStatus
    checked_at: str | None
    provider: TwilioProviderReadiness
    local: TwilioLocalReadiness
    issues: list[TwilioReadinessIssue]


class TwilioReadinessCheckResponse(BaseModel):
    check_status: Literal["queued", "running"]
    queued_at: str
    readiness: TwilioReadinessResponse
