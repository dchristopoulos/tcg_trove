from collections import Counter
from statistics import mean
from urllib.parse import quote

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.core.exceptions import InvalidRoleError, ListingNotFoundError
from app.db.session import get_db
from app.services.favorite_service import all_favorites_use_case
from app.services.inquiry_service import all_inquiries_use_case
from app.services.listing_service import (
    list_listings_use_case,
    remove_listing_use_case,
    update_listing_use_case,
)
from app.services.payment_service import get_recent_payment_logs_use_case
from app.services.search_service import list_search_logs_use_case
from app.services.user_service import (
    change_user_role,
    delete_user_use_case,
    get_all_users,
    get_user_profile,
)
from app.web.deps import (
    get_session_user_id,
    is_valid_active_session,
    is_valid_csrf,
    template_response,
)

router = APIRouter()


def _to_float(value) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _require_admin_or_supervisor(request: Request, db: Session):
    current_user_id = get_session_user_id(request)
    if current_user_id is None:
        return None, RedirectResponse(url="/login", status_code=303)
    user = get_user_profile(db, current_user_id)
    if user is None or not is_valid_active_session(request, user):
        from app.web.deps import clear_session

        clear_session(request)
        return None, RedirectResponse(url="/login", status_code=303)
    if user.role not in {"supervisor", "admin"}:
        return user, RedirectResponse(url="/dashboard", status_code=303)
    return user, None


def _supervisor_user_stats(users, listings, inquiries, favorites):
    listing_count_by_seller = Counter(item.seller_id for item in listings)
    favorites_by_user = Counter(item.user_id for item in favorites)
    inquiries_by_user = Counter(item.user_id for item in inquiries)
    return [
        {
            "id": profile.id,
            "username": profile.username,
            "email": profile.email,
            "role": profile.role,
            "email_verified": bool(getattr(profile, "email_verified", False)),
            "listing_count": listing_count_by_seller.get(profile.id, 0),
            "favorites_count": favorites_by_user.get(profile.id, 0),
            "inquiries_count": inquiries_by_user.get(profile.id, 0),
            "can_assign": profile.role in {"buyer", "seller"},
        }
        for profile in users
    ]


@router.get("/supervisor", response_class=HTMLResponse)
def supervisor_dashboard(request: Request, db: Session = Depends(get_db), message: str | None = None):
    user, redirect = _require_admin_or_supervisor(request, db)
    if redirect is not None:
        return redirect

    users = get_all_users(db)
    listings = list_listings_use_case(db)
    inquiries = all_inquiries_use_case(db)
    favorites = all_favorites_use_case(db)
    payment_logs = get_recent_payment_logs_use_case(db)
    role_counts = Counter(str(profile.role) for profile in users)

    return template_response(
        request,
        "supervisor.html",
        {
            "user": user,
            "users": users,
            "listings": listings,
            "inquiries": inquiries,
            "favorites": favorites,
            "payment_logs": payment_logs,
            "role_counts": role_counts,
            "user_stats": _supervisor_user_stats(users, listings, inquiries, favorites),
            "message": message,
        },
    )


@router.post("/supervisor/users/{user_id}/role")
def supervisor_update_user_role(
    request: Request,
    user_id: int,
    csrf_token: str = Form(...),
    role: str = Form(...),
    db: Session = Depends(get_db),
):
    user, redirect = _require_admin_or_supervisor(request, db)
    if redirect is not None:
        return redirect
    if user is None:
        return RedirectResponse(url="/login", status_code=303)
    if not is_valid_csrf(request, csrf_token):
        raise HTTPException(status_code=400, detail="Invalid CSRF token")
    if role not in {"buyer", "seller"}:
        return RedirectResponse(
            url=f"/supervisor?message={quote('Supervisors can only assign Buyer or Seller permissions from this page.')}",
            status_code=303,
        )
    target = get_user_profile(db, user_id)
    if target is None:
        return RedirectResponse(url=f"/supervisor?message={quote('User not found.')}", status_code=303)
    if target.id == user.id:
        return RedirectResponse(url=f"/supervisor?message={quote('You cannot change your own role here.')}", status_code=303)
    if target.role not in {"buyer", "seller"}:
        return RedirectResponse(
            url=f"/supervisor?message={quote('Supervisor/Admin accounts are locked on this page.')}",
            status_code=303,
        )

    try:
        updated = change_user_role(db, user_id=user_id, role=role, actor_user_id=user.id)
    except InvalidRoleError:
        return RedirectResponse(url=f"/supervisor?message={quote('Invalid role provided.')}", status_code=303)
    if updated is None:
        return RedirectResponse(url=f"/supervisor?message={quote('User not found.')}", status_code=303)
    return RedirectResponse(
        url=f"/supervisor?message={quote(f'Updated {updated.username} to {updated.role}.')}",
        status_code=303,
    )


