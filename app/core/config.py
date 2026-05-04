from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB_PATH = PROJECT_ROOT / "tcg_trove.db"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "TCG Trove"
    app_env: str = "development"
    app_version: str = "1.0.0"
    public_base_url: str = "http://127.0.0.1:8000"
    email_verification_ttl_seconds: int = 86400
    password_reset_ttl_seconds: int = 3600
    email_verification_resend_cooldown_seconds: int = 45
    session_secret: str = "dev-session-secret"
    session_max_age_seconds: int = 86400
    session_absolute_timeout_seconds: int = 43200
    allowed_origins: str = "*"
    api_rate_limit_per_minute: int = 120
    login_rate_limit_per_minute: int = 20
    rate_limit_redis_url: str = ""
    rate_limit_event_retention_seconds: int = 86400
    max_body_size_bytes: int = 10_485_760
    upload_max_bytes: int = 5_242_880
    database_url: str = f"sqlite:///{DEFAULT_DB_PATH.as_posix()}"
    login_max_attempts: int = 5
    login_lockout_seconds: int = 300
    smtp_enabled: bool = False
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from_email: str = "noreply@tcgtrove.local"
    smtp_use_tls: bool = True
    email_outbox_worker_enabled: bool = True
    email_outbox_poll_seconds: int = 20
    email_outbox_batch_size: int = 20
    sentry_dsn: str = ""
    sentry_traces_sample_rate: float = 0.0
    metrics_auth_token: str = ""
    media_dir: str = str(PROJECT_ROOT / "app" / "static" / "uploads")
    media_upload_retention_days: int = 180
    inquiry_message_retention_days: int = 365
    search_log_retention_days: int = 365
    audit_log_retention_days: int = 730
    backup_dir: str = str(PROJECT_ROOT / "backups")
    seed_default_admin: bool = True

    @property
    def allowed_origins_list(self) -> list[str]:
        if self.allowed_origins.strip() == "*":
            return ["*"]
        return [item.strip() for item in self.allowed_origins.split(",") if item.strip()]

    @property
    def is_production(self) -> bool:
        return self.app_env.strip().lower() == "production"

    @property
    def is_development(self) -> bool:
        return self.app_env.strip().lower() == "development"

    @model_validator(mode="after")
    def validate_production_settings(self):
        if self.is_production and len(self.session_secret) < 32:
            raise ValueError("session_secret must be at least 32 chars in production")

        normalized_secret = self.session_secret.strip().lower()
        if self.is_production and normalized_secret in {
            "dev-session-secret",
            "changeme",
            "change-me",
            "replace-with-strong-secret-min-32-characters",
        }:
            raise ValueError("session_secret must not use a known placeholder/default in production")

        if self.is_production and self.database_url.startswith("sqlite"):
            raise ValueError("Use a network database URL in production")

        if self.is_production and self.allowed_origins.strip() == "*":
            raise ValueError("allowed_origins cannot be '*' in production")

        if self.is_production and not self.public_base_url.startswith("https://"):
            raise ValueError("public_base_url must use https in production")

        if self.is_production and self.seed_default_admin:
            raise ValueError("seed_default_admin must be disabled in production")

        if self.is_production and self.smtp_enabled:
            if not self.smtp_username.strip() or not self.smtp_password.strip():
                raise ValueError("smtp_username and smtp_password are required when SMTP is enabled in production")
            if not self.smtp_from_email.strip() or "@" not in self.smtp_from_email:
                raise ValueError("smtp_from_email must be a valid sender address in production when SMTP is enabled")

        return self


settings = Settings()
