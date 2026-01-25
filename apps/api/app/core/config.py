"""Application configuration with environment variables."""

import json
import os
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_JWT_SECRET = "change-this-in-production"
DEFAULT_DEV_SECRET = "change-me"
DEFAULT_API_BASE_URL = "http://localhost:8000"
DEFAULT_FRONTEND_URL = "http://localhost:3000"
DEFAULT_CORS_ORIGINS = "http://localhost:3000"
DEFAULT_GOOGLE_REDIRECT_URI = "http://localhost:8000/auth/google/callback"
DEFAULT_ZOOM_REDIRECT_URI = "http://localhost:8000/integrations/zoom/callback"
DEFAULT_GMAIL_REDIRECT_URI = "http://localhost:8000/integrations/gmail/callback"
DEFAULT_GOOGLE_CALENDAR_REDIRECT_URI = "http://localhost:8000/integrations/google-calendar/callback"
DEFAULT_DUO_REDIRECT_URI = "http://localhost:3000/auth/duo/callback"
RELEASE_PLEASE_MANIFEST_NAME = ".release-please-manifest.json"
FALLBACK_APP_VERSION = "0.20.0"


def _read_release_please_manifest_version(path: Path) -> str | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    version = data.get(".")
    if isinstance(version, str) and version.strip():
        return version.strip()
    return None


def _load_release_please_version() -> str | None:
    override = os.getenv("RELEASE_PLEASE_MANIFEST_PATH")
    if override:
        override_path = Path(override)
        if override_path.is_file():
            return _read_release_please_manifest_version(override_path)
        return None

    for parent in Path(__file__).resolve().parents:
        candidate = parent / RELEASE_PLEASE_MANIFEST_NAME
        if candidate.is_file():
            return _read_release_please_manifest_version(candidate)
    return None


