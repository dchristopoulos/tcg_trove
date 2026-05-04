from sqlalchemy import func, or_
from sqlalchemy.orm import Session, aliased

from app.db.models.inquiry import Inquiry
from app.db.models.inquiry_message import InquiryMessage
from app.db.models.listing import Listing
from app.db.models.user import User
from app.schemas.status import InquiryStatus


def create_inquiry(db: Session, *, user_id: int, listing_id: int, message: str) -> Inquiry:
    inquiry = Inquiry(user_id=user_id, listing_id=listing_id, message=message)
    db.add(inquiry)
    db.commit()
    db.refresh(inquiry)
    return inquiry


def list_inquiries_for_user(db: Session, user_id: int) -> list[Inquiry]:
    return db.query(Inquiry).filter(Inquiry.user_id == user_id).all()


def list_inquiries_for_listing(db: Session, listing_id: int) -> list[Inquiry]:
    return db.query(Inquiry).filter(Inquiry.listing_id == listing_id).all()


def list_all_inquiries(db: Session) -> list[Inquiry]:
    return db.query(Inquiry).all()


def get_inquiry_by_id(db: Session, inquiry_id: int) -> Inquiry | None:
    return db.query(Inquiry).filter(Inquiry.id == inquiry_id).first()


def update_inquiry_status(db: Session, inquiry: Inquiry, status: InquiryStatus) -> Inquiry:
    inquiry.status = status.value
    db.add(inquiry)
    db.commit()
    db.refresh(inquiry)
    return inquiry


def list_inquiry_rows_for_user(
    db: Session,
    *,
    user_id: int,
    status: str | None = None,
    search: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[tuple[Inquiry, Listing | None, User | None]], int]:
    query = (
        db.query(Inquiry, Listing, User)
        .outerjoin(Listing, Listing.id == Inquiry.listing_id)
        .outerjoin(User, User.id == Listing.seller_id)
        .filter(Inquiry.user_id == user_id)
    )
    if status:
        query = query.filter(Inquiry.status == status)
    if search:
        like = f"%{search}%"
        query = query.filter(
            or_(
                Inquiry.message.ilike(like),
                Listing.title.ilike(like),
                Listing.location.ilike(like),
                User.username.ilike(like),
            )
        )

    total_count = int(query.with_entities(func.count(Inquiry.id)).scalar() or 0)
    rows = (
        query.order_by(Inquiry.created_at.desc(), Inquiry.id.desc())
        .offset(max(page - 1, 0) * page_size)
        .limit(page_size)
        .all()
    )
    return rows, total_count


def list_inquiry_rows_for_inbox(
    db: Session,
    *,
    actor_user_id: int,
    actor_role: str,
    status: str | None = None,
    search: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[tuple[Inquiry, Listing | None, User | None, User | None]], int]:
    sender_alias = aliased(User)
    seller_alias = aliased(User)

    query = (
        db.query(Inquiry, Listing, sender_alias, seller_alias)
        .outerjoin(Listing, Listing.id == Inquiry.listing_id)
        .outerjoin(sender_alias, sender_alias.id == Inquiry.user_id)
        .outerjoin(seller_alias, seller_alias.id == Listing.seller_id)
    )
    if actor_role != "admin":
        query = query.filter(Listing.seller_id == actor_user_id)
    if status:
        query = query.filter(Inquiry.status == status)
    if search:
        like = f"%{search}%"
        query = query.filter(
            or_(
                Inquiry.message.ilike(like),
                Listing.title.ilike(like),
                Listing.location.ilike(like),
                sender_alias.username.ilike(like),
                seller_alias.username.ilike(like),
            )
        )

    total_count = int(query.with_entities(func.count(Inquiry.id)).scalar() or 0)
    rows = (
        query.order_by(Inquiry.created_at.desc(), Inquiry.id.desc())
        .offset(max(page - 1, 0) * page_size)
        .limit(page_size)
        .all()
    )
    return rows, total_count


def create_inquiry_message(
    db: Session,
    *,
    inquiry_id: int,
    sender_id: int,
    body: str,
) -> InquiryMessage:
    message = InquiryMessage(inquiry_id=inquiry_id, sender_id=sender_id, body=body)
    db.add(message)
    db.commit()
    db.refresh(message)
    return message


def list_inquiry_messages_for_inquiry(
    db: Session,
    *,
    inquiry_id: int,
    after_id: int = 0,
    limit: int = 50,
) -> list[tuple[InquiryMessage, User | None]]:
    return (
        db.query(InquiryMessage, User)
        .outerjoin(User, User.id == InquiryMessage.sender_id)
        .filter(InquiryMessage.inquiry_id == inquiry_id, InquiryMessage.id > after_id)
        .order_by(InquiryMessage.created_at.asc(), InquiryMessage.id.asc())
        .limit(limit)
        .all()
    )


def list_inquiry_messages_for_inquiry_ids(
    db: Session,
    *,
    inquiry_ids: list[int],
    per_inquiry_limit: int = 12,
) -> dict[int, list[tuple[InquiryMessage, User | None]]]:
    if not inquiry_ids:
        return {}
    rows = (
        db.query(InquiryMessage, User)
        .outerjoin(User, User.id == InquiryMessage.sender_id)
        .filter(InquiryMessage.inquiry_id.in_(inquiry_ids))
        .order_by(InquiryMessage.created_at.desc(), InquiryMessage.id.desc())
        .all()
    )
    grouped: dict[int, list[tuple[InquiryMessage, User | None]]] = {}
    for row in rows:
        msg = row[0]
        group = grouped.setdefault(int(msg.inquiry_id), [])
        if len(group) < per_inquiry_limit:
            group.append(row)
    for inquiry_id in list(grouped.keys()):
        grouped[inquiry_id] = sorted(grouped[inquiry_id], key=lambda item: (item[0].created_at, item[0].id))
    return grouped
