import re
from statistics import mean
from urllib.parse import parse_qsl, quote, urlencode, urlsplit, urlunsplit

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.exceptions import FavoriteNotFoundError, ListingNotFoundError, SellerNotFoundError
from app.core.utils import parse_listing_ids, parse_optional_int_query
from app.db.session import get_db
from app.schemas.listing import ListingCreate, ListingFilter
from app.services.favorite_service import add_favorite, list_favorites, remove_favorite
from app.services.inquiry_service import create_inquiry_use_case
from app.services.listing_service import (
    compare_listings_use_case,
    create_listing_use_case,
    get_listing_use_case,
    list_listings_use_case,
    search_listings_paginated_use_case,
    similar_listings_use_case,
)
from app.services.user_service import change_user_role, get_user_profile
from app.web.deps import (
    get_session_user_id,
    is_rate_limited,
    is_valid_active_session,
    is_valid_csrf,
    save_uploaded_image,
    template_response,
)

router = APIRouter()
CREATE_LISTING_RATE_LIMIT_PER_MINUTE = 20
COMPARE_MAX_LISTINGS = 8
COMPARE_MIN_SELECTION = 2
DECISION_LAB_MAX_LISTINGS = 3
DECISION_WEIGHT_DEFAULTS = {
    "price": 35,
    "size": 25,
    "bedrooms": 15,
    "bathrooms": 15,
    "location": 10,
}
COMPARE_ERROR_MESSAGES = {
    "need_two": "Select at least two listings to compare.",
    "invalid": "Your compare selection could not be processed. Please try again.",
    "not_found": "We could not find enough listings to compare. Please select at least two available listings.",
}
_DASH_SPLIT_RE = re.compile(r"\s*[-–—]\s*")
_CARD_NUMBER_RE = re.compile(
    r"\b(?:"
    r"GG\d{2}/GG\d{2}|"
    r"[A-Z]{2,6}\d{0,2}-\d{3}|"
    r"\d{1,3}/\d{1,3}"
    r")\b"
)