@router.get("/admin", response_class=HTMLResponse)
def admin_dashboard(request: Request, db: Session = Depends(get_db), message: str | None = None):
    current_user_id = get_session_user_id(request)
    if current_user_id is None:
        return RedirectResponse(url="/login", status_code=303)
    user = get_user_profile(db, current_user_id)
    if user is None or not is_valid_active_session(request, user):
        from app.web.deps import clear_session
        clear_session(request)
        return RedirectResponse(url="/login", status_code=303)
    if user.role != "admin":
        return RedirectResponse(url="/dashboard", status_code=303)
    users = get_all_users(db)
    listings = list_listings_use_case(db)
    inquiries = all_inquiries_use_case(db)
    favorites = all_favorites_use_case(db)
    search_logs = list_search_logs_use_case(db)
    payment_logs = get_recent_payment_logs_use_case(db)
    ux_events = list(getattr(request.app.state, "ux_events", []))

    listing_count_by_seller = Counter(item.seller_id for item in listings)
    favorites_by_user = Counter(item.user_id for item in favorites)
    inquiries_by_user = Counter(item.user_id for item in inquiries)
    inquiries_by_listing = Counter(item.listing_id for item in inquiries)
    favorites_by_listing = Counter(item.listing_id for item in favorites)
    role_counts = Counter(str(profile.role) for profile in users)
    open_inquiries = [item for item in inquiries if str(getattr(item, "status", "")).lower() == "open"]
    unverified_users = [item for item in users if not bool(getattr(item, "email_verified", False))]
    listings_without_inquiries = [item for item in listings if inquiries_by_listing.get(item.id, 0) == 0]
    listings_without_favorites = [item for item in listings if favorites_by_listing.get(item.id, 0) == 0]
    user_stats = [
        {
            "id": profile.id,
            "username": profile.username,
            "email": profile.email,
            "role": profile.role,
            "email_verified": bool(getattr(profile, "email_verified", False)),
            "listing_count": listing_count_by_seller.get(profile.id, 0),
            "favorites_count": favorites_by_user.get(profile.id, 0),
            "inquiries_count": inquiries_by_user.get(profile.id, 0),
        }
        for profile in users
    ]

    listing_lookup = {item.id: item for item in listings}
    favorite_counts = Counter(item.listing_id for item in favorites)
    top_favorited_listings = [
        {
            "id": listing_id,
            "title": listing_lookup[listing_id].title,
            "location": listing_lookup[listing_id].location,
            "favorites": count,
        }
        for listing_id, count in favorite_counts.most_common(6)
        if listing_id in listing_lookup
    ]

    user_lookup = {item.id: item for item in users}
    seller_performance: list[dict[str, int | str]] = []
    for seller_id, listing_count in listing_count_by_seller.items():
        seller = user_lookup.get(seller_id)
        if seller is None:
            continue
        seller_listing_ids = [listing.id for listing in listings if listing.seller_id == seller_id]
        seller_inquiries = sum(inquiries_by_listing.get(listing_id, 0) for listing_id in seller_listing_ids)
        seller_favorites = sum(favorites_by_listing.get(listing_id, 0) for listing_id in seller_listing_ids)
        seller_performance.append(
            {
                "username": str(seller.username),
                "listing_count": listing_count,
                "inquiries": seller_inquiries,
                "favorites": seller_favorites,
                "demand_score": seller_inquiries * 2 + seller_favorites,
            }
        )
    seller_performance = sorted(seller_performance, key=lambda item: int(item["demand_score"]), reverse=True)[:8]

    admin_alerts: list[dict[str, str]] = []
    if len(open_inquiries) >= 5:
        admin_alerts.append(
            {
                "severity": "high",
                "title": "Open inquiry backlog",
                "detail": f"{len(open_inquiries)} inquiries are still open across the marketplace.",
            }
        )
    if unverified_users:
        admin_alerts.append(
            {
                "severity": "medium",
                "title": "Unverified accounts",
                "detail": f"{len(unverified_users)} users have not verified email yet.",
            }
        )
    if listings_without_inquiries:
        admin_alerts.append(
            {
                "severity": "medium",
                "title": "Low engagement listings",
                "detail": f"{len(listings_without_inquiries)} listings have no inquiries.",
            }
        )
    if not admin_alerts:
        admin_alerts.append(
            {
                "severity": "good",
                "title": "Operations stable",
                "detail": "No major operational issues detected.",
            }
        )

    admin_overview = {
        "open_inquiries": len(open_inquiries),
        "unverified_users": len(unverified_users),
        "low_engagement_listings": len(listings_without_inquiries),
        "unsaved_listings": len(listings_without_favorites),
        "seller_accounts": role_counts.get("seller", 0),
    }

    recent_ux = ux_events[-500:]
    ux_error_events = [
        event for event in recent_ux if event.get("name") in {"frontend_error", "unhandled_rejection"}
    ]
    lcp_values = [_to_float(event.get("value")) for event in recent_ux if event.get("name") == "web_vital_lcp"]
    cls_values = [_to_float(event.get("value")) for event in recent_ux if event.get("name") == "web_vital_cls"]
    inp_values = [_to_float(event.get("value")) for event in recent_ux if event.get("name") == "web_vital_inp"]
    lcp_values = [value for value in lcp_values if value is not None]
    cls_values = [value for value in cls_values if value is not None]
    inp_values = [value for value in inp_values if value is not None]

    ux_path_counts = Counter(str(event.get("path", "/")) for event in recent_ux if event.get("path"))
    ux_top_paths = [
        {"path": path, "events": count}
        for path, count in ux_path_counts.most_common(6)
    ]

    ux_summary = {
        "recent_events": len(recent_ux),
        "error_events": len(ux_error_events),
        "avg_lcp_ms": round(mean(lcp_values), 1) if lcp_values else None,
        "avg_cls": round(mean(cls_values), 3) if cls_values else None,
        "avg_inp_ms": round(mean(inp_values), 1) if inp_values else None,
        "top_paths": ux_top_paths,
    }

    return template_response(
        request,
        "admin.html",
        {
            "user": user,
            "users": users,
            "listings": listings,
            "inquiries": inquiries,
            "favorites": favorites,
            "search_logs_count": len(search_logs),
            "payment_logs": payment_logs,
            "user_stats": user_stats,
            "top_favorited_listings": top_favorited_listings,
            "seller_performance": seller_performance,
            "admin_alerts": admin_alerts,
            "admin_overview": admin_overview,
            "ux_summary": ux_summary,
            "message": message,
        },
    )


