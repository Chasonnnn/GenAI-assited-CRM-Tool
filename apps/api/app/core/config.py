"""Application configuration with environment variables."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    
    # Environment
    ENV: str = "dev"
    
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
    META_TEST_MODE: bool = True  # Set to False in production
    META_API_VERSION: str = "v21.0"
    META_ENCRYPTION_KEY: str = ""  # Fernet key for encrypting page tokens
    META_WEBHOOK_MAX_PAYLOAD_BYTES: int = 100000  # 100KB limit
    
    # Meta Conversions API (CAPI) - for sending lead quality signals back to Meta
    META_PIXEL_ID: str = ""  # Dataset ID for Conversions API
    META_CAPI_ENABLED: bool = False  # Enable sending status updates to Meta
    
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