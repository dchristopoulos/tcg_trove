from fastapi import APIRouter, Depends, Query
from pydantic import ValidationError
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.v1.deps import require_permission
from app.core.exceptions import InvalidFilterError
from app.db.models.listing import Listing
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.listing import ListingFilter, ListingRead
from app.schemas.search import SearchLogRead, SearchSuggestionsRead
from app.services.listing_service import search_listings_use_case
from app.services.search_service import list_search_logs_use_case

router = APIRouter(prefix="/search", tags=["search"])


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


@router.get("/listings", response_model=list[ListingRead])
def search_listings_endpoint(
    min_price: str | None = Query(default=None),
    max_price: str | None = Query(default=None),
    min_size: str | None = Query(default=None),
    max_size: str | None = Query(default=None),
    location: str | None = Query(default=None),
    query: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    return search_listings_use_case(
        db,
        _safe_listing_filter(
            min_price=_parse_optional_int_query(min_price),
            max_price=_parse_optional_int_query(max_price),
            min_size=_parse_optional_int_query(min_size),
            max_size=_parse_optional_int_query(max_size),
            location=location,
            query=query,
        ),
    )


@router.get("/logs", response_model=list[SearchLogRead])
def search_logs_endpoint(
    db: Session = Depends(get_db),
    _admin: User = Depends(require_permission("view_reports")),
):
    return list_search_logs_use_case(db)


@router.get("/suggestions", response_model=SearchSuggestionsRead)
def search_suggestions_endpoint(
    prefix: str | None = Query(default=None),
    limit: int = Query(default=8, ge=1, le=25),
    db: Session = Depends(get_db),
):
    normalized_prefix = (prefix or "").strip()
    location_query = db.query(Listing.location)
    property_type_query = db.query(Listing.property_type)

    if normalized_prefix:
        pattern = f"{normalized_prefix}%"
        location_query = location_query.filter(func.lower(Listing.location).like(func.lower(pattern)))
        property_type_query = property_type_query.filter(func.lower(Listing.property_type).like(func.lower(pattern)))

    locations = [
        str(item[0])
        for item in location_query.distinct().order_by(Listing.location.asc()).limit(limit).all()
        if item and item[0]
    ]
    property_types = [
        str(item[0])
        for item in property_type_query.distinct().order_by(Listing.property_type.asc()).limit(limit).all()
        if item and item[0]
    ]
    return SearchSuggestionsRead(locations=locations, property_types=property_types)
