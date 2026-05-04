# app/api/v1/routers/listings.py
from fastapi import APIRouter, Depends, Query
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_user, require_permission
from app.core.exceptions import InvalidFilterError, SellerNotFoundError, PermissionDeniedError
from app.core.utils import parse_listing_ids
from app.db.models.user import User
from app.db.session import get_db
from app.managers.user_manager import get_user_by_id
from app.schemas.listing import (
    ListingCompareRead,
    ListingCreate,
    ListingFilter,
    ListingMarketPulseRead,
    ListingPageRead,
    ListingPriceHistoryRead,
    ListingRead,
    ListingRecommendationsRead,
    ListingSummaryRead,
)
from app.services.authz_service import has_permission
from app.services.listing_service import (
    compare_listings_use_case,
    create_listing_use_case,
    get_listing_use_case,
    list_listings_use_case,
    listing_market_pulse_use_case,
    listing_summary_use_case,
    recommend_listings_use_case,
    remove_listing_use_case,
    search_listings_paginated_use_case,
    search_listings_use_case,
    similar_listings_use_case,
)

router = APIRouter(prefix="/listings", tags=["listings"])


def _safe_listing_filter(**kwargs) -> ListingFilter:
    try:
        return ListingFilter(**kwargs)
    except ValidationError as err:
        raise InvalidFilterError from err


def _parse_optional_int_query(value: str | None) -> int | None:
    if value is None:
        return None
    raw = value.strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError as err:
        raise InvalidFilterError from err


