from sqlalchemy import Boolean, Column, DateTime, Integer, String
from sqlalchemy.orm import relationship

from app.db.base import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    username = Column(String, unique=True, index=True, nullable=False)
    password = Column(String, nullable=False)
    role = Column(String, nullable=False, default="buyer")
    permission_grants = Column(String, nullable=True)
    permission_revokes = Column(String, nullable=True)
    email_verified = Column(Boolean, nullable=False, default=False)
    active_session_token = Column(String, nullable=True)
    active_session_expires_at = Column(DateTime(timezone=True), nullable=True)
    must_reset_password = Column(Boolean, nullable=False, default=False)
    balance = Column(Integer, nullable=False, default=0)

    listings = relationship("Listing", back_populates="seller", cascade="all, delete-orphan")
    orders = relationship("Order", foreign_keys="Order.buyer_id", back_populates="buyer", cascade="all, delete-orphan")
    favorites = relationship("Favorite", back_populates="user", cascade="all, delete-orphan")
    inquiries = relationship("Inquiry", back_populates="user", cascade="all, delete-orphan")
    reservations = relationship("Reservation", back_populates="user", cascade="all, delete-orphan")
    viewings = relationship("Viewing", back_populates="user", cascade="all, delete-orphan")
    search_logs = relationship("SearchLog", back_populates="user", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="actor", cascade="all, delete-orphan")
    inquiry_messages = relationship("InquiryMessage", back_populates="sender", cascade="all, delete-orphan")
