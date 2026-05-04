import os
import subprocess
import sys
from pathlib import Path

from app.core.production_preflight import evaluate_production_env


def _valid_env() -> dict[str, str]:
    return {
        "APP_ENV": "production",
        "SESSION_SECRET": "x" * 40,
        "DATABASE_URL": "postgresql+psycopg2://user:pass@db-host:5432/tcg_trove",
        "ALLOWED_ORIGINS": "https://app.example.com",
        "PUBLIC_BASE_URL": "https://app.example.com",
        "SMTP_ENABLED": "false",
        "SEED_DEFAULT_ADMIN": "false",
        "API_RATE_LIMIT_PER_MINUTE": "120",
        "LOGIN_RATE_LIMIT_PER_MINUTE": "20",
    }


def test_preflight_valid_env_has_no_errors() -> None:
    errors, warnings = evaluate_production_env(_valid_env())
    assert errors == []
    assert any("SENTRY_DSN" in item for item in warnings)


def test_preflight_rejects_sqlite_database() -> None:
    env = _valid_env()
    env["DATABASE_URL"] = "sqlite:///tcg_trove.db"

    errors, _warnings = evaluate_production_env(env)
    assert any("SQLite" in item for item in errors)


def test_preflight_requires_smtp_values_when_enabled() -> None:
    env = _valid_env()
    env["SMTP_ENABLED"] = "true"

    errors, _warnings = evaluate_production_env(env)
    assert any("SMTP_USERNAME" in item for item in errors)
    assert any("SMTP_PASSWORD" in item for item in errors)
    assert any("SMTP_FROM_EMAIL" in item for item in errors)


def test_preflight_script_runs_from_repo_root() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    command = [sys.executable, "scripts/prod_preflight.py", "--env-file", "does-not-exist.env"]
    env = os.environ.copy()
    env.update(
        {
            "APP_ENV": "development",
            "SESSION_SECRET": "short",
            "DATABASE_URL": "sqlite:///tcg_trove.db",
            "ALLOWED_ORIGINS": "",
            "PUBLIC_BASE_URL": "",
        }
    )
    result = subprocess.run(
        command,
        cwd=repo_root,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "Production preflight report" in result.stdout
    assert "APP_ENV must be set to 'production'." in result.stdout


def test_preflight_rejects_default_admin_seeding() -> None:
    env = _valid_env()
    env["SEED_DEFAULT_ADMIN"] = "true"

    errors, _warnings = evaluate_production_env(env)
    assert any("SEED_DEFAULT_ADMIN" in item for item in errors)


def test_preflight_rejects_non_positive_runtime_limits() -> None:
    env = _valid_env()
    env["SESSION_MAX_AGE_SECONDS"] = "0"
    env["SESSION_ABSOLUTE_TIMEOUT_SECONDS"] = "-1"
    env["MAX_BODY_SIZE_BYTES"] = "0"
    env["UPLOAD_MAX_BYTES"] = "0"
    env["LOGIN_MAX_ATTEMPTS"] = "0"
    env["LOGIN_LOCKOUT_SECONDS"] = "-5"

    errors, _warnings = evaluate_production_env(env)
    assert any("SESSION_MAX_AGE_SECONDS" in item for item in errors)
    assert any("SESSION_ABSOLUTE_TIMEOUT_SECONDS" in item for item in errors)
    assert any("MAX_BODY_SIZE_BYTES" in item for item in errors)
    assert any("UPLOAD_MAX_BYTES" in item for item in errors)
    assert any("LOGIN_MAX_ATTEMPTS" in item for item in errors)
    assert any("LOGIN_LOCKOUT_SECONDS" in item for item in errors)


def test_preflight_rejects_upload_larger_than_body_limit() -> None:
    env = _valid_env()
    env["MAX_BODY_SIZE_BYTES"] = "1024"
    env["UPLOAD_MAX_BYTES"] = "2048"

    errors, _warnings = evaluate_production_env(env)
    assert any("UPLOAD_MAX_BYTES must be less than or equal to MAX_BODY_SIZE_BYTES" in item for item in errors)
