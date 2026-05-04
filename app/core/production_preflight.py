from __future__ import annotations

from collections.abc import Mapping

_PLACEHOLDER_SECRETS = {
    "",
    "dev-session-secret",
    "changeme",
    "change-me",
    "replace-with-strong-secret-min-32-characters",
}


def _is_truthy(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _get_int(env: Mapping[str, str], key: str, default: int) -> int:
    raw = env.get(key, str(default)).strip()
    return int(raw)


def evaluate_production_env(env: Mapping[str, str]) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    app_env = env.get("APP_ENV", "development").strip().lower()
    if app_env != "production":
        errors.append("APP_ENV must be set to 'production'.")

    session_secret = env.get("SESSION_SECRET", "").strip()
    if len(session_secret) < 32:
        errors.append("SESSION_SECRET must be at least 32 characters.")
    if session_secret.lower() in _PLACEHOLDER_SECRETS:
        errors.append("SESSION_SECRET must not use a known placeholder/default value.")

    database_url = env.get("DATABASE_URL", "").strip().lower()
    if not database_url:
        errors.append("DATABASE_URL is required.")
    elif database_url.startswith("sqlite"):
        errors.append("DATABASE_URL must be a network database in production (SQLite is not allowed).")

    allowed_origins_raw = env.get("ALLOWED_ORIGINS", "").strip()
    if not allowed_origins_raw:
        errors.append("ALLOWED_ORIGINS is required.")
    elif allowed_origins_raw == "*":
        errors.append("ALLOWED_ORIGINS cannot be '*'.")
    else:
        origins = [origin.strip() for origin in allowed_origins_raw.split(",") if origin.strip()]
        if not origins:
            errors.append("ALLOWED_ORIGINS must contain at least one explicit origin.")
        for origin in origins:
            if origin.startswith("http://"):
                warnings.append(f"Origin '{origin}' is not HTTPS.")

    public_base_url = env.get("PUBLIC_BASE_URL", "").strip()
    if not public_base_url:
        errors.append("PUBLIC_BASE_URL is required.")
    elif not public_base_url.startswith("https://"):
        errors.append("PUBLIC_BASE_URL must start with 'https://'.")

    if _is_truthy(env.get("SEED_DEFAULT_ADMIN", "true")):
        errors.append("SEED_DEFAULT_ADMIN must be disabled in production.")

    smtp_enabled = _is_truthy(env.get("SMTP_ENABLED", "false"))
    if smtp_enabled:
        smtp_username = env.get("SMTP_USERNAME", "").strip()
        smtp_password = env.get("SMTP_PASSWORD", "").strip()
        smtp_from_email = env.get("SMTP_FROM_EMAIL", "").strip()
        if not smtp_username:
            errors.append("SMTP_USERNAME is required when SMTP_ENABLED=true.")
        if not smtp_password:
            errors.append("SMTP_PASSWORD is required when SMTP_ENABLED=true.")
        if not smtp_from_email or "@" not in smtp_from_email:
            errors.append("SMTP_FROM_EMAIL must be a valid email when SMTP_ENABLED=true.")

    if not env.get("SENTRY_DSN", "").strip():
        warnings.append("SENTRY_DSN is empty; error tracking is disabled.")

    try:
        login_rate = _get_int(env, "LOGIN_RATE_LIMIT_PER_MINUTE", 20)
        api_rate = _get_int(env, "API_RATE_LIMIT_PER_MINUTE", 120)
        if login_rate <= 0 or api_rate <= 0:
            errors.append("Rate limits must be positive integers.")
    except ValueError:
        errors.append("API_RATE_LIMIT_PER_MINUTE and LOGIN_RATE_LIMIT_PER_MINUTE must be integers.")

    bounded_positive_ints = {
        "SESSION_MAX_AGE_SECONDS": 86400,
        "SESSION_ABSOLUTE_TIMEOUT_SECONDS": 43200,
        "MAX_BODY_SIZE_BYTES": 10_485_760,
        "UPLOAD_MAX_BYTES": 5_242_880,
        "LOGIN_MAX_ATTEMPTS": 5,
        "LOGIN_LOCKOUT_SECONDS": 300,
    }
    parsed_values: dict[str, int] = {}
    for key, default in bounded_positive_ints.items():
        try:
            value = _get_int(env, key, default)
            if value <= 0:
                errors.append(f"{key} must be a positive integer.")
            else:
                parsed_values[key] = value
        except ValueError:
            errors.append(f"{key} must be an integer.")

    max_body = parsed_values.get("MAX_BODY_SIZE_BYTES")
    upload_max = parsed_values.get("UPLOAD_MAX_BYTES")
    if max_body is not None and upload_max is not None and upload_max > max_body:
        errors.append("UPLOAD_MAX_BYTES must be less than or equal to MAX_BODY_SIZE_BYTES.")

    return errors, warnings
