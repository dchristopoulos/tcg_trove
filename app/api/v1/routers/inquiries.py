from typing import Any, cast

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_user
from app.core.exceptions import InquiryNotFoundError, ListingNotFoundError, PermissionDeniedError
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.inquiry import (
    InquiryCreate,
    InquiryRead,
    InquiryReplyCreate,
    InquiryReplyRead,
    InquiryStatusUpdate,
)
from app.services.inquiry_service import (
    add_inquiry_reply_use_case,
    create_inquiry_use_case,
    inquiry_replies_use_case,
    listing_inquiries_use_case,
    my_inquiries_use_case,
    update_inquiry_status_use_case,
)

router = APIRouter(prefix="/inquiries", tags=["inquiries"])


@router.post("/", response_model=InquiryRead)
def create_inquiry_endpoint(
    payload: InquiryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return create_inquiry_use_case(
        db,
        user_id=int(cast(Any, current_user.id)),
        listing_id=payload.listing_id,
        message=payload.message,
    )


@router.get("/me", response_model=list[InquiryRead])
def my_inquiries_endpoint(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return my_inquiries_use_case(db, user_id=int(cast(Any, current_user.id)))


@router.get("/listing/{listing_id}", response_model=list[InquiryRead])
def listing_inquiries_endpoint(
    listing_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return listing_inquiries_use_case(
        db,
        listing_id=listing_id,
        actor_user_id=int(cast(Any, current_user.id)),
        actor_role=str(cast(Any, current_user.role)),
    )


@router.put("/{inquiry_id}", response_model=InquiryRead)
def update_inquiry_status_endpoint(
    inquiry_id: int,
    payload: InquiryStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return update_inquiry_status_use_case(
        db,
        inquiry_id=inquiry_id,
        status=payload.status,
        actor_user_id=int(cast(Any, current_user.id)),
        actor_role=str(cast(Any, current_user.role)),
    )


@router.get("/{inquiry_id}/messages", response_model=list[InquiryReplyRead])
def list_inquiry_messages_endpoint(
    inquiry_id: int,
    after_id: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    try:
        rows = inquiry_replies_use_case(
            db,
            inquiry_id=inquiry_id,
            actor_user_id=int(cast(Any, actor.id)),
            actor_role=str(cast(Any, actor.role)),
            after_id=after_id,
            limit=limit,
        )
    except InquiryNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Inquiry not found") from exc
    except ListingNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Listing not found") from exc
    except PermissionDeniedError as exc:
        raise HTTPException(status_code=403, detail="Permission denied") from exc
    return [
        {
            "id": int(message.id),
            "inquiry_id": int(message.inquiry_id),
            "sender_id": int(message.sender_id),
            "sender_username": str(user.username) if user is not None else None,
            "body": str(message.body),
            "created_at": message.created_at,
        }
        for message, user in rows
    ]


@router.post("/{inquiry_id}/messages", response_model=InquiryReplyRead)
def post_inquiry_message_endpoint(
    inquiry_id: int,
    payload: InquiryReplyCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
):
    try:
        reply = add_inquiry_reply_use_case(
            db,
            inquiry_id=inquiry_id,
            sender_user_id=int(cast(Any, actor.id)),
            sender_role=str(cast(Any, actor.role)),
            body=payload.body,
        )
    except InquiryNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Inquiry not found") from exc
    except ListingNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Listing not found") from exc
    except PermissionDeniedError as exc:
        raise HTTPException(status_code=403, detail="Permission denied") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "id": int(reply.id),
        "inquiry_id": int(reply.inquiry_id),
        "sender_id": int(reply.sender_id),
        "sender_username": str(cast(Any, actor.username)),
        "body": str(reply.body),
        "created_at": reply.created_at,
    }