def _default_app_version() -> str:
    return _load_release_please_version() or FALLBACK_APP_VERSION


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Environment (required - no default to prevent accidental dev mode in production)
    ENV: str

    # App Version (SemVer: MAJOR.MINOR.PATCH)
    VERSION: str = Field(default_factory=_default_app_version)

    # Version Control Encryption (Fernet key for config snapshots)
    VERSION_ENCRYPTION_KEY: str = ""  # Falls back to META_ENCRYPTION_KEY if empty

    # Proxy/Load Balancer Settings
    # Set to True when running behind nginx/Cloudflare to trust X-Forwarded-For
    TRUST_PROXY_HEADERS: bool = False

    # Database
    DATABASE_URL: str
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_TIMEOUT: int = 30
    DB_POOL_RECYCLE: int = -1
    DB_POOL_PRE_PING: bool = True
    DB_MIGRATION_CHECK: bool = True
    DB_AUTO_MIGRATE: bool = False

    # Session Token (supports key rotation)
    JWT_SECRET: str = ""
    JWT_SECRET_PREVIOUS: str = ""  # Set during rotation, clear after
    JWT_EXPIRES_HOURS: int = 4
    COOKIE_SAMESITE: str = "lax"

    # Google OAuth
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = ""

    # Domain restriction (comma-separated)
    ALLOWED_EMAIL_DOMAINS: str = ""

    # CORS
    CORS_ORIGINS: str = ""

    # Frontend (for safe redirects)
    FRONTEND_URL: str = ""

    # Ops Console frontend URL (for platform admin redirects)
    OPS_FRONTEND_URL: str = ""

    # Cookie domain for cross-subdomain sharing (e.g., ".surrogacyforce.com")
    # Leave empty for host-only cookies (local dev)
    COOKIE_DOMAIN: str = ""

    # Platform admin emails (comma-separated, for allowlist-based access)
    PLATFORM_ADMIN_EMAILS: str = ""

    # Platform/system email sender (Resend)
    # Intentionally separate from RESEND_API_KEY/EMAIL_FROM (used by campaign/user email paths).
    PLATFORM_RESEND_API_KEY: str = ""
    PLATFORM_RESEND_WEBHOOK_SECRET: str = ""
    # Optional fallback From header. Recommended: set per-template `from_email` in ops/system templates.
    PLATFORM_EMAIL_FROM: str = ""

    # HMAC secret for PII-safe audit logging (IP, user agent)
    AUDIT_HMAC_SECRET: str = ""

    # Support session settings (platform admin role override)
    SUPPORT_SESSION_TTL_MINUTES: int = 60
    SUPPORT_SESSION_ALLOW_READ_ONLY: bool = False

    # API base URL (for tracking, callbacks)
    API_BASE_URL: str = ""

    # Dev-only
    DEV_SECRET: str = ""

    # Meta Lead Ads webhook
    META_VERIFY_TOKEN: str = ""

    # Meta Lead Ads API
    META_APP_ID: str = ""
    META_APP_SECRET: str = ""
    META_TEST_MODE: bool = False  # Set to True only for local testing
    META_API_VERSION: str = "v21.0"
    META_ENCRYPTION_KEY: str = ""  # Fernet key for encrypting page tokens
    META_WEBHOOK_MAX_PAYLOAD_BYTES: int = 100000  # 100KB limit

    # Meta Ads Insights (spend/budget data)
    META_AD_ACCOUNT_ID: str = ""  # Format: act_XXXXXX
    META_SYSTEM_TOKEN: str = ""  # System user token with ads_read permission

    # Meta Conversions API (CAPI) - for sending lead quality signals back to Meta
    META_PIXEL_ID: str = ""  # Dataset ID for Conversions API
    META_CAPI_ENABLED: bool = False  # Enable sending status updates to Meta
    META_CAPI_ACCESS_TOKEN: str = (
        ""  # System user access token for CAPI (optional, falls back to page token)
    )

    # Internal scheduled endpoints (cron jobs)
    INTERNAL_SECRET: str = ""  # Secret for /internal/scheduled/* endpoints

    # Zoom OAuth (for per-user Zoom integration)
    ZOOM_CLIENT_ID: str = ""
    ZOOM_CLIENT_SECRET: str = ""
    ZOOM_REDIRECT_URI: str = ""
    ZOOM_WEBHOOK_SECRET: str = ""  # Webhook verification token from Zoom app settings

    # Token Encryption (for storing OAuth tokens, AI API keys)
    FERNET_KEY: str = ""  # Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

    # PII Field Encryption (cases, intended parents, etc.)
    DATA_ENCRYPTION_KEY: str = ""  # Fernet key for PII encryption at rest
    PII_HASH_KEY: str = ""  # HMAC key for deterministic PII hashes

    # Gmail OAuth (per-user, different from Google Login OAuth)
    GMAIL_REDIRECT_URI: str = ""
    # Google Calendar OAuth (per-user, used for Meet + calendar sync)
    GOOGLE_CALENDAR_REDIRECT_URI: str = ""

    # Error Tracking (optional, set in production)
    SENTRY_DSN: str = ""  # Get from https://sentry.io

    # GCP Monitoring (Cloud Logging + Error Reporting)
    GCP_MONITORING_ENABLED: bool = True
    GCP_PROJECT_ID: str = ""
    GCP_SERVICE_NAME: str = "crm-api"
    GCP_ERROR_REPORTING_SAMPLE_RATE: float = 1.0

    # Rate Limiting (requests per minute)
    RATE_LIMIT_AUTH: int = 5  # Login attempts
    RATE_LIMIT_WEBHOOK: int = 100  # Meta webhooks
    RATE_LIMIT_API: int = 60  # General API
    RATE_LIMIT_SEARCH: int = 30  # Global search
    RATE_LIMIT_PUBLIC_READ: int = 60  # Public GET endpoints
    RATE_LIMIT_PUBLIC_FORMS: int = 10  # Public form submissions
    RATE_LIMIT_FAIL_OPEN: bool = True

    # Analytics caching
    ANALYTICS_CACHE_TTL_SECONDS: int = 300

    # Observability (OpenTelemetry)
    OTEL_ENABLED: bool = False
    OTEL_SERVICE_NAME: str = "crm-api"
    OTEL_EXPORTER_OTLP_ENDPOINT: str = ""
    OTEL_EXPORTER_OTLP_HEADERS: str = ""
    OTEL_SAMPLE_RATE: float = 0.1

    # SLO defaults (core workflows)
    SLO_SUCCESS_RATE: float = 0.99
    SLO_AVG_LATENCY_MS: int = 500

    def model_post_init(self, __context) -> None:
        env = self.ENV.lower()
        if env in {"dev", "development", "test"}:
            if not self.JWT_SECRET:
                self.JWT_SECRET = DEFAULT_JWT_SECRET
            if not self.DEV_SECRET:
                self.DEV_SECRET = DEFAULT_DEV_SECRET
            if not self.API_BASE_URL:
                self.API_BASE_URL = DEFAULT_API_BASE_URL
            if not self.FRONTEND_URL:
                self.FRONTEND_URL = DEFAULT_FRONTEND_URL
            if not self.CORS_ORIGINS:
                self.CORS_ORIGINS = DEFAULT_CORS_ORIGINS
            if not self.GOOGLE_REDIRECT_URI:
                self.GOOGLE_REDIRECT_URI = DEFAULT_GOOGLE_REDIRECT_URI
            if not self.ZOOM_REDIRECT_URI:
                self.ZOOM_REDIRECT_URI = DEFAULT_ZOOM_REDIRECT_URI
            if not self.GMAIL_REDIRECT_URI:
                self.GMAIL_REDIRECT_URI = DEFAULT_GMAIL_REDIRECT_URI
            if not self.GOOGLE_CALENDAR_REDIRECT_URI:
                self.GOOGLE_CALENDAR_REDIRECT_URI = DEFAULT_GOOGLE_CALENDAR_REDIRECT_URI
            if not self.DUO_REDIRECT_URI:
                self.DUO_REDIRECT_URI = DEFAULT_DUO_REDIRECT_URI
            return

        errors: list[str] = []
        if not self.JWT_SECRET or self.JWT_SECRET == DEFAULT_JWT_SECRET:
            errors.append("JWT_SECRET must be set for non-dev environments")
        if not self.DEV_SECRET or self.DEV_SECRET == DEFAULT_DEV_SECRET:
            errors.append("DEV_SECRET must be set for non-dev environments")
        if not self.API_BASE_URL:
            errors.append("API_BASE_URL must be set for non-dev environments")
        if self.META_TEST_MODE:
            errors.append("META_TEST_MODE must be false in non-dev environments")

        url_fields = [
            "API_BASE_URL",
            "GOOGLE_REDIRECT_URI",
            "CORS_ORIGINS",
            "FRONTEND_URL",
            "ZOOM_REDIRECT_URI",
            "GMAIL_REDIRECT_URI",
            "DUO_REDIRECT_URI",
        ]
        for field in url_fields:
            value = getattr(self, field, "")
            if "localhost" in value or "127.0.0.1" in value:
                errors.append(f"{field} must not use localhost in non-dev environments")

        # Enforce encryption keys in production
        encryption_keys = [
            ("META_ENCRYPTION_KEY", self.META_ENCRYPTION_KEY),
            ("FERNET_KEY", self.FERNET_KEY),
            ("DATA_ENCRYPTION_KEY", self.DATA_ENCRYPTION_KEY),
            ("PII_HASH_KEY", self.PII_HASH_KEY),
        ]
        for key_name, key_value in encryption_keys:
            if not key_value:
                errors.append(f"{key_name} must be set for non-dev environments")

        if not self.ATTACHMENT_SCAN_ENABLED:
            errors.append("ATTACHMENT_SCAN_ENABLED must be true in non-dev environments")

        if not self.SENTRY_DSN:
            if not self.GCP_MONITORING_ENABLED:
                errors.append(
                    "SENTRY_DSN must be set or GCP_MONITORING_ENABLED must be true in non-dev environments"
                )
            elif not self.gcp_project_id:
                errors.append(
                    "GCP_PROJECT_ID or GOOGLE_CLOUD_PROJECT must be set when GCP monitoring is enabled"
                )

        if errors:
            raise ValueError("Invalid production configuration: " + "; ".join(errors))

    SLO_WINDOW_MINUTES: int = 60

    # Compliance exports
    EXPORT_STORAGE_BACKEND: str = "local"  # local or s3
    EXPORT_LOCAL_DIR: str = ".exports"
    EXPORT_S3_BUCKET: str = ""
    EXPORT_S3_REGION: str = ""
    EXPORT_S3_PREFIX: str = "exports"
    EXPORT_URL_TTL_SECONDS: int = 3600
    EXPORT_MAX_RECORDS: int = 50000
    EXPORT_RATE_LIMIT_PER_HOUR: int = 5
    DEFAULT_RETENTION_DAYS: int = 2190  # 6 years

    # Attachment Storage
    STORAGE_BACKEND: str = "local"  # local or s3
    LOCAL_STORAGE_PATH: str = ".attachments"
    S3_BUCKET: str = ""
    S3_REGION: str = "us-east-1"
    S3_ENDPOINT_URL: str = ""  # Optional S3-compatible endpoint (e.g., GCS)
    S3_PUBLIC_BASE_URL: str = ""  # Optional public base URL for assets
    S3_URL_STYLE: str = "path"  # path or virtual
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    ATTACHMENT_SCAN_ENABLED: bool = False

    # Export Storage (optional separate endpoint)
    EXPORT_S3_ENDPOINT_URL: str = ""

    # Duo MFA (Web SDK v4)
    DUO_CLIENT_ID: str = ""  # Integration key from Duo Admin
    DUO_CLIENT_SECRET: str = ""  # Secret key from Duo Admin
    DUO_API_HOST: str = ""  # API hostname (api-XXXXX.duosecurity.com)
    DUO_REDIRECT_URI: str = ""

    @property
    def duo_enabled(self) -> bool:
        """Check if Duo is configured."""
        return bool(
            (self.DUO_CLIENT_ID or "").strip()
            and (self.DUO_CLIENT_SECRET or "").strip()
            and (self.DUO_API_HOST or "").strip()
        )

    @property
    def gcp_project_id(self) -> str:
        """Return explicit GCP project or Cloud Run project id."""
        return self.GCP_PROJECT_ID or os.getenv("GOOGLE_CLOUD_PROJECT", "")

    @property
    def is_dev(self) -> bool:
        """True for dev-like environments (dev/development/test)."""
        return self.ENV.lower() in {"dev", "development", "test"}

    @property
    def is_prod(self) -> bool:
        """True for production-like environments."""
        return self.ENV.lower() in {"prod", "production"}

    @property
    def cors_origins_list(self) -> list[str]:
        """Parse CORS_ORIGINS into a list."""
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def allowed_domains_list(self) -> list[str]:
        """Parse ALLOWED_EMAIL_DOMAINS into lowercase list."""
        if not self.ALLOWED_EMAIL_DOMAINS:
            return []
        return [d.strip().lower() for d in self.ALLOWED_EMAIL_DOMAINS.split(",")]

    @property
    def platform_admin_emails_list(self) -> list[str]:
        """Parse PLATFORM_ADMIN_EMAILS into lowercase list."""
        if not self.PLATFORM_ADMIN_EMAILS:
            return []
        return [e.strip().lower() for e in self.PLATFORM_ADMIN_EMAILS.split(",") if e.strip()]

    @property
    def jwt_secrets(self) -> list[str]:
        """Returns list of valid secrets (current first, then previous if set)."""
        secrets = [self.JWT_SECRET]
        if self.JWT_SECRET_PREVIOUS:
            secrets.append(self.JWT_SECRET_PREVIOUS)
        return secrets

    @property
    def cookie_samesite(self) -> str:
        """Normalize SameSite setting for cookies."""
        value = (self.COOKIE_SAMESITE or "lax").strip().lower()
        if value not in {"lax", "strict", "none"}:
            raise ValueError("COOKIE_SAMESITE must be one of: lax, strict, none")
        return value

    @property
    def cookie_secure(self) -> bool:
        """Secure cookies only in production."""
        if self.cookie_samesite == "none":
            return True
        return not self.is_dev


settings = Settings()