@router.post("/admin/users/{user_id}/role")
def admin_update_user_role(
    request: Request,
    user_id: int,
    csrf_token: str = Form(...),
    role: str = Form(...),
    db: Session = Depends(get_db),
):
    current_user_id = get_session_user_id(request)
    if current_user_id is None:
        return RedirectResponse(url="/login", status_code=303)
    admin_user = get_user_profile(db, current_user_id)
    if admin_user is None or not is_valid_active_session(request, admin_user):
        from app.web.deps import clear_session
        clear_session(request)
        return RedirectResponse(url="/login", status_code=303)
    if admin_user.role != "admin":
        return RedirectResponse(url="/dashboard", status_code=303)
    if not is_valid_csrf(request, csrf_token):
        raise HTTPException(status_code=400, detail="Invalid CSRF token")
    if admin_user.id == user_id and role != "admin":
        return RedirectResponse(url=f"/admin?message={quote('You cannot demote your own admin role.')}", status_code=303)

    try:
        updated = change_user_role(db, user_id=user_id, role=role, actor_user_id=admin_user.id)
    except InvalidRoleError:
        return RedirectResponse(url=f"/admin?message={quote('Invalid role provided.')}", status_code=303)
    if updated is None:
        return RedirectResponse(url=f"/admin?message={quote('User not found.')}", status_code=303)
    return RedirectResponse(
        url=f"/admin?message={quote(f'Updated role for {updated.username} to {updated.role}.')}",
        status_code=303,
    )