def _is_safe_listing_image_url(value: str) -> bool:
    value = value.strip()
    if value.startswith("/static/"):
        return True
    parsed = urlsplit(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _is_async_request(request: Request) -> bool:
    return request.headers.get("X-Requested-With") == "fetch"


def _resolve_redirect_target(next_path: str | None, fallback: str) -> str:
    if not next_path:
        return fallback
    if not next_path.startswith("/") or next_path.startswith("//"):
        return fallback
    return next_path


def _append_query_params(path: str, params: dict[str, str]) -> str:
    split = urlsplit(path)
    existing_params = [(k, v) for k, v in parse_qsl(split.query, keep_blank_values=True) if k not in params]
    merged = existing_params + [(k, v) for k, v in params.items() if v]
    return urlunsplit((split.scheme, split.netloc, split.path, urlencode(merged), split.fragment))


def _card_number_from_title(title: str | None) -> str | None:
    if not title:
        return None
    match = _CARD_NUMBER_RE.search(title)
    return match.group(0) if match else None


def _card_number_map(listings) -> dict[int, str | None]:
    return {int(item.id): _card_number_from_title(item.title) for item in listings}


def _compare_error_redirect(
    next_path: str | None,
    fallback: str,
    error_code: str,
    selected_ids: list[int] | None = None,
) -> RedirectResponse:
    params = {"compare_error": error_code}
    if selected_ids:
        params["compare_selected"] = ",".join(str(listing_id) for listing_id in selected_ids)
    redirect_target = _resolve_redirect_target(next_path, fallback)
    return RedirectResponse(url=_append_query_params(redirect_target, params), status_code=303)


def _parse_preselected_compare_ids(compare_seed: str | None, compare_selected: str | None) -> set[int]:
    preselected_ids: set[int] = set()
    seed_id = parse_optional_int_query(compare_seed)
    if seed_id is not None:
        preselected_ids.add(seed_id)
    if compare_selected:
        try:
            preselected_ids.update(parse_listing_ids(compare_selected))
        except ValueError:
            pass
    return preselected_ids


def _saved_listing_state(request: Request, db: Session) -> tuple[int | None, set[int]]:
    current_user_id = get_session_user_id(request)
    if current_user_id is None:
        return None, set()
    user = get_user_profile(db, current_user_id)
    if user is None or not is_valid_active_session(request, user):
        return None, set()
    if bool(getattr(user, "must_reset_password", False)):
        return None, set()
    saved_listing_ids = {item.listing_id for item in list_favorites(db, user_id=current_user_id)}
    return current_user_id, saved_listing_ids


def _normalize_listing_location(raw_location: str) -> str:
    value = re.sub(r"\s+", " ", raw_location.strip())
    if not value:
        return value
    if any(token in value for token in (":", "!", "Pokemon", "Yu-Gi-Oh", "Magic", "Lorcana")):
        return value

    parts = [part.strip() for part in value.split(",") if part.strip()]
    known_countries = {"greece", "gr"}
    if len(parts) >= 3:
        country, city, area = parts[0], parts[1], parts[2]
    elif len(parts) == 2:
        first, second = parts
        if first.casefold() in known_countries:
            country, city, area = first, second, "Center"
        else:
            country, city, area = "Greece", first, second
    else:
        dash_parts = [part.strip() for part in _DASH_SPLIT_RE.split(value, maxsplit=1) if part.strip()]
        if len(dash_parts) == 2:
            country, city, area = "Greece", dash_parts[0], dash_parts[1]
        else:
            country, city, area = "Greece", value, "Center"
    return f"{country.title()}, {city.title()}, {area.title()}"


def _clamp_weight(value: int | None, default: int) -> int:
    if value is None:
        return default
    return max(0, min(value, 100))


def _normalize_scores(values: list[float], invert: bool = False) -> list[float]:
    if not values:
        return []
    low = min(values)
    high = max(values)
    if abs(high - low) < 1e-9:
        return [100.0 for _ in values]
    if invert:
        return [100.0 * (high - value) / (high - low) for value in values]
    return [100.0 * (value - low) / (high - low) for value in values]


def _monthly_payment(principal: float, annual_rate_pct: float, years: int) -> float:
    if principal <= 0:
        return 0.0
    months = max(1, years * 12)
    monthly_rate = annual_rate_pct / 100.0 / 12.0
    if monthly_rate <= 0:
        return principal / months
    factor = (1 + monthly_rate) ** months
    return principal * (monthly_rate * factor) / (factor - 1)


@router.get("/listings", response_class=HTMLResponse)
def listings_page(
    request: Request,
    page: int = 1,
    page_size: int = 12,
    q: str | None = None,
    location: str | None = None,
    min_price: str | None = None,
    max_price: str | None = None,
    min_bedrooms: str | None = None,
    max_bedrooms: str | None = None,
    min_bathrooms: str | None = None,
    max_bathrooms: str | None = None,
    property_type: str | None = None,
    furnished: str | None = None,
    compare_error: str | None = None,
    compare_seed: str | None = None,
    compare_selected: str | None = None,
    db: Session = Depends(get_db),
):
    parsed_min_price = parse_optional_int_query(min_price)
    parsed_max_price = parse_optional_int_query(max_price)
    parsed_min_bedrooms = parse_optional_int_query(min_bedrooms)
    parsed_max_bedrooms = parse_optional_int_query(max_bedrooms)
    parsed_min_bathrooms = parse_optional_int_query(min_bathrooms)
    parsed_max_bathrooms = parse_optional_int_query(max_bathrooms)
    compare_error_message = COMPARE_ERROR_MESSAGES.get(compare_error)
    preselected_compare_ids = _parse_preselected_compare_ids(compare_seed, compare_selected)
    current_user_id, saved_listing_ids = _saved_listing_state(request, db)

    try:
        listing_filter = ListingFilter(
            query=q,
            location=location,
            min_price=parsed_min_price,
            max_price=parsed_max_price,
            min_bedrooms=parsed_min_bedrooms,
            max_bedrooms=parsed_max_bedrooms,
            min_bathrooms=parsed_min_bathrooms,
            max_bathrooms=parsed_max_bathrooms,
            property_type=property_type,
            furnished=furnished,
        )
    except ValidationError:
        return template_response(
            request,
            "listings.html",
            {
                "listings": [],
                "card_numbers": {},
                "page": 1,
                "page_size": min(max(page_size, 1), 24),
                "total": 0,
                "total_pages": 1,
                "query": q or "",
                "location": location or "",
                "min_price": parsed_min_price,
                "max_price": parsed_max_price,
                "min_bedrooms": parsed_min_bedrooms,
                "max_bedrooms": parsed_max_bedrooms,
                "min_bathrooms": parsed_min_bathrooms,
                "max_bathrooms": parsed_max_bathrooms,
                "property_type": property_type or "",
                "furnished": furnished or "",
                "error": "Invalid search filters. Please correct your min/max values.",
                "can_save_listings": current_user_id is not None,
                "saved_listing_ids": saved_listing_ids,
                "preselected_compare_ids": preselected_compare_ids,
                "hidden_preselected_compare_ids": sorted(preselected_compare_ids),
            },
            status_code=400,
        )

    page_payload = search_listings_paginated_use_case(
        db,
        listing_filter,
        page=max(page, 1),
        page_size=min(max(page_size, 1), 24),
    )
    page_listing_ids = {item.id for item in page_payload.items}
    hidden_preselected_compare_ids = sorted(preselected_compare_ids.difference(page_listing_ids))
    total_pages = max((page_payload.total + page_payload.page_size - 1) // page_payload.page_size, 1)
    return template_response(
        request,
        "listings.html",
        {
            "listings": page_payload.items,
            "card_numbers": _card_number_map(page_payload.items),
            "page": page_payload.page,
            "page_size": page_payload.page_size,
            "total": page_payload.total,
            "total_pages": total_pages,
            "query": q or "",
            "location": location or "",
            "min_price": parsed_min_price,
            "max_price": parsed_max_price,
            "min_bedrooms": parsed_min_bedrooms,
            "max_bedrooms": parsed_max_bedrooms,
            "min_bathrooms": parsed_min_bathrooms,
            "max_bathrooms": parsed_max_bathrooms,
            "property_type": property_type or "",
            "furnished": furnished or "",
            "error": compare_error_message,
            "can_save_listings": current_user_id is not None,
            "saved_listing_ids": saved_listing_ids,
            "preselected_compare_ids": preselected_compare_ids,
            "hidden_preselected_compare_ids": hidden_preselected_compare_ids,
        },
    )


@router.get("/listings/new", response_class=HTMLResponse)
def create_listing_form(request: Request, db: Session = Depends(get_db)):
    current_user_id = get_session_user_id(request)
    if current_user_id is None:
        return RedirectResponse(url="/login", status_code=303)
    user = get_user_profile(db, current_user_id)
    if not is_valid_active_session(request, user):
        from app.web.deps import clear_session
        clear_session(request)
        return RedirectResponse(url="/login", status_code=303)
    if bool(getattr(user, "must_reset_password", False)):
        return RedirectResponse(url="/change-password", status_code=303)
    return template_response(request, "create_listing.html", {"error": None})


@router.post("/listings/new")
def create_listing_submit(
    request: Request,
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
    image_url: str = Form(default=""),
    image: UploadFile | None = File(default=None),
    db: Session = Depends(get_db),
):
    current_user_id = get_session_user_id(request)
    if current_user_id is None:
        return RedirectResponse(url="/login", status_code=303)
    user = get_user_profile(db, current_user_id)
    if user is None or not is_valid_active_session(request, user):
        from app.web.deps import clear_session
        clear_session(request)
        return RedirectResponse(url="/login", status_code=303)
    if bool(getattr(user, "must_reset_password", False)):
        return RedirectResponse(url="/change-password", status_code=303)
    if is_rate_limited(db, request, "listing_create_web", str(current_user_id), CREATE_LISTING_RATE_LIMIT_PER_MINUTE):
        return template_response(
            request,
            "create_listing.html",
            {"error": "Too many listing submissions. Please wait a minute and try again."},
            status_code=429,
        )
    if not is_valid_csrf(request, csrf_token):
        raise HTTPException(status_code=400, detail="Invalid CSRF token")
    cleaned_image_url = image_url.strip()
    if (image is None or not image.filename) and not cleaned_image_url:
        return template_response(
            request,
            "create_listing.html",
            {"error": "A primary listing photo or image URL is required."},
            status_code=400,
        )
    if cleaned_image_url and not _is_safe_listing_image_url(cleaned_image_url):
        return template_response(
            request,
            "create_listing.html",
            {"error": "Image URL must start with http://, https://, or /static/."},
            status_code=400,
        )
    try:
        final_image_url = save_uploaded_image(image) if image is not None and image.filename else cleaned_image_url
        listing = create_listing_use_case(
            db,
            ListingCreate(
                title=title,
                price=price,
                location=_normalize_listing_location(location),
                size=size,
                bedrooms=bedrooms,
                bathrooms=bathrooms,
                property_type=property_type,
                furnished=furnished,
                description=description,
                seller_id=current_user_id,
                image_url=final_image_url,
            ),
        )
        if getattr(user, "role", "") == "buyer":
            change_user_role(
                db,
                user_id=current_user_id,
                role="seller",
                actor_user_id=current_user_id,
            )
        return RedirectResponse(url=f"/listings/{listing.id}", status_code=303)
    except ValidationError:
        return template_response(
            request,
            "create_listing.html",
            {"error": "Please complete all required listing fields with valid values."},
            status_code=400,
        )
    except SellerNotFoundError:
        return template_response(request, "create_listing.html", {"error": "Seller not found"}, status_code=400)


@router.post("/listings/{listing_id}/save")
def save_listing(
    request: Request,
    listing_id: int,
    csrf_token: str | None = Form(default=None),
    next_path: str | None = Form(default=None),
    db: Session = Depends(get_db),
):
    is_async = _is_async_request(request)
    redirect_target = _resolve_redirect_target(next_path, f"/listings/{listing_id}")
    current_user_id = get_session_user_id(request)
    if current_user_id is None:
        if is_async:
            return JSONResponse(status_code=401, content={"ok": False, "redirect": "/login"})
        return RedirectResponse(url="/login", status_code=303)
    user = get_user_profile(db, current_user_id)
    if user is None or not is_valid_active_session(request, user):
        from app.web.deps import clear_session

        clear_session(request)
        if is_async:
            return JSONResponse(status_code=401, content={"ok": False, "redirect": "/login"})
        return RedirectResponse(url="/login", status_code=303)
    if bool(getattr(user, "must_reset_password", False)):
        if is_async:
            return JSONResponse(status_code=403, content={"ok": False, "redirect": "/change-password"})
        return RedirectResponse(url="/change-password", status_code=303)
    if not csrf_token or not is_valid_csrf(request, csrf_token):
        if is_async:
            return JSONResponse(status_code=400, content={"ok": False, "error": "Invalid CSRF token"})
        raise HTTPException(status_code=400, detail="Invalid CSRF token")
    try:
        add_favorite(db, user_id=current_user_id, listing_id=listing_id)
    except ListingNotFoundError as exc:
        if is_async:
            return JSONResponse(status_code=404, content={"ok": False, "error": "Listing not found"})
        raise HTTPException(status_code=404, detail="Listing not found") from exc
    if is_async:
        return JSONResponse(
            status_code=200,
            content={"ok": True, "saved": True, "listing_id": listing_id},
        )
    return RedirectResponse(url=redirect_target, status_code=303)


@router.get("/saved", response_class=HTMLResponse)
def saved_listings_page(request: Request, db: Session = Depends(get_db)):
    current_user_id = get_session_user_id(request)
    if current_user_id is None:
        return RedirectResponse(url="/login", status_code=303)
    user = get_user_profile(db, current_user_id)
    if user is None or not is_valid_active_session(request, user):
        from app.web.deps import clear_session

        clear_session(request)
        return RedirectResponse(url="/login", status_code=303)
    if bool(getattr(user, "must_reset_password", False)):
        return RedirectResponse(url="/change-password", status_code=303)

    favorites = list_favorites(db, user_id=current_user_id)
    listings_lookup = {
        favorite.listing.id: favorite.listing
        for favorite in favorites
        if getattr(favorite, "listing", None) is not None
    }
    saved_listings = list(listings_lookup.values())
    card_numbers = _card_number_map(saved_listings)
    return template_response(
        request,
        "saved.html",
        {
            "user": user,
            "saved_listings": saved_listings,
            "card_numbers": card_numbers,
            "can_save_listings": True,
        },
    )


@router.post("/listings/{listing_id}/unsave")
def unsave_listing(
    request: Request,
    listing_id: int,
    csrf_token: str | None = Form(default=None),
    next_path: str | None = Form(default=None),
    db: Session = Depends(get_db),
):
    is_async = _is_async_request(request)
    redirect_target = _resolve_redirect_target(next_path, f"/listings/{listing_id}")
    current_user_id = get_session_user_id(request)
    if current_user_id is None:
        if is_async:
            return JSONResponse(status_code=401, content={"ok": False, "redirect": "/login"})
        return RedirectResponse(url="/login", status_code=303)
    user = get_user_profile(db, current_user_id)
    if user is None or not is_valid_active_session(request, user):
        from app.web.deps import clear_session

        clear_session(request)
        if is_async:
            return JSONResponse(status_code=401, content={"ok": False, "redirect": "/login"})
        return RedirectResponse(url="/login", status_code=303)
    if bool(getattr(user, "must_reset_password", False)):
        if is_async:
            return JSONResponse(status_code=403, content={"ok": False, "redirect": "/change-password"})
        return RedirectResponse(url="/change-password", status_code=303)
    if not csrf_token or not is_valid_csrf(request, csrf_token):
        if is_async:
            return JSONResponse(status_code=400, content={"ok": False, "error": "Invalid CSRF token"})
        raise HTTPException(status_code=400, detail="Invalid CSRF token")
    try:
        remove_favorite(db, user_id=current_user_id, listing_id=listing_id)
    except FavoriteNotFoundError:
        pass
    if is_async:
        return JSONResponse(
            status_code=200,
            content={"ok": True, "saved": False, "listing_id": listing_id},
        )
    return RedirectResponse(url=redirect_target, status_code=303)


@router.post("/listings/compare")
def compare_listings_submit(
    request: Request,
    csrf_token: str | None = Form(default=None),
    listing_ids: tuple[int, ...] = Form(default=()),
    next_path: str | None = Form(default=None),
):
    if not csrf_token or not is_valid_csrf(request, csrf_token):
        raise HTTPException(status_code=400, detail="Invalid CSRF token")
    selected_ids = list(dict.fromkeys(listing_ids))[:COMPARE_MAX_LISTINGS]
    if len(selected_ids) < COMPARE_MIN_SELECTION:
        return _compare_error_redirect(next_path, "/listings", "need_two", selected_ids)
    ids_query = ",".join(str(listing_id) for listing_id in selected_ids)
    return RedirectResponse(url=f"/listings/compare?ids={ids_query}", status_code=303)


@router.get("/listings/compare", response_class=HTMLResponse)
def compare_listings_page(request: Request, ids: str | None = None, db: Session = Depends(get_db)):
    if ids is None:
        return _compare_error_redirect(None, "/listings", "need_two")
    try:
        parsed_ids = parse_listing_ids(ids)
    except ValueError:
        return _compare_error_redirect(None, "/listings", "invalid")
    if len(parsed_ids) < COMPARE_MIN_SELECTION:
        return _compare_error_redirect(None, "/listings", "need_two", parsed_ids)

    compare_payload = compare_listings_use_case(db, parsed_ids[:COMPARE_MAX_LISTINGS])
    resolved_listing_ids = [item.listing.id for item in compare_payload.items]
    if len(resolved_listing_ids) < COMPARE_MIN_SELECTION:
        return _compare_error_redirect(None, "/listings", "not_found", resolved_listing_ids)

    current_user_id, saved_listing_ids = _saved_listing_state(request, db)
    return template_response(
        request,
        "listings_compare.html",
        {
            "compare": compare_payload,
            "can_save_listings": current_user_id is not None,
            "saved_listing_ids": saved_listing_ids,
        },
    )


@router.get("/listings/decision-lab", response_class=HTMLResponse)
def decision_lab_page(
    request: Request,
    ids: str | None = None,
    pref_location: str | None = None,
    weight_price: str | None = None,
    weight_size: str | None = None,
    weight_bedrooms: str | None = None,
    weight_bathrooms: str | None = None,
    weight_location: str | None = None,
    down_payment_pct: str | None = None,
    interest_rate: str | None = None,
    loan_years: str | None = None,
    monthly_income: str | None = None,
    db: Session = Depends(get_db),
):
    parsed_ids: list[int] = []
    if ids:
        try:
            parsed_ids = parse_listing_ids(ids)
        except ValueError:
            parsed_ids = []

    selected_items = compare_listings_use_case(db, parsed_ids[:DECISION_LAB_MAX_LISTINGS]).items if parsed_ids else []
    if not selected_items:
        fallback = list_listings_use_case(db)[:DECISION_LAB_MAX_LISTINGS]
        selected_items = compare_listings_use_case(db, [item.id for item in fallback]).items if fallback else []

    listings = [item.listing for item in selected_items]
    if len(listings) < 2:
        return template_response(
            request,
            "decision_lab.html",
            {
                "error": "Decision Lab needs at least two listings. Select listings from Compare first.",
                "analysis": None,
            },
            status_code=400,
        )

    weights = {
        "price": _clamp_weight(parse_optional_int_query(weight_price), DECISION_WEIGHT_DEFAULTS["price"]),
        "size": _clamp_weight(parse_optional_int_query(weight_size), DECISION_WEIGHT_DEFAULTS["size"]),
        "bedrooms": _clamp_weight(parse_optional_int_query(weight_bedrooms), DECISION_WEIGHT_DEFAULTS["bedrooms"]),
        "bathrooms": _clamp_weight(parse_optional_int_query(weight_bathrooms), DECISION_WEIGHT_DEFAULTS["bathrooms"]),
        "location": _clamp_weight(parse_optional_int_query(weight_location), DECISION_WEIGHT_DEFAULTS["location"]),
    }
    total_weight = sum(weights.values()) or 1
    normalized_weights = {key: value / total_weight for key, value in weights.items()}

    preferred_location = (pref_location or "").strip().casefold()
    location_scores: list[float] = []
    for listing in listings:
        location_text = str(listing.location).casefold()
        if not preferred_location:
            location_scores.append(50.0)
        elif preferred_location in location_text:
            location_scores.append(100.0)
        elif preferred_location.split(",")[0].strip() and preferred_location.split(",")[0].strip() in location_text:
            location_scores.append(75.0)
        else:
            location_scores.append(30.0)

    price_scores = _normalize_scores([float(item.price) for item in listings], invert=True)
    size_scores = _normalize_scores([float(item.size) for item in listings])
    bedroom_scores = _normalize_scores([float(item.bedrooms) for item in listings])
    bathroom_scores = _normalize_scores([float(item.bathrooms) for item in listings])

    down_payment = max(0, min(parse_optional_int_query(down_payment_pct) or 20, 95))
    apr = max(1, min(parse_optional_int_query(interest_rate) or 5, 20))
    years = max(5, min(parse_optional_int_query(loan_years) or 30, 40))
    income = max(0, parse_optional_int_query(monthly_income) or 6000)

    score_rows: list[dict] = []
    for idx, listing in enumerate(listings):
        components = {
            "price": round(price_scores[idx], 2),
            "size": round(size_scores[idx], 2),
            "bedrooms": round(bedroom_scores[idx], 2),
            "bathrooms": round(bathroom_scores[idx], 2),
            "location": round(location_scores[idx], 2),
        }
        weighted_score = sum(components[key] * normalized_weights[key] for key in components)

        principal = float(listing.price) * (1 - down_payment / 100.0)
        payment_base = _monthly_payment(principal, float(apr), years)
        payment_stress_1 = _monthly_payment(principal, float(apr + 2), years)
        payment_stress_2 = _monthly_payment(principal, float(apr + 4), years)
        burden_ratio = (payment_base / income) if income > 0 else 0.0

        reasons = [
            f"Price score {components['price']:.0f} / 100",
            f"Space score {components['size']:.0f} / 100",
            f"Monthly payment ~ ${payment_base:,.0f}",
        ]
        score_rows.append(
            {
                "listing": listing,
                "components": components,
                "weighted_score": round(weighted_score, 2),
                "payment_base": round(payment_base, 2),
                "payment_stress_1": round(payment_stress_1, 2),
                "payment_stress_2": round(payment_stress_2, 2),
                "burden_ratio_pct": round(burden_ratio * 100, 2),
                "reasons": reasons,
            }
        )

    ranked_rows = sorted(score_rows, key=lambda item: item["weighted_score"], reverse=True)
    winner = ranked_rows[0]
    avg_payment = mean([item["payment_base"] for item in ranked_rows])
    chart_rows = [
        {
            "id": row["listing"].id,
            "title": row["listing"].title,
            "components": row["components"],
        }
        for row in ranked_rows
    ]

    return template_response(
        request,
        "decision_lab.html",
        {
            "error": None,
            "analysis": {
                "rows": ranked_rows,
                "winner_id": winner["listing"].id,
                "winner_title": winner["listing"].title,
                "winner_score": winner["weighted_score"],
                "weights": weights,
                "preferred_location": pref_location or "",
                "down_payment_pct": down_payment,
                "interest_rate": apr,
                "loan_years": years,
                "monthly_income": income,
                "avg_payment": round(avg_payment, 2),
                "chart_rows": chart_rows,
            },
            "decision_ids": ",".join(str(item.id) for item in [row["listing"] for row in ranked_rows]),
        },
    )


@router.get("/listings/{listing_id}", response_class=HTMLResponse)
def listing_detail(
    request: Request,
    listing_id: int,
    message: str | None = None,
    error: str | None = None,
    db: Session = Depends(get_db),
):
    try:
        listing = get_listing_use_case(db, listing_id)
    except ListingNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Listing not found") from exc
    seller = get_user_profile(db, listing.seller_id)
    same_game_listings = similar_listings_use_case(db, listing_id)[:4]
    current_user_id, saved_listing_ids = _saved_listing_state(request, db)
    return template_response(
        request,
        "listing_detail.html",
        {
            "listing": listing,
            "seller": seller,
            "same_game_listings": same_game_listings,
            "card_number": _card_number_from_title(listing.title),
            "same_game_card_numbers": _card_number_map(same_game_listings),
            "can_save_listings": current_user_id is not None,
            "is_saved": listing.id in saved_listing_ids,
            "message": message,
            "error": error,
        },
    )


@router.post("/listings/{listing_id}/contact-seller")
def contact_seller_submit(
    request: Request,
    listing_id: int,
    csrf_token: str | None = Form(default=None),
    message: str = Form(default=""),
    db: Session = Depends(get_db),
):
    current_user_id = get_session_user_id(request)
    if current_user_id is None:
        return RedirectResponse(url="/login", status_code=303)
    user = get_user_profile(db, current_user_id)
    if user is None or not is_valid_active_session(request, user):
        from app.web.deps import clear_session

        clear_session(request)
        return RedirectResponse(url="/login", status_code=303)
    if bool(getattr(user, "must_reset_password", False)):
        return RedirectResponse(url="/change-password", status_code=303)
    if not csrf_token or not is_valid_csrf(request, csrf_token):
        raise HTTPException(status_code=400, detail="Invalid CSRF token")

    clean_message = re.sub(r"\s+", " ", message.strip())
    if len(clean_message) < 10:
        error_text = quote("Please write at least 10 characters for your message.")
        return RedirectResponse(
            url=f"/listings/{listing_id}?error={error_text}",
            status_code=303,
        )

    try:
        create_inquiry_use_case(
            db,
            user_id=current_user_id,
            listing_id=listing_id,
            message=clean_message,
        )
    except ListingNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Listing not found") from exc

    success_text = quote("Inquiry sent to the property seller.")
    return RedirectResponse(
        url=f"/listings/{listing_id}?message={success_text}",
        status_code=303,
    )
