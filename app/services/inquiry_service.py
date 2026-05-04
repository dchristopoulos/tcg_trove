import logging
from typing import Any, cast

from sqlalchemy.orm import Session

from app.core.exceptions import (
    InquiryNotFoundError,
    InvalidStatusTransitionError,
    ListingNotFoundError,
    PermissionDeniedError,
)
from app.db.models.inquiry import Inquiry
from app.db.models.inquiry_message import InquiryMessage
from app.managers.inquiry_manager import (
    create_inquiry,
    create_inquiry_message,
    get_inquiry_by_id,
    list_all_inquiries,
    list_inquiries_for_listing,
    list_inquiries_for_user,
    list_inquiry_messages_for_inquiry,
    list_inquiry_messages_for_inquiry_ids,
    list_inquiry_rows_for_inbox,
    list_inquiry_rows_for_user,
    update_inquiry_status,
)
from app.managers.listing_manager import get_listing_by_id
from app.managers.user_manager import get_user_by_id
from app.schemas.status import ALLOWED_INQUIRY_TRANSITIONS, InquiryStatus
from app.services.email_service import send_confirmation_email

logger = logging.getLogger("tcg_trove.inquiries")


def create_inquiry_use_case(db: Session, *, user_id: int, listing_id: int, message: str) -> Inquiry:
    listing = get_listing_by_id(db, listing_id)
    if listing is None:
        raise ListingNotFoundError
    inquiry = create_inquiry(db, user_id=user_id, listing_id=listing_id, message=message)
    user = get_user_by_id(db, user_id)
    if user is not None:
        try:
            send_confirmation_email(
                to=str(user.email),
                event_name="Inquiry received",
                details=f"Your inquiry for listing {listing_id} has been recorded.",
            )
        except Exception:
            logger.exception("Failed to enqueue inquiry confirmation email", extra={"listing_id": listing_id})
    return inquiry


def my_inquiries_use_case(db: Session, *, user_id: int) -> list[Inquiry]:
    return list_inquiries_for_user(db, user_id)


def listing_inquiries_use_case(db: Session, *, listing_id: int, actor_user_id: int, actor_role: str) -> list[Inquiry]:
    listing = get_listing_by_id(db, listing_id)
    if listing is None:
        raise ListingNotFoundError
    listing_seller_id = int(cast(Any, listing.seller_id))
    if actor_role != "admin" and actor_user_id != listing_seller_id:
        raise PermissionDeniedError
    return list_inquiries_for_listing(db, listing_id)


def update_inquiry_status_use_case(
    db: Session,
    *,
    inquiry_id: int,
    status: InquiryStatus | str,
    actor_user_id: int,
    actor_role: str,
) -> Inquiry:
    inquiry = get_inquiry_by_id(db, inquiry_id)
    if inquiry is None:
        raise InquiryNotFoundError
    listing = get_listing_by_id(db, int(cast(Any, inquiry.listing_id)))
    if listing is None:
        raise ListingNotFoundError
    listing_seller_id = int(cast(Any, listing.seller_id))
    if actor_role != "admin" and actor_user_id != listing_seller_id:
        raise PermissionDeniedError
    try:
        requested_status = status if isinstance(status, InquiryStatus) else InquiryStatus(str(status))
        current_status = InquiryStatus(str(cast(Any, inquiry.status)))
    except ValueError as err:
        raise InvalidStatusTransitionError from err
    if requested_status != current_status and requested_status not in ALLOWED_INQUIRY_TRANSITIONS[current_status]:
        raise InvalidStatusTransitionError
    return update_inquiry_status(db, inquiry, requested_status)


def all_inquiries_use_case(db: Session) -> list[Inquiry]:
    return list_all_inquiries(db)


def _is_inquiry_participant(
    *,
    inquiry: Inquiry,
    listing_seller_id: int,
    actor_user_id: int,
    actor_role: str,
) -> bool:
    if actor_role == "admin":
        return True
    if actor_user_id == int(cast(Any, inquiry.user_id)):
        return True
    if actor_user_id == int(listing_seller_id):
        return True
    return False


def add_inquiry_reply_use_case(
    db: Session,
    *,
    inquiry_id: int,
    sender_user_id: int,
    sender_role: str,
    body: str,
) -> InquiryMessage:
    inquiry = get_inquiry_by_id(db, inquiry_id)
    if inquiry is None:
        raise InquiryNotFoundError
    listing = get_listing_by_id(db, int(cast(Any, inquiry.listing_id)))
    if listing is None:
        raise ListingNotFoundError
    listing_seller_id = int(cast(Any, listing.seller_id))
    if not _is_inquiry_participant(
        inquiry=inquiry,
        listing_seller_id=listing_seller_id,
        actor_user_id=sender_user_id,
        actor_role=sender_role,
    ):
        raise PermissionDeniedError
    clean = " ".join(body.split()).strip()
    if len(clean) < 2:
        raise ValueError("Reply is too short.")
    if len(clean) > 2000:
        raise ValueError("Reply is too long.")
    return create_inquiry_message(
        db,
        inquiry_id=inquiry_id,
        sender_id=sender_user_id,
        body=clean,
    )


def inquiry_replies_use_case(
    db: Session,
    *,
    inquiry_id: int,
    actor_user_id: int,
    actor_role: str,
    after_id: int = 0,
    limit: int = 50,
) -> list[tuple[InquiryMessage, Any | None]]:
    inquiry = get_inquiry_by_id(db, inquiry_id)
    if inquiry is None:
        raise InquiryNotFoundError
    listing = get_listing_by_id(db, int(cast(Any, inquiry.listing_id)))
    if listing is None:
        raise ListingNotFoundError
    if not _is_inquiry_participant(
        inquiry=inquiry,
        listing_seller_id=int(cast(Any, listing.seller_id)),
        actor_user_id=actor_user_id,
        actor_role=actor_role,
    ):
        raise PermissionDeniedError
    bounded_limit = max(1, min(int(limit), 100))
    safe_after_id = max(0, int(after_id))
    return list_inquiry_messages_for_inquiry(
        db,
        inquiry_id=inquiry_id,
        after_id=safe_after_id,
        limit=bounded_limit,
    )


def replies_for_inquiry_ids_use_case(
    db: Session,
    *,
    inquiry_ids: list[int],
    per_inquiry_limit: int = 12,
) -> dict[int, list[tuple[InquiryMessage, Any | None]]]:
    return list_inquiry_messages_for_inquiry_ids(
        db,
        inquiry_ids=inquiry_ids,
        per_inquiry_limit=max(1, min(int(per_inquiry_limit), 50)),
    )


def my_inquiries_page_use_case(
    db: Session,
    *,
    user_id: int,
    status: str | None = None,
    search: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[tuple[Inquiry, Any | None, Any | None]], int]:
    rows, total_count = list_inquiry_rows_for_user(
        db,
        user_id=user_id,
        status=status,
        search=search,
        page=page,
        page_size=page_size,
    )
    return rows, total_count


def inbox_inquiries_page_use_case(
    db: Session,
    *,
    actor_user_id: int,
    actor_role: str,
    status: str | None = None,
    search: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[tuple[Inquiry, Any | None, Any | None, Any | None]], int]:
    rows, total_count = list_inquiry_rows_for_inbox(
        db,
        actor_user_id=actor_user_id,
        actor_role=actor_role,
        status=status,
        search=search,
        page=page,
        page_size=page_size,
    )
    return rows, total_count