@router.post("/admin/users/{user_id}/delete")
def admin_delete_user(
    request: Request,
    user_id: int,
    csrf_token: str = Form(...),
    db: Session = Depends(get_db),
):
    current_user_id = get_session_user_id(request)
    if current_user_id is None:
        return RedirectResponse(url="/login", status_code=303)
    admin_user = get_user_profile(db, current_user_id)
    if admin_user is None or not is_valid_active_session(request, admin_user):
        from app.web.deps import clear_session
        clear_session(request)
        return RedirectResponse(url="/login", status_code=303)
    if admin_user.role != "admin":
        return RedirectResponse(url="/dashboard", status_code=303)
    if not is_valid_csrf(request, csrf_token):
        raise HTTPException(status_code=400, detail="Invalid CSRF token")
    if admin_user.id == user_id:
        return RedirectResponse(url=f"/admin?message={quote('You cannot delete your own account.')}", status_code=303)

    removed = delete_user_use_case(db, user_id=user_id, actor_user_id=admin_user.id)
    if not removed:
        return RedirectResponse(url=f"/admin?message={quote('User not found.')}", status_code=303)
    return RedirectResponse(url=f"/admin?message={quote('User removed successfully.')}", status_code=303)


@router.post("/admin/listings/{listing_id}/update")
def admin_update_listing(
    request: Request,
    listing_id: int,
    csrf_token: str = Form(...),
    title: str = Form(...),
    price: int = Form(...),
    location: str = Form(...),
    size: int = Form(...),
    bedrooms: int = Form(...),
    bathrooms: int = Form(...),
    property_type: str = Form(...),
    furnished: str = Form(...),
    description: str = Form(...),
    db: Session = Depends(get_db),
):
    current_user_id = get_session_user_id(request)
    if current_user_id is None:
        return RedirectResponse(url="/login", status_code=303)
    admin_user = get_user_profile(db, current_user_id)
    if admin_user is None or not is_valid_active_session(request, admin_user):
        from app.web.deps import clear_session
        clear_session(request)
        return RedirectResponse(url="/login", status_code=303)
    if admin_user.role != "admin":
        return RedirectResponse(url="/dashboard", status_code=303)
    if not is_valid_csrf(request, csrf_token):
        raise HTTPException(status_code=400, detail="Invalid CSRF token")
    if (
        len(title.strip()) < 2
        or len(location.strip()) < 2
        or len(property_type.strip()) < 3
        or len(description.strip()) < 30
        or price <= 0
        or size <= 0
        or bedrooms < 0
        or bathrooms <= 0
        or furnished not in {
            "near_mint",
            "lightly_played",
            "moderately_played",
            "heavily_played",
            "damaged",
            "furnished",
            "semi_furnished",
            "unfurnished",
        }
    ):
        return RedirectResponse(url=f"/admin?message={quote('Invalid listing values.')}", status_code=303)

    try:
        update_listing_use_case(
            db,
            listing_id=listing_id,
            title=title.strip(),
            price=price,
            location=location.strip(),
            size=size,
            bedrooms=bedrooms,
            bathrooms=bathrooms,
            property_type=property_type.strip().lower(),
            furnished=furnished,
            description=description.strip(),
            actor_user_id=admin_user.id,
        )
    except ListingNotFoundError:
        return RedirectResponse(url=f"/admin?message={quote('Listing not found.')}", status_code=303)
    return RedirectResponse(url=f"/admin?message={quote('Listing updated successfully.')}", status_code=303)


@router.post("/admin/listings/{listing_id}/delete")
def admin_delete_listing(
    request: Request,
    listing_id: int,
    csrf_token: str = Form(...),
    db: Session = Depends(get_db),
):
    current_user_id = get_session_user_id(request)
    if current_user_id is None:
        return RedirectResponse(url="/login", status_code=303)
    admin_user = get_user_profile(db, current_user_id)
    if admin_user is None or not is_valid_active_session(request, admin_user):
        from app.web.deps import clear_session
        clear_session(request)
        return RedirectResponse(url="/login", status_code=303)
    if admin_user.role != "admin":
        return RedirectResponse(url="/dashboard", status_code=303)
    if not is_valid_csrf(request, csrf_token):
        raise HTTPException(status_code=400, detail="Invalid CSRF token")

    try:
        remove_listing_use_case(db, listing_id, actor_user_id=admin_user.id)
    except ListingNotFoundError:
        return RedirectResponse(url=f"/admin?message={quote('Listing not found.')}", status_code=303)
    return RedirectResponse(url=f"/admin?message={quote('Listing removed successfully.')}", status_code=303)
