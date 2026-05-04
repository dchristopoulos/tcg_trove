from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_user
from app.db.models.inquiry_message import InquiryMessage
from app.db.models.user import User
from app.db.session import get_db
from app.managers.user_manager import delete_user
from app.schemas.gdpr import DetailResponse, GDPRExportResponse
from app.services.favorite_service import list_favorites
from app.services.inquiry_service import my_inquiries_use_case
from app.services.reservation_service import my_reservations_use_case

router = APIRouter(prefix="/gdpr", tags=["gdpr"])


@router.get("/export-me", response_model=GDPRExportResponse)
def export_my_data(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    favorites = list_favorites(db, user_id=current_user.id)
    inquiries = my_inquiries_use_case(db, user_id=current_user.id)
    reservations = my_reservations_use_case(db, user_id=current_user.id)
    inquiry_messages = db.query(InquiryMessage).filter(InquiryMessage.sender_id == current_user.id).all()
    return {
        "user": {
            "id": current_user.id,
            "email": current_user.email,
            "username": current_user.username,
            "role": current_user.role,
        },
        "favorites": [item.id for item in favorites],
        "inquiries": [item.id for item in inquiries],
        "inquiry_messages": [item.id for item in inquiry_messages],
        "reservations": [item.id for item in reservations],
    }


@router.delete("/delete-me", response_model=DetailResponse)
def delete_my_data(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    delete_user(db, current_user)
    return {"detail": "User data deleted"}