@router.post("/", response_model=ListingRead)
def create_listing_endpoint(
    listing_in: ListingCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    can_manage_all = has_permission(
        current_user.role,
        "manage_listings",
        current_user.permission_grants,
        current_user.permission_revokes,
    )
    if current_user.id != listing_in.seller_id and not can_manage_all:
        raise PermissionDeniedError

    seller = get_user_by_id(db, listing_in.seller_id)
    if seller is None:
        raise SellerNotFoundError
    if not has_permission(
        seller.role,
        "manage_own_listings",
        seller.permission_grants,
        seller.permission_revokes,
    ):
        raise PermissionDeniedError
    return create_listing_use_case(db, listing_in)


@router.get("/", response_model=list[ListingRead])
def list_listings_endpoint(
    min_price: str | None = Query(default=None),
    max_price: str | None = Query(default=None),
    min_size: str | None = Query(default=None),
    max_size: str | None = Query(default=None),
    min_bedrooms: str | None = Query(default=None),
    max_bedrooms: str | None = Query(default=None),
    min_bathrooms: str | None = Query(default=None),
    max_bathrooms: str | None = Query(default=None),
    property_type: str | None = Query(default=None),
    furnished: str | None = Query(default=None),
    location: str | None = Query(default=None),
    query: str | None = Query(default=None),
    sort_by: str | None = Query(default=None),
    sort_order: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    parsed_min_price = _parse_optional_int_query(min_price)
    parsed_max_price = _parse_optional_int_query(max_price)
    parsed_min_size = _parse_optional_int_query(min_size)
    parsed_max_size = _parse_optional_int_query(max_size)
    parsed_min_bedrooms = _parse_optional_int_query(min_bedrooms)
    parsed_max_bedrooms = _parse_optional_int_query(max_bedrooms)
    parsed_min_bathrooms = _parse_optional_int_query(min_bathrooms)
    parsed_max_bathrooms = _parse_optional_int_query(max_bathrooms)

    if any(
        value is not None
        for value in [
            parsed_min_price,
            parsed_max_price,
            parsed_min_size,
            parsed_max_size,
            parsed_min_bedrooms,
            parsed_max_bedrooms,
            parsed_min_bathrooms,
            parsed_max_bathrooms,
            property_type,
            furnished,
            location,
            query,
            sort_by,
            sort_order,
        ]
    ):
        return search_listings_use_case(
            db,
            _safe_listing_filter(
                min_price=parsed_min_price,
                max_price=parsed_max_price,
                min_size=parsed_min_size,
                max_size=parsed_max_size,
                min_bedrooms=parsed_min_bedrooms,
                max_bedrooms=parsed_max_bedrooms,
                min_bathrooms=parsed_min_bathrooms,
                max_bathrooms=parsed_max_bathrooms,
                property_type=property_type,
                furnished=furnished,
                location=location,
                query=query,
                sort_by=sort_by,
                sort_order=sort_order,
            ),
        )
    return list_listings_use_case(db)


@router.get("/summary/stats", response_model=ListingSummaryRead)
def listings_summary_endpoint(
    min_price: str | None = Query(default=None),
    max_price: str | None = Query(default=None),
    min_size: str | None = Query(default=None),
    max_size: str | None = Query(default=None),
    min_bedrooms: str | None = Query(default=None),
    max_bedrooms: str | None = Query(default=None),
    min_bathrooms: str | None = Query(default=None),
    max_bathrooms: str | None = Query(default=None),
    property_type: str | None = Query(default=None),
    furnished: str | None = Query(default=None),
    location: str | None = Query(default=None),
    query: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    return listing_summary_use_case(
        db,
        _safe_listing_filter(
            min_price=_parse_optional_int_query(min_price),
            max_price=_parse_optional_int_query(max_price),
            min_size=_parse_optional_int_query(min_size),
            max_size=_parse_optional_int_query(max_size),
            min_bedrooms=_parse_optional_int_query(min_bedrooms),
            max_bedrooms=_parse_optional_int_query(max_bedrooms),
            min_bathrooms=_parse_optional_int_query(min_bathrooms),
            max_bathrooms=_parse_optional_int_query(max_bathrooms),
            property_type=property_type,
            furnished=furnished,
            location=location,
            query=query,
        ),
    )


@router.get("/market/pulse", response_model=ListingMarketPulseRead)
def listings_market_pulse_endpoint(db: Session = Depends(get_db)):
    return listing_market_pulse_use_case(db)


@router.get("/compare", response_model=ListingCompareRead)
def compare_listings_endpoint(
    ids: str = Query(..., description="Comma-separated listing IDs, e.g. 1,2,3"),
    db: Session = Depends(get_db),
):
    try:
        parsed_ids = parse_listing_ids(ids)
    except ValueError as err:
        raise InvalidFilterError from err
    return compare_listings_use_case(db, parsed_ids)


@router.get("/recommendations", response_model=ListingRecommendationsRead)
def recommendations_endpoint(
    user_id: int = Query(..., ge=1),
    limit: int = Query(6, ge=1, le=20),
    db: Session = Depends(get_db),
):
    return recommend_listings_use_case(db, user_id=user_id, limit=limit)


@router.get("/{listing_id}/similar", response_model=list[ListingRead])
def similar_listings_endpoint(listing_id: int, db: Session = Depends(get_db)):
    return similar_listings_use_case(db, listing_id)


@router.get("/search/page", response_model=ListingPageRead)
def paginated_search_listings_endpoint(
    min_price: str | None = Query(default=None),
    max_price: str | None = Query(default=None),
    min_size: str | None = Query(default=None),
    max_size: str | None = Query(default=None),
    min_bedrooms: str | None = Query(default=None),
    max_bedrooms: str | None = Query(default=None),
    min_bathrooms: str | None = Query(default=None),
    max_bathrooms: str | None = Query(default=None),
    property_type: str | None = Query(default=None),
    furnished: str | None = Query(default=None),
    location: str | None = Query(default=None),
    query: str | None = Query(default=None),
    sort_by: str | None = Query(default=None),
    sort_order: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=12, ge=1, le=100),
    db: Session = Depends(get_db),
):
    return search_listings_paginated_use_case(
        db,
        _safe_listing_filter(
            min_price=_parse_optional_int_query(min_price),
            max_price=_parse_optional_int_query(max_price),
            min_size=_parse_optional_int_query(min_size),
            max_size=_parse_optional_int_query(max_size),
            min_bedrooms=_parse_optional_int_query(min_bedrooms),
            max_bedrooms=_parse_optional_int_query(max_bedrooms),
            min_bathrooms=_parse_optional_int_query(min_bathrooms),
            max_bathrooms=_parse_optional_int_query(max_bathrooms),
            property_type=property_type,
            furnished=furnished,
            location=location,
            query=query,
            sort_by=sort_by,
            sort_order=sort_order,
        ),
        page=page,
        page_size=page_size,
    )


@router.get("/{listing_id}", response_model=ListingRead)
def get_listing_endpoint(listing_id: int, db: Session = Depends(get_db)):
    return get_listing_use_case(db, listing_id)


@router.get("/{listing_id}/price-history", response_model=list[ListingPriceHistoryRead])
def get_listing_price_history_endpoint(listing_id: int, db: Session = Depends(get_db)):
    from app.managers.listing_manager import get_listing_price_history
    history = get_listing_price_history(db, listing_id)
    return [{"price": h.price, "changed_at": h.changed_at} for h in history]


@router.delete("/{listing_id}", response_model=dict[str, str])
def remove_listing_endpoint(
    listing_id: int,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_permission("manage_listings")),
):
    remove_listing_use_case(db, listing_id, actor_user_id=admin_user.id)
    return {"detail": "Listing removed"}
