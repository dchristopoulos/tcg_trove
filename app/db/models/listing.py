from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import relationship

from app.db.base import Base


class Listing(Base):
    __tablename__ = "listings"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    price = Column(Integer, nullable=False, index=True)
    location = Column(String, nullable=False, index=True)
    size = Column(Integer, nullable=False)
    image_url = Column(String, nullable=False)
    bedrooms = Column(Integer, nullable=False)
    bathrooms = Column(Integer, nullable=False)
    property_type = Column(String, nullable=False, index=True)
    furnished = Column(String, nullable=False)
    description = Column(String, nullable=False)
    seller_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    seller = relationship("User", back_populates="listings")
    favorites = relationship("Favorite", back_populates="listing", cascade="all, delete-orphan")
    inquiries = relationship("Inquiry", back_populates="listing", cascade="all, delete-orphan")
    reservations = relationship("Reservation", back_populates="listing", cascade="all, delete-orphan")
    viewings = relationship("Viewing", back_populates="listing", cascade="all, delete-orphan")
    price_history = relationship("ListingPriceHistory", back_populates="listing", cascade="all, delete-orphan")


class ListingPriceHistory(Base):
    __tablename__ = "listing_price_history"

    id = Column(Integer, primary_key=True, index=True)
    listing_id = Column(Integer, ForeignKey("listings.id"), nullable=False)
    price = Column(Integer, nullable=False)
    changed_at = Column(DateTime, nullable=False, server_default=func.now())

    listing = relationship("Listing", back_populates="price_history")
