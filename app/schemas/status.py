from enum import StrEnum


class ReservationStatus(StrEnum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


class InquiryStatus(StrEnum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESPONDED = "responded"
    CLOSED = "closed"


ALLOWED_RESERVATION_TRANSITIONS: dict[ReservationStatus, set[ReservationStatus]] = {
    ReservationStatus.PENDING: {ReservationStatus.CONFIRMED, ReservationStatus.CANCELLED, ReservationStatus.REJECTED},
    ReservationStatus.CONFIRMED: {ReservationStatus.CANCELLED},
    ReservationStatus.CANCELLED: set(),
    ReservationStatus.REJECTED: set(),
}

ALLOWED_INQUIRY_TRANSITIONS: dict[InquiryStatus, set[InquiryStatus]] = {
    InquiryStatus.OPEN: {InquiryStatus.IN_PROGRESS, InquiryStatus.RESPONDED, InquiryStatus.CLOSED},
    InquiryStatus.IN_PROGRESS: {InquiryStatus.RESPONDED, InquiryStatus.CLOSED},
    InquiryStatus.RESPONDED: {InquiryStatus.CLOSED},
    InquiryStatus.CLOSED: set(),
}
