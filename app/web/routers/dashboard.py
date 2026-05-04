from collections import Counter
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.models.payment_log import PaymentLog
from app.db.models.reservation import Reservation
from app.db.models.search_log import SearchLog
from app.db.models.viewing import Viewing
from app.db.session import get_db
from app.services.favorite_service import all_favorites_use_case
from app.services.inquiry_service import all_inquiries_use_case
from app.services.listing_service import list_listings_use_case
from app.services.user_service import get_all_users, get_user_profile
from app.web.auth import SESSION_ROLE_KEY
from app.web.deps import (
    get_session_user_id,
    is_valid_active_session,
    template_response,
)

router = APIRouter()


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db), message: str | None = None):
    current_user_id = get_session_user_id(request)
    if current_user_id is None:
        return RedirectResponse(url="/login", status_code=303)
    user = get_user_profile(db, current_user_id)
    if user is None:
        from app.web.deps import clear_session
        clear_session(request)
        return RedirectResponse(url="/login", status_code=303)
    if not is_valid_active_session(request, user):
        from app.web.deps import clear_session
        clear_session(request)
        return RedirectResponse(url="/login", status_code=303)
    if bool(getattr(user, "must_reset_password", False)):
        return RedirectResponse(url="/change-password", status_code=303)
    request.session[SESSION_ROLE_KEY] = user.role
    users = get_all_users(db)
    listings = list_listings_use_case(db)
    favorites = all_favorites_use_case(db)
    inquiries = all_inquiries_use_case(db)
    reservation_count = db.query(func.count(Reservation.id)).scalar() or 0
    viewing_count = db.query(func.count(Viewing.id)).scalar() or 0
    search_count = db.query(func.count(SearchLog.id)).scalar() or 0
    payment_count = db.query(func.count(PaymentLog.id)).scalar() or 0

    role_counts = Counter(str(profile.role) for profile in users)
    location_counts = Counter(str(listing.location) for listing in listings if getattr(listing, "location", None))
    avg_listing_price = int(sum(listing.price for listing in listings) / len(listings)) if listings else 0
    avg_listing_size = int(sum(listing.size for listing in listings) / len(listings)) if listings else 0

    onboarding = {
        "has_listing": any(item.seller_id == user.id for item in listings),
        "has_favorite": any(item.user_id == user.id for item in favorites),
        "has_inquiry": any(item.user_id == user.id for item in inquiries),
    }

    my_listings = [item for item in listings if item.seller_id == user.id]
    my_listing_ids = {item.id for item in my_listings}
    my_favorites = [item for item in favorites if item.user_id == user.id]
    my_inquiries_sent = [item for item in inquiries if item.user_id == user.id]
    inquiries_on_my_listings = [item for item in inquiries if item.listing_id in my_listing_ids]
    favorites_on_my_listings = [item for item in favorites if item.listing_id in my_listing_ids]
    open_inquiries_on_my_listings = [
        item for item in inquiries_on_my_listings if str(getattr(item, "status", "")).lower() == "open"
    ]

    listing_lookup = {item.id: item for item in listings}
    listing_scores: list[dict[str, int | str]] = []
    listing_performance: list[dict[str, int | str]] = []
    for listing in my_listings:
        inquiry_count = sum(1 for item in inquiries if item.listing_id == listing.id)
        favorite_count = sum(1 for item in favorites if item.listing_id == listing.id)
        score = inquiry_count * 2 + favorite_count
        listing_scores.append(
            {
                "title": str(listing.title),
                "location": str(listing.location),
                "inquiries": inquiry_count,
                "favorites": favorite_count,
                "score": score,
            }
        )
        listing_performance.append(
            {
                "id": int(listing.id),
                "title": str(listing.title),
                "location": str(listing.location),
                "price": int(listing.price),
                "inquiries": inquiry_count,
                "favorites": favorite_count,
                "score": score,
            }
        )

    top_listing_opportunities = sorted(
        listing_scores,
        key=lambda item: int(item["score"]),
        reverse=True,
    )[:3]

    my_favorite_listings = [
        listing_lookup[item.listing_id]
        for item in my_favorites
        if item.listing_id in listing_lookup
    ]

    demand_by_location = Counter(
        str(listing_lookup[item.listing_id].location)
        for item in inquiries
        if item.listing_id in listing_lookup and getattr(listing_lookup[item.listing_id], "location", None)
    )

    quick_actions: list[dict[str, str]] = []
    if not onboarding["has_listing"]:
        quick_actions.append(
            {
                "label": "Publish your first listing",
                "detail": "Listings with photos typically get more attention.",
                "href": "/listings/new",
            }
        )
    if onboarding["has_listing"] and open_inquiries_on_my_listings:
        quick_actions.append(
            {
                "label": "Respond to open inquiries",
                "detail": f"You currently have {len(open_inquiries_on_my_listings)} open conversations.",
                "href": "/account",
            }
        )
    if not onboarding["has_favorite"]:
        quick_actions.append(
            {
                "label": "Save target listings",
                "detail": "Build a shortlist to track options and compare prices.",
                "href": "/listings",
            }
        )
    if not onboarding["has_inquiry"]:
        quick_actions.append(
            {
                "label": "Send your first inquiry",
                "detail": "Start conversations with sellers about card availability.",
                "href": "/listings",
            }
        )
    if not quick_actions:
        quick_actions.append(
            {
                "label": "Review account activity",
                "detail": "Monitor sign-ins and profile changes from your account center.",
                "href": "/account",
            }
        )

    personal_metrics = {
        "my_listings": len(my_listings),
        "my_favorites": len(my_favorites),
        "my_inquiries_sent": len(my_inquiries_sent),
        "inquiries_on_my_listings": len(inquiries_on_my_listings),
        "favorites_on_my_listings": len(favorites_on_my_listings),
        "open_inquiries_on_my_listings": len(open_inquiries_on_my_listings),
    }

    my_avg_inquiries_per_listing = (
        round(len(inquiries_on_my_listings) / len(my_listings), 2)
        if my_listings
        else 0.0
    )
    platform_avg_inquiries_per_listing = (
        round(len(inquiries) / len(listings), 2)
        if listings
        else 0.0
    )
    favorite_conversion_rate = (
        round((len(favorites_on_my_listings) / len(inquiries_on_my_listings)) * 100, 1)
        if inquiries_on_my_listings
        else 0.0
    )

    now = datetime.now(UTC).replace(tzinfo=None)
    window_7 = now - timedelta(days=7)
    window_14 = now - timedelta(days=14)

    recent_inquiries = [
        item for item in inquiries_on_my_listings if getattr(item, "created_at", None) and item.created_at >= window_7
    ]
    previous_inquiries = [
        item
        for item in inquiries_on_my_listings
        if getattr(item, "created_at", None) and window_14 <= item.created_at < window_7
    ]
    recent_favorites = [
        item for item in favorites_on_my_listings if getattr(item, "created_at", None) and item.created_at >= window_7
    ]
    previous_favorites = [
        item
        for item in favorites_on_my_listings
        if getattr(item, "created_at", None) and window_14 <= item.created_at < window_7
    ]

    trend_days = [(now - timedelta(days=offset)).date() for offset in range(6, -1, -1)]
    inquiry_by_day = Counter(
        item.created_at.date() for item in recent_inquiries if getattr(item, "created_at", None)
    )
    favorite_by_day = Counter(
        item.created_at.date() for item in recent_favorites if getattr(item, "created_at", None)
    )

    inquiry_series = [inquiry_by_day.get(day, 0) for day in trend_days]
    favorite_series = [favorite_by_day.get(day, 0) for day in trend_days]
    inquiry_peak = max(inquiry_series) if inquiry_series else 0
    favorite_peak = max(favorite_series) if favorite_series else 0

    trend = {
        "inquiries_last_7": len(recent_inquiries),
        "inquiries_delta": len(recent_inquiries) - len(previous_inquiries),
        "favorites_last_7": len(recent_favorites),
        "favorites_delta": len(recent_favorites) - len(previous_favorites),
        "inquiry_bars": [
            {
                "day": day.strftime("%a"),
                "count": count,
                "height": 18 if inquiry_peak == 0 else 18 + int((count / inquiry_peak) * 62),
            }
            for day, count in zip(trend_days, inquiry_series, strict=False)
        ],
        "favorite_bars": [
            {
                "day": day.strftime("%a"),
                "count": count,
                "height": 18 if favorite_peak == 0 else 18 + int((count / favorite_peak) * 62),
            }
            for day, count in zip(trend_days, favorite_series, strict=False)
        ],
    }

    dashboard_alerts: list[dict[str, str]] = []
    if not my_listings:
        dashboard_alerts.append(
            {
                "severity": "high",
                "title": "No active listings",
                "detail": "You cannot capture inquiries until at least one listing is published.",
            }
        )
    if len(open_inquiries_on_my_listings) >= 3:
        dashboard_alerts.append(
            {
                "severity": "high",
                "title": "Inquiry backlog building",
                "detail": f"{len(open_inquiries_on_my_listings)} inquiries are still open. Respond quickly to avoid drop-off.",
            }
        )
    if my_listings and len(inquiries_on_my_listings) == 0:
        dashboard_alerts.append(
            {
                "severity": "medium",
                "title": "No demand yet",
                "detail": "Improve photos, pricing, and description quality to increase visibility.",
            }
        )
    if not dashboard_alerts:
        dashboard_alerts.append(
            {
                "severity": "good",
                "title": "Seller activity healthy",
                "detail": "No urgent blockers detected right now.",
            }
        )

    health_score = 40
    if onboarding["has_listing"]:
        health_score += 15
    if onboarding["has_favorite"]:
        health_score += 10
    if onboarding["has_inquiry"]:
        health_score += 10
    if len(open_inquiries_on_my_listings) == 0 and my_listings:
        health_score += 10
    if my_avg_inquiries_per_listing >= platform_avg_inquiries_per_listing and my_listings:
        health_score += 15
    health_score = min(100, max(0, health_score))

    benchmark = {
        "my_avg_inquiries_per_listing": my_avg_inquiries_per_listing,
        "platform_avg_inquiries_per_listing": platform_avg_inquiries_per_listing,
        "favorite_conversion_rate": favorite_conversion_rate,
        "health_score": health_score,
    }

    stats = {
        "total_users": len(users),
        "total_listings": len(listings),
        "total_favorites": len(favorites),
        "total_inquiries": len(inquiries),
        "total_reservations": reservation_count,
        "total_viewings": viewing_count,
        "total_searches": search_count,
        "total_payments": payment_count,
        "avg_listing_price": avg_listing_price,
        "avg_listing_size": avg_listing_size,
        "top_locations": location_counts.most_common(5),
        "role_breakdown": {
            "buyer": role_counts.get("buyer", 0),
            "seller": role_counts.get("seller", 0),
            "supervisor": role_counts.get("supervisor", 0),
            "admin": role_counts.get("admin", 0),
        },
    }

    return template_response(
        request,
        "dashboard.html",
        {
            "user": user,
            "onboarding": onboarding,
            "stats": stats,
            "personal_metrics": personal_metrics,
            "quick_actions": quick_actions,
            "top_listing_opportunities": top_listing_opportunities,
            "demand_hotspots": demand_by_location.most_common(5),
            "my_favorite_listings": my_favorite_listings,
            "dashboard_alerts": dashboard_alerts,
            "benchmark": benchmark,
            "listing_performance": sorted(listing_performance, key=lambda item: int(item["score"]), reverse=True),
            "trend": trend,
            "message": message,
        },
    )
