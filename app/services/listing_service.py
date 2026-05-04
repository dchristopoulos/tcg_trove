from collections import Counter

from sqlalchemy.orm import Session

from app.core.exceptions import (
    InvalidFilterError,
    ListingNotFoundError,
    SellerNotFoundError,
    UserNotFoundError,
)
from app.db.models.favorite import Favorite
from app.db.models.inquiry import Inquiry
from app.db.models.listing import Listing
from app.managers.listing_manager import (
    create_listing_in_db,
    delete_listing_by_id,
    get_all_listings,
    get_filtered_listings,
    get_filtered_listings_paginated,
    get_filtered_listings_summary,
    get_listing_by_id,
    get_listing_market_pulse_data,
    get_recommendation_candidates,
    get_similar_listings,
    update_listing_by_id,
)
from app.managers.search_manager import create_search_log
from app.managers.user_manager import get_user_by_id
from app.schemas.listing import (
    ListingCompareItemRead,
    ListingCompareRead,
    ListingCreate,
    ListingFilter,
    ListingMarketPulseRead,
    ListingPageRead,
    ListingRecommendationItemRead,
    ListingRecommendationsRead,
    ListingSummaryRead,
)
from app.services.audit_service import record_audit_event


def create_listing_use_case(db: Session, listing_in: ListingCreate) -> Listing:
    if get_user_by_id(db, listing_in.seller_id) is None:
        raise SellerNotFoundError
    return create_listing_in_db(db, listing_in)


def list_listings_use_case(db: Session) -> list[Listing]:
    return get_all_listings(db)


def search_listings_use_case(
    db: Session,
    listing_filter: ListingFilter,
    *,
    user_id: int | None = None,
) -> list[Listing]:
    if (
        listing_filter.min_price is not None
        and listing_filter.max_price is not None
        and listing_filter.min_price > listing_filter.max_price
    ):
        raise InvalidFilterError
    if listing_filter.min_size is not None and listing_filter.max_size is not None and listing_filter.min_size > listing_filter.max_size:
        raise InvalidFilterError
    create_search_log(
        db,
        user_id=user_id,
        query=listing_filter.query or "",
        filters=listing_filter.model_dump_json(),
    )
    return get_filtered_listings(db, listing_filter)


def similar_listings_use_case(db: Session, listing_id: int) -> list[Listing]:
    listing = get_listing_by_id(db, listing_id)
    if listing is None:
        raise ListingNotFoundError
    return get_similar_listings(db, listing)


def get_listing_use_case(db: Session, listing_id: int) -> Listing:
    listing = get_listing_by_id(db, listing_id)
    if listing is None:
        raise ListingNotFoundError
    return listing


def search_listings_paginated_use_case(
    db: Session,
    listing_filter: ListingFilter,
    *,
    page: int,
    page_size: int,
    user_id: int | None = None,
) -> ListingPageRead:
    if page < 1 or page_size < 1:
        raise InvalidFilterError
    if (
        listing_filter.min_price is not None
        and listing_filter.max_price is not None
        and listing_filter.min_price > listing_filter.max_price
    ):
        raise InvalidFilterError
    if (
        listing_filter.min_size is not None
        and listing_filter.max_size is not None
        and listing_filter.min_size > listing_filter.max_size
    ):
        raise InvalidFilterError
    create_search_log(
        db,
        user_id=user_id,
        query=listing_filter.query or "",
        filters=listing_filter.model_dump_json(),
    )
    items, total = get_filtered_listings_paginated(db, listing_filter, page=page, page_size=min(page_size, 100))
    return ListingPageRead(page=page, page_size=min(page_size, 100), total=total, items=items)


def listing_summary_use_case(db: Session, listing_filter: ListingFilter) -> ListingSummaryRead:
    return ListingSummaryRead(**get_filtered_listings_summary(db, listing_filter))


def listing_market_pulse_use_case(db: Session) -> ListingMarketPulseRead:
    data = get_listing_market_pulse_data(db)
    if data["total"] == 0:
        return ListingMarketPulseRead(
            total_listings=0,
            avg_price=None,
            avg_size=None,
            top_locations=[],
            price_buckets=[
                {"label": "budget", "count": 0},
                {"label": "mid", "count": 0},
                {"label": "premium", "count": 0},
                {"label": "luxury", "count": 0},
            ],
        )

    return ListingMarketPulseRead(
        total_listings=data["total"],
        avg_price=data["avg_price"],
        avg_size=data["avg_size"],
        top_locations=data["top_locations"],
        price_buckets=[
            {"label": "budget", "count": data["budget_count"]},
            {"label": "mid", "count": data["mid_count"]},
            {"label": "premium", "count": data["premium_count"]},
            {"label": "luxury", "count": data["luxury_count"]},
        ],
    )


