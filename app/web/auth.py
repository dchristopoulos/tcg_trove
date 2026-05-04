import hashlib
import hmac
import secrets
from hashlib import sha256

SESSION_USER_KEY = "user_id"
SESSION_TOKEN_KEY = "session_token"
SESSION_ROLE_KEY = "user_role"
SESSION_LOGIN_AT_KEY = "session_login_at"
SESSION_CSRF_KEY = "csrf_token"
_PBKDF2_ITERATIONS = 390000


def _is_legacy_sha256_hash(hashed_password: str) -> bool:
    if len(hashed_password) != 64:
        return False
    return all(ch in "0123456789abcdef" for ch in hashed_password.lower())


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        bytes.fromhex(salt),
        _PBKDF2_ITERATIONS,
    )
    return f"pbkdf2_sha256${_PBKDF2_ITERATIONS}${salt}${digest.hex()}"


def verify_password(password: str, hashed_password: str) -> bool:
    if _is_legacy_sha256_hash(hashed_password):
        return secrets.compare_digest(sha256(password.encode("utf-8")).hexdigest(), hashed_password)
    if not hashed_password.startswith("pbkdf2_sha256$"):
        return False
    try:
        _, rounds_str, salt_hex, digest_hex = hashed_password.split("$", maxsplit=3)
        rounds = int(rounds_str)
        computed = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            bytes.fromhex(salt_hex),
            rounds,
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(computed.hex(), digest_hex)


def needs_password_rehash(hashed_password: str) -> bool:
    if _is_legacy_sha256_hash(hashed_password):
        return True
    if not hashed_password.startswith("pbkdf2_sha256$"):
        return True
    try:
        rounds = int(hashed_password.split("$", maxsplit=3)[1])
    except (IndexError, ValueError):
        return True
    return rounds < _PBKDF2_ITERATIONS


def get_current_user_id(request) -> int | None:
    user_id = request.session.get(SESSION_USER_KEY)
    return int(user_id) if user_id is not None else None
