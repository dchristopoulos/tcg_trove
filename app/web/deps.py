import logging
import secrets
import time
from io import BytesIO
from pathlib import Path
from uuid import uuid4

from fastapi import (
    HTTPException,
    Request,
    UploadFile,
)
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.core.config import settings
from app.services.rate_limit_service import consume_rate_limit
from app.services.user_service import is_session_token_valid
from app.web.auth import (
    SESSION_CSRF_KEY,
    SESSION_LOGIN_AT_KEY,
    SESSION_ROLE_KEY,
    SESSION_TOKEN_KEY,
    SESSION_USER_KEY,
)

logger = logging.getLogger("tcg_trove.web.deps")
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parents[1] / "templates"))
UPLOADS_DIR = Path(settings.media_dir)
RATE_WINDOW_SECONDS = 60
MAX_UPLOAD_IMAGE_DIMENSION = 1920


def condition_label(value: str | None) -> str:
    """Display inherited condition storage names as trading-card terms."""
    labels = {
        "near_mint": "Near Mint",
        "lightly_played": "Lightly Played",
        "moderately_played": "Moderately Played",
        "heavily_played": "Heavily Played",
        "damaged": "Damaged",
        "furnished": "Near Mint",
        "semi_furnished": "Lightly Played",
        "unfurnished": "Played",
    }
    if value is None:
        return ""
    normalized = str(value).strip().lower()
    return labels.get(normalized, normalized.replace("_", " ").title())


templates.env.filters["condition_label"] = condition_label

_IMAGE_SIGNATURES: dict[str, tuple[bytes, ...]] = {
    "jpeg": (b"\xff\xd8\xff",),
    "png": (b"\x89PNG\r\n\x1a\n",),
}

try:
    from PIL import Image, ImageOps
except Exception:  # pragma: no cover - optional dependency fallback
    Image = None
    ImageOps = None


def get_session_user_id(request: Request) -> int | None:
    raw_user_id = request.session.get(SESSION_USER_KEY)
    if raw_user_id is None:
        return None
    try:
        return int(raw_user_id)
    except (TypeError, ValueError):
        request.session.pop(SESSION_USER_KEY, None)
        return None


def is_valid_active_session(request: Request, user) -> bool:
    if user is None:
        return False
    login_at = request.session.get(SESSION_LOGIN_AT_KEY)
    if login_at is None:
        return False
    try:
        if int(time.time()) - int(login_at) > settings.session_absolute_timeout_seconds:
            return False
    except (TypeError, ValueError):
        return False
    return is_session_token_valid(user, request.session.get(SESSION_TOKEN_KEY))


def clear_session(request: Request) -> None:
    request.session.pop(SESSION_USER_KEY, None)
    request.session.pop(SESSION_TOKEN_KEY, None)
    request.session.pop(SESSION_ROLE_KEY, None)
    request.session.pop(SESSION_LOGIN_AT_KEY, None)


def get_or_create_csrf_token(request: Request) -> str:
    token = request.session.get(SESSION_CSRF_KEY)
    if token is None:
        token = secrets.token_urlsafe(24)
        request.session[SESSION_CSRF_KEY] = token
    return str(token)


def is_valid_csrf(request: Request, csrf_token: str) -> bool:
    token = request.session.get(SESSION_CSRF_KEY)
    if token is None:
        return False
    return secrets.compare_digest(str(token), csrf_token)


def template_response(request: Request, template_name: str, context: dict, status_code: int = 200):
    merged_context = dict(context)
    merged_context["csrf_token"] = get_or_create_csrf_token(request)
    return templates.TemplateResponse(request, template_name, merged_context, status_code=status_code)


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def is_rate_limited(db: Session, request: Request, action: str, identifier: str, limit: int) -> bool:
    ip_key = f"{action}:ip:{client_ip(request)}"
    account_key = f"{action}:acct:{identifier.strip().lower()}"
    ip_allowed = consume_rate_limit(db, scope_key=ip_key, limit=limit, window_seconds=RATE_WINDOW_SECONDS)
    account_allowed = consume_rate_limit(db, scope_key=account_key, limit=limit, window_seconds=RATE_WINDOW_SECONDS)
    return not (ip_allowed and account_allowed)


def request_audit_context(request: Request) -> dict[str, str | None]:
    request_id = getattr(request.state, "request_id", None)
    return {
        "ip_address": request.client.host if request.client else None,
        "user_agent": request.headers.get("user-agent"),
        "request_id": request_id,
    }


def detect_image_type(content: bytes) -> str | None:
    for image_type, signatures in _IMAGE_SIGNATURES.items():
        for signature in signatures:
            if content.startswith(signature):
                return image_type
    if len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return "webp"
    return None


def _maybe_optimize_image(content: bytes) -> tuple[bytes, str]:
    if Image is None or ImageOps is None:
        return content, ""

    try:
        with Image.open(BytesIO(content)) as source:
            normalized = ImageOps.exif_transpose(source)
            normalized.thumbnail((MAX_UPLOAD_IMAGE_DIMENSION, MAX_UPLOAD_IMAGE_DIMENSION), Image.Resampling.LANCZOS)
            has_alpha = normalized.mode in {"RGBA", "LA"} or (
                normalized.mode == "P" and "transparency" in normalized.info
            )
            output = BytesIO()
            if has_alpha:
                normalized.save(output, format="WEBP", lossless=True, method=6)
            else:
                normalized.convert("RGB").save(output, format="WEBP", quality=82, method=6)
            optimized = output.getvalue()
            if optimized and len(optimized) < len(content):
                return optimized, ".webp"
    except Exception:
        logger.exception("Image optimization failed; storing original upload")

    return content, ""


def save_uploaded_image(file: UploadFile | None) -> str | None:
    if file is None or not file.filename:
        return None
    if file.content_type not in {"image/jpeg", "image/png", "image/webp"}:
        raise HTTPException(status_code=400, detail="Unsupported image type")
    suffix = Path(file.filename).suffix.lower()
    if suffix not in {".jpg", ".jpeg", ".png", ".webp"}:
        raise HTTPException(status_code=400, detail="Unsupported image extension")
    content = file.file.read()
    if len(content) > settings.upload_max_bytes:
        raise HTTPException(status_code=413, detail="Uploaded image is too large")
    detected_type = detect_image_type(content)
    if detected_type is None:
        raise HTTPException(status_code=400, detail="Uploaded file is not a valid supported image")
    suffix_map = {"jpeg": {".jpg", ".jpeg"}, "png": {".png"}, "webp": {".webp"}}
    if suffix not in suffix_map[detected_type]:
        raise HTTPException(status_code=400, detail="File extension does not match uploaded image type")
    optimized_content, optimized_suffix = _maybe_optimize_image(content)
    if optimized_suffix:
        content = optimized_content
        suffix = optimized_suffix
    if len(content) > settings.upload_max_bytes:
        raise HTTPException(status_code=413, detail="Uploaded image is too large after processing")
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    image_name = f"{uuid4().hex}{suffix}"
    target = UPLOADS_DIR / image_name
    target.write_bytes(content)
    return f"/static/uploads/{image_name}"