def compare_listings_use_case(db: Session, listing_ids: list[int]) -> ListingCompareRead:
    unique_ids = list(dict.fromkeys(listing_ids))[:8]
    listings = [item for item in (get_listing_by_id(db, listing_id) for listing_id in unique_ids) if item is not None]
    items = [
        ListingCompareItemRead(
            listing=item,
            price_per_size=round(item.price / max(item.size, 1), 2),
        )
        for item in listings
    ]
    if not listings:
        return ListingCompareRead(items=[], cheapest_listing_id=None, largest_listing_id=None, best_value_listing_id=None)

    cheapest = min(listings, key=lambda x: x.price)
    largest = max(listings, key=lambda x: x.size)
    best_value = min(listings, key=lambda x: x.price / max(x.size, 1))
    return ListingCompareRead(
        items=items,
        cheapest_listing_id=cheapest.id,
        largest_listing_id=largest.id,
        best_value_listing_id=best_value.id,
    )


def recommend_listings_use_case(db: Session, *, user_id: int, limit: int = 6) -> ListingRecommendationsRead:
    if get_user_by_id(db, user_id) is None:
        raise UserNotFoundError

    favorites = db.query(Favorite).filter(Favorite.user_id == user_id).all()
    inquiries = db.query(Inquiry).filter(Inquiry.user_id == user_id).all()

    interacted_listing_ids = {item.listing_id for item in favorites} | {item.listing_id for item in inquiries}

    # Use a small sample to derive preferences
    interacted_listings = [
        item for item in (get_listing_by_id(db, lid) for lid in list(interacted_listing_ids)[:20])
        if item is not None
    ]

    preferred_locations = Counter(str(item.location) for item in interacted_listings if getattr(item, "location", None))
    preferred_types = Counter(str(item.property_type) for item in interacted_listings if getattr(item, "property_type", None))

    # Fetch candidates from DB instead of all listings
    recommendation_candidates = get_recommendation_candidates(
        db,
        excluded_ids=interacted_listing_ids,
        preferred_locations=list(preferred_locations.keys()),
        preferred_types=list(preferred_types.keys()),
        limit=50,
    )

    scored: list[ListingRecommendationItemRead] = []
    for item in recommendation_candidates:
        score = 1.0
        reasons: list[str] = []
        location = str(item.location)
        property_type = str(item.property_type)

        if preferred_locations.get(location):
            score += 2.5 + preferred_locations[location] * 0.4
            reasons.append(f"Matches your preferred area: {location}")
        if preferred_types.get(property_type):
            score += 2.0 + preferred_types[property_type] * 0.4
            reasons.append(f"Matches your preferred property type: {property_type}")

        value_boost = max(0.0, 2.0 - (item.price / max(item.size, 1)) / 100)
        if value_boost > 0:
            score += value_boost
            reasons.append("Strong price-per-square-meter value")

        if not reasons:
            reasons.append("Popular option to explore")

        scored.append(
            ListingRecommendationItemRead(
                listing=item,
                score=round(score, 2),
                reasons=reasons[:2],
            )
        )

    scored.sort(key=lambda x: x.score, reverse=True)
    return ListingRecommendationsRead(user_id=user_id, items=scored[: max(1, min(limit, 20))])


def remove_listing_use_case(db: Session, listing_id: int, *, actor_user_id: int | None = None) -> None:
    removed = delete_listing_by_id(db, listing_id)
    if not removed:
        raise ListingNotFoundError
    record_audit_event(
        db,
        actor_user_id=actor_user_id,
        action="listing_deleted",
        target_type="listing",
        target_id=str(listing_id),
    )


def update_listing_use_case(
    db: Session,
    *,
    listing_id: int,
    title: str,
    price: int,
    location: str,
    size: int,
    bedrooms: int,
    bathrooms: int,
    property_type: str,
    furnished: str,
    description: str,
    actor_user_id: int | None = None,
) -> Listing:
    updated = update_listing_by_id(
        db,
        listing_id=listing_id,
        title=title,
        price=price,
        location=location,
        size=size,
        bedrooms=bedrooms,
        bathrooms=bathrooms,
        property_type=property_type,
        furnished=furnished,
        description=description,
    )
    if updated is None:
        raise ListingNotFoundError
    record_audit_event(
        db,
        actor_user_id=actor_user_id,
        action="listing_updated",
        target_type="listing",
        target_id=str(updated.id),
        details=(
            f"price={updated.price};location={updated.location};size={updated.size};"
            f"bedrooms={updated.bedrooms};bathrooms={updated.bathrooms};"
            f"property_type={updated.property_type};furnished={updated.furnished}"
        ),
    )
    return updated
