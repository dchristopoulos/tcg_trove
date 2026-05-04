from typing import Any

import pytest
from pydantic import ValidationError

from app.core.config import Settings


def _base_prod_settings() -> dict[str, Any]:
    return {
        "app_env": "production",
        "session_secret": "A" * 48,
        "database_url": "postgresql+psycopg2://user:pass@db-host:5432/tcg_trove",
        "allowed_origins": "https://app.example.com",
        "public_base_url": "https://app.example.com",
        "smtp_enabled": False,
        "smtp_username": "",
        "smtp_password": "",
        "smtp_from_email": "noreply@example.com",
        "seed_default_admin": False,
    }


def test_production_rejects_placeholder_session_secret() -> None:
    values = _base_prod_settings()
    values["session_secret"] = "replace-with-strong-secret-min-32-characters"

    with pytest.raises(ValidationError):
        Settings(**values)


def test_production_requires_https_public_base_url() -> None:
    values = _base_prod_settings()
    values["public_base_url"] = "http://app.example.com"

    with pytest.raises(ValidationError):
        Settings(**values)


def test_production_requires_smtp_credentials_when_enabled() -> None:
    values = _base_prod_settings()
    values["smtp_enabled"] = True

    with pytest.raises(ValidationError):
        Settings(**values)


def test_production_accepts_valid_smtp_configuration() -> None:
    values = _base_prod_settings()
    values["smtp_enabled"] = True
    values["smtp_username"] = "smtp-user"
    values["smtp_password"] = "smtp-pass"
    values["smtp_from_email"] = "alerts@example.com"

    settings = Settings(**values)
    assert settings.is_production is True


def test_production_rejects_default_admin_seeding() -> None:
    values = _base_prod_settings()
    values["seed_default_admin"] = True

    with pytest.raises(ValidationError):
        Settings(**values)
