"""Application configuration with environment variables."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    
    # Environment
    ENV: str = "dev"
    
    # App Version (format: a.bc.de - major.feature.patch)
    VERSION: str = "0.06.00"
    
    # Version Control Encryption (Fernet key for config snapshots)
    VERSION_ENCRYPTION_KEY: str = ""  # Falls back to META_ENCRYPTION_KEY if empty
    
    # Proxy/Load Balancer Settings
    # Set to True when running behind nginx/Cloudflare to trust X-Forwarded-For
    TRUST_PROXY_HEADERS: bool = False

    
    # Database
    DATABASE_URL: str
    
    # Session Token (supports key rotation)
    JWT_SECRET: str = "change-this-in-production"
    JWT_SECRET_PREVIOUS: str = ""  # Set during rotation, clear after
    JWT_EXPIRES_HOURS: int = 4
    
    # Google OAuth
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = "http://localhost:8000/auth/google/callback"
    
    # Domain restriction (comma-separated)
    ALLOWED_EMAIL_DOMAINS: str = ""
    
    # CORS
    CORS_ORIGINS: str = "http://localhost:3000"
    
    # Frontend (for safe redirects)
    FRONTEND_URL: str = "http://localhost:3000"
    
    # Dev-only
    DEV_SECRET: str = "change-me"
    
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
    META_CAPI_ACCESS_TOKEN: str = ""  # System user access token for CAPI (optional, falls back to page token)
    
    # Internal scheduled endpoints (cron jobs)
    INTERNAL_SECRET: str = ""  # Secret for /internal/scheduled/* endpoints
    
    # Zoom OAuth (for per-user Zoom integration)
    ZOOM_CLIENT_ID: str = ""
    ZOOM_CLIENT_SECRET: str = ""
    ZOOM_REDIRECT_URI: str = "http://localhost:8000/integrations/zoom/callback"
    
    # Token Encryption (for storing OAuth tokens, AI API keys)
    FERNET_KEY: str = ""  # Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    
    # Gmail OAuth (per-user, different from Google Login OAuth)
    GMAIL_REDIRECT_URI: str = "http://localhost:8000/integrations/gmail/callback"
    
    # Error Tracking (optional, set in production)
    SENTRY_DSN: str = ""  # Get from https://sentry.io
    
    # Rate Limiting (requests per minute)
    RATE_LIMIT_AUTH: int = 5  # Login attempts
    RATE_LIMIT_WEBHOOK: int = 100  # Meta webhooks
    RATE_LIMIT_API: int = 60  # General API
    
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
    def jwt_secrets(self) -> list[str]:
        """Returns list of valid secrets (current first, then previous if set)."""
        secrets = [self.JWT_SECRET]
        if self.JWT_SECRET_PREVIOUS:
            secrets.append(self.JWT_SECRET_PREVIOUS)
        return secrets
    
    @property
    def cookie_secure(self) -> bool:
        """Secure cookies only in production."""
        return self.ENV != "dev"


settings = Settings()