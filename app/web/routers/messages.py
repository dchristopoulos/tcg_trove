import logging
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

from app.core.exceptions import InquiryNotFoundError, ListingNotFoundError, PermissionDeniedError
from app.core.metrics import record_message_poll, record_message_reply
from app.db.models.inquiry import Inquiry
from app.db.models.listing import Listing
from app.db.models.user import User
from app.db.session import get_db
from app.services.inquiry_service import (
    add_inquiry_reply_use_case,
    inbox_inquiries_page_use_case,
    inquiry_replies_use_case,
    my_inquiries_page_use_case,
    replies_for_inquiry_ids_use_case,
    update_inquiry_status_use_case,
)
from app.services.user_service import get_user_profile
from app.web.auth import SESSION_ROLE_KEY
from app.web.deps import (
    get_session_user_id,
    is_rate_limited,
    is_valid_active_session,
    is_valid_csrf,
    template_response,
)

router = APIRouter()
logger = logging.getLogger("tcg_trove.web.messages")
ALLOWED_INQUIRY_STATUSES = {"open", "in_progress", "responded", "closed"}
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 50
MAX_SEARCH_CHARS = 120
MAX_FLASH_CHARS = 200
MESSAGE_REPLY_RATE_LIMIT_PER_MINUTE = 30
MESSAGE_POLL_RATE_LIMIT_PER_MINUTE = 180
MESSAGE_STATUS_RATE_LIMIT_PER_MINUTE = 120


def _resolve_redirect_target(next_path: str | None, fallback: str, *, request: Request | None = None) -> str:
    raw_target = (next_path or "").strip()
    if not raw_target and request is not None:
        raw_target = str(request.headers.get("referer") or "")
    if not raw_target:
        return fallback

    split = urlsplit(raw_target)
    path = split.path
    query = split.query
    if split.scheme or split.netloc:
        if request is None:
            return fallback
        request_split = urlsplit(str(request.url))
        if split.netloc != request_split.netloc or split.scheme not in {"http", "https"}:
            return fallback

    if not path.startswith("/") or path.startswith("//") or "\\" in path:
        return fallback
    if any(ch in path for ch in ("\r", "\n", "\x00")):
        return fallback
    return urlunsplit(("", "", path, query, ""))


def _append_query_params(path: str, params: dict[str, str]) -> str:
    split = urlsplit(path)
    existing_params = [(k, v) for k, v in parse_qsl(split.query, keep_blank_values=True) if k not in params]
    merged = existing_params + [(k, v) for k, v in params.items() if v]
    return urlunsplit((split.scheme, split.netloc, split.path, urlencode(merged), split.fragment))


def _normalize_flash(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = " ".join(str(value).split()).strip()
    if not normalized:
        return None
    return normalized[:MAX_FLASH_CHARS]


def _normalize_search(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = " ".join(str(value).split()).strip()
    if not normalized:
        return None
    return normalized[:MAX_SEARCH_CHARS]


def _normalize_status(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip().lower()
    if not normalized or normalized == "all":
        return None
    if normalized not in ALLOWED_INQUIRY_STATUSES:
        return "INVALID"
    return normalized


def _pagination_meta(*, page: int, page_size: int, total_count: int) -> dict[str, int | bool]:
    total_pages = max((total_count + page_size - 1) // page_size, 1)
    return {
        "page": page,
        "page_size": page_size,
        "total_count": total_count,
        "total_pages": total_pages,
        "has_prev": page > 1,
        "has_next": page < total_pages,
    }


def _messages_query_params(*, page: int, status: str | None, search: str | None, page_size: int) -> dict[str, str]:
    return {
        "page": str(page),
        "page_size": str(page_size),
        "status": status or "",
        "search": search or "",
    }


def _require_user(request: Request, db: Session) -> User | RedirectResponse:
    current_user_id = get_session_user_id(request)
    if current_user_id is None:
        return RedirectResponse(url="/login", status_code=303)

    user = get_user_profile(db, current_user_id)
    if user is None:
        from app.web.deps import clear_session

        clear_session(request)
        return RedirectResponse(url="/login", status_code=303)

    if not is_valid_active_session(request, user):
        from app.web.deps import clear_session

        clear_session(request)
        return RedirectResponse(url="/login", status_code=303)

    if bool(getattr(user, "must_reset_password", False)):
        return RedirectResponse(url="/change-password", status_code=303)

    request.session[SESSION_ROLE_KEY] = user.role
    return user


@router.get("/messages")
def messages_home(request: Request, db: Session = Depends(get_db)):
    user = _require_user(request, db)
    if isinstance(user, RedirectResponse):
        return user
    has_sent_inquiries = (
        db.query(Inquiry.id).filter(Inquiry.user_id == int(user.id)).order_by(Inquiry.created_at.desc()).first()
        is not None
    )
    if has_sent_inquiries:
        return RedirectResponse(url="/messages/my", status_code=303)
    if str(user.role) in {"seller", "admin"}:
        return RedirectResponse(url="/messages/inbox", status_code=303)
    return RedirectResponse(url="/messages/my", status_code=303)


@router.get("/messages/my", response_class=HTMLResponse)
def my_messages_page(
    request: Request,
    db: Session = Depends(get_db),
    message: str | None = Query(default=None, max_length=MAX_FLASH_CHARS),
    error: str | None = Query(default=None, max_length=MAX_FLASH_CHARS),
    page: int = Query(default=1, ge=1, le=100000),
    page_size: int = Query(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    status: str | None = Query(default=None, max_length=32),
    search: str | None = Query(default=None, max_length=MAX_SEARCH_CHARS),
):
    user = _require_user(request, db)
    if isinstance(user, RedirectResponse):
        return user

    normalized_status = _normalize_status(status)
    normalized_search = _normalize_search(search)
    normalized_message = _normalize_flash(message)
    normalized_error = _normalize_flash(error)
    if normalized_status == "INVALID":
        return RedirectResponse(
            url=_append_query_params(
                "/messages/my",
                {
                    "page": "1",
                    "search": normalized_search or "",
                    "error": "Invalid status filter.",
                },
            ),
            status_code=303,
        )

    raw_rows, total_count = my_inquiries_page_use_case(
        db,
        user_id=int(user.id),
        status=normalized_status,
        search=normalized_search,
        page=page,
        page_size=page_size,
    )
    page_meta = _pagination_meta(page=page, page_size=page_size, total_count=total_count)
    total_pages = int(page_meta["total_pages"])
    if total_count > 0 and page > total_pages:
        return RedirectResponse(
            url=_append_query_params(
                "/messages/my",
                _messages_query_params(
                    page=total_pages,
                    status=normalized_status,
                    search=normalized_search,
                    page_size=page_size,
                ),
            ),
            status_code=303,
        )

    rows = [{"inquiry": inquiry, "listing": listing, "seller": seller} for inquiry, listing, seller in raw_rows]
    inquiry_ids = [int(item["inquiry"].id) for item in rows]
    thread_rows = replies_for_inquiry_ids_use_case(db, inquiry_ids=inquiry_ids, per_inquiry_limit=12)
    threads_by_inquiry: dict[int, list[dict[str, str | int | None]]] = {}
    for inquiry_id, items in thread_rows.items():
        threads_by_inquiry[inquiry_id] = [
            {
                "id": int(message.id),
                "sender_id": int(message.sender_id),
                "sender_username": str(user.username) if user is not None else None,
                "body": str(message.body),
                "created_at": message.created_at.isoformat() if message.created_at else None,
            }
            for message, user in items
        ]

    return template_response(
        request,
        "messages_my.html",
        {
            "user": user,
            "rows": rows,
            "message": normalized_message,
            "error": normalized_error,
            "can_view_inbox": str(user.role) in {"seller", "admin"},
            "active_status": normalized_status or "all",
            "active_search": normalized_search or "",
            **page_meta,
            "query_params": _messages_query_params(
                page=page,
                status=normalized_status,
                search=normalized_search,
                page_size=page_size,
            ),
            "threads_by_inquiry": threads_by_inquiry,
        },
    )


@router.get("/messages/inbox", response_class=HTMLResponse)
def seller_inbox_page(
    request: Request,
    db: Session = Depends(get_db),
    message: str | None = Query(default=None, max_length=MAX_FLASH_CHARS),
    error: str | None = Query(default=None, max_length=MAX_FLASH_CHARS),
    page: int = Query(default=1, ge=1, le=100000),
    page_size: int = Query(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    status: str | None = Query(default=None, max_length=32),
    search: str | None = Query(default=None, max_length=MAX_SEARCH_CHARS),
):
    user = _require_user(request, db)
    if isinstance(user, RedirectResponse):
        return user

    normalized_status = _normalize_status(status)
    normalized_search = _normalize_search(search)
    normalized_message = _normalize_flash(message)
    normalized_error = _normalize_flash(error)
    if normalized_status == "INVALID":
        return RedirectResponse(
            url=_append_query_params(
                "/messages/inbox",
                {
                    "page": "1",
                    "search": normalized_search or "",
                    "error": "Invalid status filter.",
                },
            ),
            status_code=303,
        )

    is_admin_inbox = str(user.role) == "admin"
    raw_rows, total_count = inbox_inquiries_page_use_case(
        db,
        actor_user_id=int(user.id),
        actor_role=str(user.role),
        status=normalized_status,
        search=normalized_search,
        page=page,
        page_size=page_size,
    )
    page_meta = _pagination_meta(page=page, page_size=page_size, total_count=total_count)
    total_pages = int(page_meta["total_pages"])
    if total_count > 0 and page > total_pages:
        return RedirectResponse(
            url=_append_query_params(
                "/messages/inbox",
                _messages_query_params(
                    page=total_pages,
                    status=normalized_status,
                    search=normalized_search,
                    page_size=page_size,
                ),
            ),
            status_code=303,
        )

    rows = [
        {
            "inquiry": inquiry,
            "listing": listing,
            "sender": sender,
            "seller": seller,
        }
        for inquiry, listing, sender, seller in raw_rows
    ]
    inquiry_ids = [int(item["inquiry"].id) for item in rows]
    thread_rows = replies_for_inquiry_ids_use_case(db, inquiry_ids=inquiry_ids, per_inquiry_limit=12)
    threads_by_inquiry: dict[int, list[dict[str, str | int | None]]] = {}
    for inquiry_id, items in thread_rows.items():
        threads_by_inquiry[inquiry_id] = [
            {
                "id": int(message.id),
                "sender_id": int(message.sender_id),
                "sender_username": str(user.username) if user is not None else None,
                "body": str(message.body),
                "created_at": message.created_at.isoformat() if message.created_at else None,
            }
            for message, user in items
        ]

    owned_count = 1 if is_admin_inbox else int(db.query(func.count(Listing.id)).filter(Listing.seller_id == int(user.id)).scalar() or 0)
    return template_response(
        request,
        "messages_inbox.html",
        {
            "user": user,
            "rows": rows,
            "owned_count": owned_count,
            "message": normalized_message,
            "error": normalized_error,
            "is_admin_inbox": is_admin_inbox,
            "status_options": sorted(ALLOWED_INQUIRY_STATUSES),
            "active_status": normalized_status or "all",
            "active_search": normalized_search or "",
            **page_meta,
            "query_params": _messages_query_params(
                page=page,
                status=normalized_status,
                search=normalized_search,
                page_size=page_size,
            ),
            "threads_by_inquiry": threads_by_inquiry,
        },
    )


@router.get("/messages/contacts/{contact_user_id}", response_class=HTMLResponse)
def message_contact_profile_page(
    request: Request,
    contact_user_id: int,
    db: Session = Depends(get_db),
    error: str | None = Query(default=None, max_length=MAX_FLASH_CHARS),
):
    user = _require_user(request, db)
    if isinstance(user, RedirectResponse):
        return user

    contact = db.query(User).filter(User.id == contact_user_id).first()
    if contact is None:
        return RedirectResponse(
            url=_append_query_params("/messages", {"error": "Contact not found."}),
            status_code=303,
        )

    if int(contact.id) != int(user.id) and str(user.role) != "admin":
        has_shared_inquiry = (
            db.query(Inquiry.id)
            .join(Listing, Listing.id == Inquiry.listing_id)
            .filter(
                or_(
                    and_(Inquiry.user_id == int(user.id), Listing.seller_id == int(contact.id)),
                    and_(Inquiry.user_id == int(contact.id), Listing.seller_id == int(user.id)),
                )
            )
            .first()
            is not None
        )
        if not has_shared_inquiry:
            return RedirectResponse(
                url=_append_query_params("/messages", {"error": "You cannot view this contact profile."}),
                status_code=303,
            )

    listing_count = db.query(Listing.id).filter(Listing.seller_id == int(contact.id)).count()
    sent_inquiries_count = db.query(Inquiry.id).filter(Inquiry.user_id == int(contact.id)).count()
    received_inquiries_count = (
        db.query(Inquiry.id).join(Listing, Listing.id == Inquiry.listing_id).filter(Listing.seller_id == int(contact.id)).count()
    )

    shared_inquiries_query = (
        db.query(Inquiry)
        .join(Listing, Listing.id == Inquiry.listing_id)
        .filter(
            or_(
                and_(Inquiry.user_id == int(user.id), Listing.seller_id == int(contact.id)),
                and_(Inquiry.user_id == int(contact.id), Listing.seller_id == int(user.id)),
            )
        )
        .order_by(Inquiry.created_at.desc())
    )
    if str(user.role) == "admin":
        shared_inquiries_query = (
            db.query(Inquiry)
            .join(Listing, Listing.id == Inquiry.listing_id)
            .filter((Inquiry.user_id == int(contact.id)) | (Listing.seller_id == int(contact.id)))
            .order_by(Inquiry.created_at.desc())
        )

    shared_inquiries = shared_inquiries_query.limit(10).all()
    shared_listing_ids = list({int(item.listing_id) for item in shared_inquiries})
    shared_listings = db.query(Listing).filter(Listing.id.in_(shared_listing_ids)).all() if shared_listing_ids else []
    shared_listing_map = {int(item.id): item for item in shared_listings}

    return template_response(
        request,
        "messages_contact.html",
        {
            "user": user,
            "contact": contact,
            "listing_count": listing_count,
            "sent_inquiries_count": sent_inquiries_count,
            "received_inquiries_count": received_inquiries_count,
            "shared_rows": [
                {"inquiry": item, "listing": shared_listing_map.get(int(item.listing_id))}
                for item in shared_inquiries
            ],
            "error": _normalize_flash(error),
        },
    )


@router.post("/messages/{inquiry_id}/status")
def update_message_status(
    request: Request,
    inquiry_id: int,
    status: str = Form(...),
    csrf_token: str = Form(...),
    next_path: str | None = Form(default="/messages/inbox"),
    db: Session = Depends(get_db),
):
    user = _require_user(request, db)
    if isinstance(user, RedirectResponse):
        return user

    redirect_target = _resolve_redirect_target(next_path, "/messages/inbox", request=request)

    if not is_valid_csrf(request, csrf_token):
        return RedirectResponse(
            url=_append_query_params(redirect_target, {"error": "Invalid CSRF token."}),
            status_code=303,
        )
    if is_rate_limited(
        db,
        request,
        "message_status_web",
        str(int(user.id)),
        MESSAGE_STATUS_RATE_LIMIT_PER_MINUTE,
    ):
        return RedirectResponse(
            url=_append_query_params(redirect_target, {"error": "Too many status updates. Please wait a minute."}),
            status_code=303,
        )

    normalized_status = status.strip().lower()
    if normalized_status not in ALLOWED_INQUIRY_STATUSES:
        return RedirectResponse(
            url=_append_query_params(redirect_target, {"error": "Invalid inquiry status."}),
            status_code=303,
        )

    try:
        update_inquiry_status_use_case(
            db,
            inquiry_id=inquiry_id,
            status=normalized_status,
            actor_user_id=int(user.id),
            actor_role=str(user.role),
        )
    except InquiryNotFoundError:
        return RedirectResponse(
            url=_append_query_params(redirect_target, {"error": "Inquiry not found."}),
            status_code=303,
        )
    except (PermissionDeniedError, ListingNotFoundError):
        return RedirectResponse(
            url=_append_query_params(redirect_target, {"error": "You cannot update this inquiry."}),
            status_code=303,
        )

    return RedirectResponse(
        url=_append_query_params(redirect_target, {"message": "Inquiry status updated."}),
        status_code=303,
    )


@router.post("/messages/{inquiry_id}/reply")
def add_message_reply(
    request: Request,
    inquiry_id: int,
    body: str = Form(default=""),
    csrf_token: str = Form(...),
    next_path: str | None = Form(default="/messages"),
    db: Session = Depends(get_db),
):
    user = _require_user(request, db)
    if isinstance(user, RedirectResponse):
        return user

    redirect_target = _resolve_redirect_target(next_path, "/messages", request=request)
    if not is_valid_csrf(request, csrf_token):
        return RedirectResponse(
            url=_append_query_params(redirect_target, {"error": "Invalid CSRF token."}),
            status_code=303,
        )
    if is_rate_limited(
        db,
        request,
        "message_reply_web",
        str(int(user.id)),
        MESSAGE_REPLY_RATE_LIMIT_PER_MINUTE,
    ):
        return RedirectResponse(
            url=_append_query_params(redirect_target, {"error": "Too many reply attempts. Please wait a minute."}),
            status_code=303,
        )

    try:
        add_inquiry_reply_use_case(
            db,
            inquiry_id=inquiry_id,
            sender_user_id=int(user.id),
            sender_role=str(user.role),
            body=body,
        )
    except InquiryNotFoundError:
        return RedirectResponse(
            url=_append_query_params(redirect_target, {"error": "Inquiry not found."}),
            status_code=303,
        )
    except ListingNotFoundError:
        return RedirectResponse(
            url=_append_query_params(redirect_target, {"error": "Listing not found."}),
            status_code=303,
        )
    except PermissionDeniedError:
        return RedirectResponse(
            url=_append_query_params(redirect_target, {"error": "You cannot reply to this inquiry."}),
            status_code=303,
        )
    except ValueError as exc:
        return RedirectResponse(
            url=_append_query_params(redirect_target, {"error": str(exc)}),
            status_code=303,
        )

    logger.info(
        "Inquiry reply created",
        extra={
            "inquiry_id": inquiry_id,
            "actor_user_id": int(user.id),
            "role": str(user.role),
            "request_id": getattr(request.state, "request_id", None),
        },
    )
    record_message_reply()
    return RedirectResponse(
        url=_append_query_params(redirect_target, {"message": "Reply sent."}),
        status_code=303,
    )


@router.get("/messages/{inquiry_id}/events")
def message_events(
    request: Request,
    inquiry_id: int,
    db: Session = Depends(get_db),
    after_id: int = Query(default=0, ge=0),
    limit: int = Query(default=25, ge=1, le=100),
):
    user = _require_user(request, db)
    if isinstance(user, RedirectResponse):
        return JSONResponse(status_code=401, content={"detail": "Unauthorized"})
    if is_rate_limited(
        db,
        request,
        "message_poll_web",
        str(int(user.id)),
        MESSAGE_POLL_RATE_LIMIT_PER_MINUTE,
    ):
        return JSONResponse(status_code=429, content={"detail": "Too many requests"})
    try:
        replies = inquiry_replies_use_case(
            db,
            inquiry_id=inquiry_id,
            actor_user_id=int(user.id),
            actor_role=str(user.role),
            after_id=after_id,
            limit=limit,
        )
    except InquiryNotFoundError:
        return JSONResponse(status_code=404, content={"detail": "Inquiry not found"})
    except ListingNotFoundError:
        return JSONResponse(status_code=404, content={"detail": "Listing not found"})
    except PermissionDeniedError:
        return JSONResponse(status_code=403, content={"detail": "Permission denied"})
    record_message_poll()
    return {
        "inquiry_id": inquiry_id,
        "items": [
            {
                "id": int(message.id),
                "sender_id": int(message.sender_id),
                "sender_username": str(sender.username) if sender is not None else None,
                "body": str(message.body),
                "created_at": message.created_at.isoformat() if message.created_at else None,
            }
            for message, sender in replies
        ],
    }
