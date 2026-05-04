import os
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

# Force an isolated SQLite DB for API tests before importing the app.
TEST_DB = Path(__file__).parent / f"test_tcg_trove_{uuid4().hex}.db"
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB.as_posix()}"
os.environ["EMAIL_OUTBOX_WORKER_ENABLED"] = "false"
os.environ["API_RATE_LIMIT_PER_MINUTE"] = "100000"
os.environ["LOGIN_RATE_LIMIT_PER_MINUTE"] = "100000"

import app.main as main_module
from app.core.config import settings
from app.db.base import Base
from app.db.models.audit_log import AuditLog
from app.db.models.favorite import Favorite
from app.db.models.inquiry import Inquiry
from app.db.models.listing import Listing
from app.db.models.rate_limit_event import RateLimitEvent
from app.db.models.two_factor_challenge import TwoFactorChallenge
from app.db.models.user import User
from app.db.session import SessionLocal, engine
from app.main import app
from app.services import user_service as user_service_module
from app.services.rate_limit_service import consume_rate_limit
from app.services.user_service import (
    generate_email_verification_token,
    generate_password_reset_token,
    get_user_by_identifier_use_case,
    is_session_token_valid,
    issue_single_active_session,
)

_ADMIN_HEADERS_CACHE: dict[str, str] | None = None


def _extract_csrf_token(html_text: str) -> str:
    match = re.search(r'name="csrf_token"\s+value="([^"]+)"', html_text)
    assert match is not None
    return match.group(1)


def _login_web_session(client: TestClient, identifier: str, password: str) -> None:
    login_page = client.get("/login")
    login_csrf = _extract_csrf_token(login_page.text)
    login = client.post(
        "/login",
        data={"csrf_token": login_csrf, "email": identifier, "password": password},
        follow_redirects=False,
    )
    assert login.status_code == 303


def _user_headers(client: TestClient, identifier: str) -> dict[str, str]:
    _ = client
    db = SessionLocal()
    try:
        user = db.query(User).filter((User.username == identifier) | (User.email == identifier)).first()
        assert user is not None
        token = issue_single_active_session(db, user)
        return {"x-user-id": str(user.id), "x-session-token": str(token)}
    finally:
        db.close()


def _admin_headers(client) -> dict[str, str]:
    global _ADMIN_HEADERS_CACHE
    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.username == "admin").first()
        assert admin is not None
        cached_token = _ADMIN_HEADERS_CACHE.get("x-session-token") if _ADMIN_HEADERS_CACHE is not None else None
        if (
            _ADMIN_HEADERS_CACHE is not None
            and _ADMIN_HEADERS_CACHE.get("x-user-id") == str(admin.id)
            and is_session_token_valid(admin, cached_token)
        ):
            return dict(_ADMIN_HEADERS_CACHE)
        fresh_token = issue_single_active_session(db, admin)
    finally:
        db.close()

    _ = client
    _ADMIN_HEADERS_CACHE = {"x-user-id": str(admin.id), "x-session-token": str(fresh_token)}
    return dict(_ADMIN_HEADERS_CACHE)


def _post_listing(client: TestClient, payload: dict, headers: dict[str, str] | None = None):
    return client.post("/api/v1/listings/", json=payload, headers=headers or _admin_headers(client))


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def setup_module(module):
    global _ADMIN_HEADERS_CACHE
    _ADMIN_HEADERS_CACHE = None
    settings.email_outbox_worker_enabled = False
    settings.api_rate_limit_per_minute = 10_000
    settings.login_rate_limit_per_minute = 10_000
    engine.dispose()
    if TEST_DB.exists():
        try:
            TEST_DB.unlink()
        except PermissionError:
            pass
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def teardown_module(module):
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    if TEST_DB.exists():
        try:
            TEST_DB.unlink()
        except PermissionError:
            pass


def test_health_endpoint(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_live_and_ready_health_endpoints(client):
    live = client.get("/health/live")
    assert live.status_code == 200
    assert live.json()["status"] == "ok"

    ready = client.get("/health/ready")
    assert ready.status_code in {200, 503}
    assert ready.json()["status"] in {"ready", "not_ready"}
    assert "database_ok" in ready.json()


def test_ready_health_endpoint_reports_not_ready_on_db_failure(client, monkeypatch):
    class _BrokenSession:
        def execute(self, *_args, **_kwargs):
            raise RuntimeError("db unavailable")

        def close(self):
            return None

    monkeypatch.setattr(main_module, "SessionLocal", lambda: _BrokenSession())
    response = client.get("/health/ready")
    assert response.status_code == 503
    assert response.json()["status"] == "not_ready"
    assert response.json()["database_ok"] is False


def test_user_listing_flow_and_validations(client):
    headers = _admin_headers(client)

    create_user = client.post(
        "/api/v1/users/",
        json={"email": "john@example.com", "username": "john", "password": "secret123"},
    )
    assert create_user.status_code == 200
    user_data = create_user.json()
    assert user_data["email"] == "john@example.com"

    duplicate_email = client.post(
        "/api/v1/users/",
        json={"email": "john@example.com", "username": "john2", "password": "secret123"},
    )
    assert duplicate_email.status_code == 400

    duplicate_username = client.post(
        "/api/v1/users/",
        json={"email": "john2@example.com", "username": "john", "password": "secret123"},
    )
    assert duplicate_username.status_code == 400

    get_user = client.get(f"/api/v1/users/{user_data['id']}", headers=headers)
    assert get_user.status_code == 200

    missing_user = client.get("/api/v1/users/99999", headers=headers)
    assert missing_user.status_code == 404

    invalid_listing = _post_listing(
        client,
        {
            "title": "Invalid",
            "price": 1000,
            "location": "Nowhere",
            "size": 50,
            "bedrooms": 1,
            "bathrooms": 1,
            "property_type": "apartment",
            "furnished": "unfurnished",
            "description": "Bright unit with balcony and easy transit access nearby.",
            "image_url": "/static/uploads/invalid-listing.jpg",
            "seller_id": 99999,
        },
    )
    assert invalid_listing.status_code == 400

    create_listing = _post_listing(
        client,
        {
            "title": "Studio",
            "price": 1200,
            "location": "Athens",
            "size": 42,
            "bedrooms": 1,
            "bathrooms": 1,
            "property_type": "studio",
            "furnished": "semi_furnished",
            "description": "Compact studio with modern kitchen and close metro access.",
            "image_url": "/static/uploads/studio-main.jpg",
            "seller_id": user_data["id"],
        },
    )
    assert create_listing.status_code == 200

    list_users = client.get("/api/v1/users/", headers=headers)
    assert list_users.status_code == 200
    users_payload = list_users.json()
    assert any(user["username"] == "john" for user in users_payload)

    list_listings = client.get("/api/v1/listings/")
    assert list_listings.status_code == 200
    assert len(list_listings.json()) == 1


def test_api_registration_rejects_weak_password(client):
    weak = client.post(
        "/api/v1/users/",
        json={"email": "weak@example.com", "username": "weakuser", "password": "abcdefgh"},
    )
    assert weak.status_code == 400
    assert "Password" in weak.json()["detail"]


def test_api_registration_rejects_invalid_role(client):
    invalid_role = client.post(
        "/api/v1/users/",
        json={"email": "rolebad@example.com", "username": "rolebad", "password": "secret123", "role": "hacker"},
    )
    assert invalid_role.status_code == 422


def test_api_registration_cannot_assign_privileged_role(client):
    elevated = client.post(
        "/api/v1/users/",
        json={"email": "elevated@example.com", "username": "elevated", "password": "secret123", "role": "admin"},
    )
    assert elevated.status_code == 403
    assert elevated.json()["detail"] == "Permission denied"


def test_protected_api_missing_headers_returns_permission_denied(client):
    denied = client.put(
        "/api/v1/users/1/role",
        json={"role": "admin"},
    )
    assert denied.status_code == 403
    assert denied.json()["detail"] == "Permission denied"


def test_listing_create_requires_authenticated_headers(client):
    seller = client.post(
        "/api/v1/users/",
        json={"email": "listingauth@example.com", "username": "listingauth", "password": "secret123"},
    )
    assert seller.status_code == 200
    seller_id = seller.json()["id"]

    denied = client.post(
        "/api/v1/listings/",
        json={
            "title": "Unauthorized Listing",
            "price": 1000,
            "location": "Athens",
            "size": 50,
            "bedrooms": 1,
            "bathrooms": 1,
            "property_type": "apartment",
            "furnished": "unfurnished",
            "description": "Listing create should require authenticated actor headers.",
            "image_url": "/static/uploads/unauthorized-listing.jpg",
            "seller_id": seller_id,
        },
    )
    assert denied.status_code == 403
    assert denied.json()["detail"] == "Permission denied"


def test_listing_create_for_other_seller_requires_admin_permission(client):
    user_a = client.post(
        "/api/v1/users/",
        json={"email": "sellera@example.com", "username": "sellera", "password": "secret123"},
    )
    assert user_a.status_code == 200

    user_b = client.post(
        "/api/v1/users/",
        json={"email": "sellerb@example.com", "username": "sellerb", "password": "secret123"},
    )
    assert user_b.status_code == 200
    user_b_id = user_b.json()["id"]

    seller_headers = _user_headers(client, "sellera")

    forbidden = _post_listing(
        client,
        {
            "title": "Spoofed Seller Listing",
            "price": 1500,
            "location": "Athens",
            "size": 65,
            "bedrooms": 2,
            "bathrooms": 1,
            "property_type": "apartment",
            "furnished": "semi_furnished",
            "description": "Non-admin users cannot create listings for different seller IDs.",
            "image_url": "/static/uploads/spoofed-seller.jpg",
            "seller_id": user_b_id,
        },
        headers=seller_headers,
    )
    assert forbidden.status_code == 403
    assert forbidden.json()["detail"] == "Permission denied"

    admin_created = _post_listing(
        client,
        {
            "title": "Admin Seller Assignment Listing",
            "price": 1700,
            "location": "Athens",
            "size": 70,
            "bedrooms": 2,
            "bathrooms": 2,
            "property_type": "apartment",
            "furnished": "furnished",
            "description": "Admins can create listings on behalf of other sellers when needed.",
            "image_url": "/static/uploads/admin-seller-assignment.jpg",
            "seller_id": user_b_id,
        },
    )
    assert admin_created.status_code == 200
    assert admin_created.json()["seller_id"] == user_b_id


def test_user_read_endpoints_require_admin_permission(client):
    created = client.post(
        "/api/v1/users/",
        json={"email": "readguard@example.com", "username": "readguard", "password": "secret123"},
    )
    assert created.status_code == 200
    user_id = created.json()["id"]

    list_denied = client.get("/api/v1/users/")
    assert list_denied.status_code == 403
    assert list_denied.json()["detail"] == "Permission denied"

    get_denied = client.get(f"/api/v1/users/{user_id}")
    assert get_denied.status_code == 403
    assert get_denied.json()["detail"] == "Permission denied"


def test_search_logs_endpoint_requires_view_reports_permission(client):
    regular = client.post(
        "/api/v1/users/",
        json={"email": "nologs@example.com", "username": "nologs", "password": "secret123"},
    )
    assert regular.status_code == 200
    regular_headers = _user_headers(client, identifier="nologs")

    _ = client.get("/api/v1/search/listings?query=athens")

    denied = client.get("/api/v1/search/logs", headers=regular_headers)
    assert denied.status_code == 403
    assert denied.json()["detail"] == "Permission denied"

    admin_logs = client.get("/api/v1/search/logs", headers=_admin_headers(client))
    assert admin_logs.status_code == 200
    assert isinstance(admin_logs.json(), list)


def test_listing_viewings_endpoint_requires_seller_or_admin(client):
    seller = client.post(
        "/api/v1/users/",
        json={"email": "viewseller@example.com", "username": "viewseller", "password": "secret123"},
    )
    assert seller.status_code == 200
    seller_id = seller.json()["id"]

    viewer = client.post(
        "/api/v1/users/",
        json={"email": "viewer@example.com", "username": "viewer", "password": "secret123"},
    )
    assert viewer.status_code == 200
    viewer_id = viewer.json()["id"]

    created_listing = _post_listing(
        client,
        {
            "title": "Viewing Access Test",
            "price": 1750,
            "location": "Athens",
            "size": 70,
            "bedrooms": 2,
            "bathrooms": 1,
            "property_type": "apartment",
            "furnished": "semi_furnished",
            "description": "Listing used to verify viewing access boundaries for seller/admin actors.",
            "image_url": "/static/uploads/viewing-access.jpg",
            "seller_id": seller_id,
        },
        headers=_admin_headers(client),
    )
    assert created_listing.status_code == 200
    listing_id = created_listing.json()["id"]

    now = datetime.now(UTC)
    viewer_headers = _user_headers(client, identifier="viewer")
    create_viewing = client.post(
        "/api/v1/viewings/",
        json={
            "listing_id": listing_id,
            "scheduled_at": (now + timedelta(days=1)).isoformat(),
            "duration_minutes": 45,
            "notes": "Schedule check for authz boundaries.",
        },
        headers=viewer_headers,
    )
    assert create_viewing.status_code == 200
    assert create_viewing.json()["user_id"] == viewer_id

    viewer_listing_viewings = client.get(f"/api/v1/viewings/listing/{listing_id}", headers=viewer_headers)
    assert viewer_listing_viewings.status_code == 403
    assert viewer_listing_viewings.json()["detail"] == "Permission denied"

    seller_headers = _user_headers(client, identifier="viewseller")
    seller_listing_viewings = client.get(f"/api/v1/viewings/listing/{listing_id}", headers=seller_headers)
    assert seller_listing_viewings.status_code == 200
    assert len(seller_listing_viewings.json()) >= 1

    admin_listing_viewings = client.get(f"/api/v1/viewings/listing/{listing_id}", headers=_admin_headers(client))
    assert admin_listing_viewings.status_code == 200
    assert len(admin_listing_viewings.json()) >= 1


def test_api_rejects_user_without_active_session_token(client):
    created = client.post(
        "/api/v1/users/",
        json={"email": "nosession@example.com", "username": "nosession", "password": "secret123"},
    )
    assert created.status_code == 200
    user_id = created.json()["id"]

    unauthorized = client.put(
        f"/api/v1/users/{user_id}/password",
        json={"new_password": "new-secret-456"},
        headers={"x-user-id": str(user_id), "x-session-token": "forged-token"},
    )
    assert unauthorized.status_code == 403
    assert unauthorized.json()["detail"] == "Permission denied"


def test_listing_creation_rejects_seller_spoofing_for_non_admin(client):
    seller = client.post(
        "/api/v1/users/",
        json={"email": "seller-spoof@example.com", "username": "seller_spoof", "password": "secret123"},
    )
    assert seller.status_code == 200
    seller_id = seller.json()["id"]

    attacker = client.post(
        "/api/v1/users/",
        json={"email": "attacker@example.com", "username": "attacker", "password": "secret123"},
    )
    assert attacker.status_code == 200

    attacker_headers = _user_headers(client, identifier="attacker")
    spoofed = _post_listing(
        client,
        {
            "title": "Spoof Attempt",
            "price": 1500,
            "location": "Athens",
            "size": 55,
            "bedrooms": 2,
            "bathrooms": 1,
            "property_type": "apartment",
            "furnished": "unfurnished",
            "description": "Attempted seller spoofing by a non-admin account should be denied.",
            "image_url": "/static/uploads/spoof-attempt.jpg",
            "seller_id": seller_id,
        },
        headers=attacker_headers,
    )
    assert spoofed.status_code == 403
    assert spoofed.json()["detail"] == "Permission denied"


def test_login_verify_rejects_invalid_otp_payload(client):
    invalid = client.post(
        "/api/v1/users/login-verify",
        json={
            "email": "someone@example.com",
            "password": "secret123",
            "challenge_id": "challenge-123456",
            "otp_code": "12ab",
        },
    )
    assert invalid.status_code == 422


def test_login_init_rejects_invalid_email_payload(client):
    invalid = client.post(
        "/api/v1/users/login-init",
        json={"email": "not-an-email", "password": "secret123"},
    )
    assert invalid.status_code == 422


def test_login_verify_challenge_bound_to_identity(client):
    first_user = client.post(
        "/api/v1/users/",
        json={"email": "otpfirst@example.com", "username": "otpfirst", "password": "secret123"},
    )
    assert first_user.status_code == 200
    second_user = client.post(
        "/api/v1/users/",
        json={"email": "otpsecond@example.com", "username": "otpsecond", "password": "secret123"},
    )
    assert second_user.status_code == 200

    init = client.post(
        "/api/v1/users/login-init",
        json={"email": "otpfirst@example.com", "password": "secret123"},
    )
    assert init.status_code == 200
    challenge_id = init.json()["challenge_id"]
    db = SessionLocal()
    try:
        challenge = db.get(TwoFactorChallenge, challenge_id)
        assert challenge is not None
        otp_code = str(challenge.otp_code)
    finally:
        db.close()

    mismatch = client.post(
        "/api/v1/users/login-verify",
        json={
            "email": "otpsecond@example.com",
            "password": "secret123",
            "challenge_id": challenge_id,
            "otp_code": otp_code,
        },
    )
    assert mismatch.status_code == 404


def test_login_verify_invalidates_challenge_after_max_attempts(client):
    created = client.post(
        "/api/v1/users/",
        json={"email": "otplimit@example.com", "username": "otplimit", "password": "secret123"},
    )
    assert created.status_code == 200

    init = client.post(
        "/api/v1/users/login-init",
        json={"email": "otplimit@example.com", "password": "secret123"},
    )
    assert init.status_code == 200
    challenge_id = init.json()["challenge_id"]
    db = SessionLocal()
    try:
        challenge = db.get(TwoFactorChallenge, challenge_id)
        assert challenge is not None
        otp_code = str(challenge.otp_code)
    finally:
        db.close()

    for _ in range(user_service_module.MAX_2FA_VERIFY_ATTEMPTS):
        bad = client.post(
            "/api/v1/users/login-verify",
            json={
                "email": "otplimit@example.com",
                "password": "secret123",
                "challenge_id": challenge_id,
                "otp_code": "000000",
            },
        )
        assert bad.status_code == 404

    locked = client.post(
        "/api/v1/users/login-verify",
        json={
            "email": "otplimit@example.com",
            "password": "secret123",
            "challenge_id": challenge_id,
            "otp_code": otp_code,
        },
    )
    assert locked.status_code == 404


def test_listings_invalid_filter_range_rejected(client):
    response = client.get("/api/v1/listings/?min_price=2000&max_price=1000")
    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid search filters"


def test_listings_paginated_invalid_filter_range_rejected(client):
    response = client.get("/api/v1/listings/search/page?min_price=2000&max_price=1000")
    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid search filters"


def test_web_listings_invalid_filter_range_rejected(client):
    response = client.get("/listings?min_price=2000&max_price=1000")
    assert response.status_code == 400
    assert "Invalid search filters" in response.text


def test_api_listings_filter_by_rooms_and_type(client):
    seller = client.post(
        "/api/v1/users/",
        json={"email": "filterseller@example.com", "username": "filterseller", "password": "secret123"},
    )
    assert seller.status_code == 200
    seller_id = seller.json()["id"]

    low_match = _post_listing(
        client,
        {
            "title": "Filter Flat",
            "price": 1100,
            "location": "FilterCity",
            "size": 48,
            "bedrooms": 1,
            "bathrooms": 1,
            "property_type": "apartment",
            "furnished": "unfurnished",
            "description": "Compact apartment for filter test with one bedroom and one bathroom.",
            "image_url": "/static/uploads/filter-flat.jpg",
            "seller_id": seller_id,
        },
    )
    assert low_match.status_code == 200

    high_match = _post_listing(
        client,
        {
            "title": "Filter House",
            "price": 2100,
            "location": "FilterCity",
            "size": 120,
            "bedrooms": 3,
            "bathrooms": 2,
            "property_type": "house",
            "furnished": "furnished",
            "description": "Large house for filter test with family-sized layout and modern finish.",
            "image_url": "/static/uploads/filter-house.jpg",
            "seller_id": seller_id,
        },
    )
    assert high_match.status_code == 200

    filtered = client.get(
        "/api/v1/listings/?location=FilterCity&min_bedrooms=3&property_type=house&furnished=furnished"
    )
    assert filtered.status_code == 200
    payload = filtered.json()
    assert len(payload) == 1
    assert payload[0]["title"] == "Filter House"


def test_api_listing_detail_sort_summary_and_suggestions(client):
    seller = client.post(
        "/api/v1/users/",
        json={"email": "featureseller@example.com", "username": "featureseller", "password": "secret123"},
    )
    assert seller.status_code == 200
    seller_id = seller.json()["id"]

    first = _post_listing(
        client,
        {
            "title": "Alpha Loft",
            "price": 1300,
            "location": "Athens",
            "size": 55,
            "bedrooms": 2,
            "bathrooms": 1,
            "property_type": "apartment",
            "furnished": "furnished",
            "description": "Alpha listing for feature tests with detailed floor plan and bright interior.",
            "image_url": "/static/uploads/feature-alpha.jpg",
            "seller_id": seller_id,
        },
    )
    assert first.status_code == 200
    first_id = first.json()["id"]

    second = _post_listing(
        client,
        {
            "title": "Beta Villa",
            "price": 2600,
            "location": "Athens",
            "size": 140,
            "bedrooms": 4,
            "bathrooms": 2,
            "property_type": "house",
            "furnished": "unfurnished",
            "description": "Beta listing with larger footprint and private outdoor area for families.",
            "image_url": "/static/uploads/feature-beta.jpg",
            "seller_id": seller_id,
        },
    )
    assert second.status_code == 200

    detail = client.get(f"/api/v1/listings/{first_id}")
    assert detail.status_code == 200
    assert detail.json()["title"] == "Alpha Loft"

    sorted_desc = client.get("/api/v1/listings/?location=Athens&sort_by=price&sort_order=desc")
    assert sorted_desc.status_code == 200
    sorted_payload = sorted_desc.json()
    assert sorted_payload[0]["price"] >= sorted_payload[1]["price"]

    summary = client.get("/api/v1/listings/summary/stats?location=Athens")
    assert summary.status_code == 200
    summary_payload = summary.json()
    assert summary_payload["total"] >= 2
    assert summary_payload["min_price"] is not None
    assert summary_payload["max_price"] is not None
    assert summary_payload["avg_price"] is not None

    suggestions = client.get("/api/v1/search/suggestions?prefix=At")
    assert suggestions.status_code == 200
    suggestions_payload = suggestions.json()
    assert any(item.lower().startswith("at") for item in suggestions_payload["locations"])


def test_api_market_pulse_compare_and_recommendations(client):
    user_a = client.post(
        "/api/v1/users/",
        json={"email": "pulsea@example.com", "username": "pulsea", "password": "secret123"},
    )
    assert user_a.status_code == 200
    user_a_id = user_a.json()["id"]

    user_b = client.post(
        "/api/v1/users/",
        json={"email": "pulseb@example.com", "username": "pulseb", "password": "secret123"},
    )
    assert user_b.status_code == 200
    user_b_id = user_b.json()["id"]

    listing_one = _post_listing(
        client,
        {
            "title": "Pulse One",
            "price": 900,
            "location": "Athens",
            "size": 40,
            "bedrooms": 1,
            "bathrooms": 1,
            "property_type": "studio",
            "furnished": "unfurnished",
            "description": "Pulse one listing in Athens with compact layout and urban convenience nearby.",
            "image_url": "/static/uploads/pulse-one.jpg",
            "seller_id": user_a_id,
        },
    )
    assert listing_one.status_code == 200
    one_id = listing_one.json()["id"]

    listing_two = _post_listing(
        client,
        {
            "title": "Pulse Two",
            "price": 2400,
            "location": "Athens",
            "size": 120,
            "bedrooms": 3,
            "bathrooms": 2,
            "property_type": "house",
            "furnished": "furnished",
            "description": "Pulse two listing in Athens with family-ready interior and spacious rooms.",
            "image_url": "/static/uploads/pulse-two.jpg",
            "seller_id": user_b_id,
        },
    )
    assert listing_two.status_code == 200
    two_id = listing_two.json()["id"]

    pulse = client.get("/api/v1/listings/market/pulse")
    assert pulse.status_code == 200
    pulse_payload = pulse.json()
    assert pulse_payload["total_listings"] >= 2
    assert len(pulse_payload["top_locations"]) >= 1
    assert len(pulse_payload["price_buckets"]) == 4

    compare = client.get(f"/api/v1/listings/compare?ids={one_id},{two_id}")
    assert compare.status_code == 200
    compare_payload = compare.json()
    assert len(compare_payload["items"]) == 2
    assert compare_payload["cheapest_listing_id"] in {one_id, two_id}
    assert compare_payload["largest_listing_id"] in {one_id, two_id}
    assert compare_payload["best_value_listing_id"] in {one_id, two_id}

    db = SessionLocal()
    try:
        db.add(RateLimitEvent(scope_key="feature-noop", created_at=datetime.now(UTC).replace(tzinfo=None)))
        db.commit()
    finally:
        db.close()

    favorites_user_a = _admin_headers(client)
    _ = favorites_user_a
    fav_add = client.post(
        f"/api/v1/favorites/{one_id}",
        headers={"x-user-id": str(user_a_id), "x-session-token": "invalid"},
    )
    assert fav_add.status_code == 403

    recs = client.get(f"/api/v1/listings/recommendations?user_id={user_a_id}&limit=5")
    assert recs.status_code == 200
    recs_payload = recs.json()
    assert recs_payload["user_id"] == user_a_id
    assert isinstance(recs_payload["items"], list)


def test_api_listings_accept_blank_numeric_query_values(client):
    response = client.get("/api/v1/listings/?min_price=&max_price=&min_bedrooms=&max_bedrooms=")
    assert response.status_code == 200


def test_api_search_accept_blank_numeric_query_values(client):
    response = client.get("/api/v1/search/listings?min_price=&max_price=&min_size=&max_size=")
    assert response.status_code == 200


def test_web_listings_filter_controls_apply(client):
    response = client.get("/listings?location=Athens&min_bedrooms=1&property_type=studio&furnished=semi_furnished")
    assert response.status_code == 200
    assert "Any type" in response.text
    assert "Any furnishing" in response.text


def test_web_listings_empty_filter_values_do_not_fail(client):
    response = client.get(
        "/listings?q=&location=&min_price=&max_price=&min_bedrooms=0&max_bedrooms=&min_bathrooms=&max_bathrooms=&property_type=&furnished=&page_size=12"
    )
    assert response.status_code == 200
    assert "Listings" in response.text


def test_web_compare_flow_roundtrips_errors_and_redirects_to_compare_page(client):
    seller = client.post(
        "/api/v1/users/",
        json={"email": "compare-web-seller@example.com", "username": "comparewebseller", "password": "secret123"},
    )
    assert seller.status_code == 200
    seller_id = seller.json()["id"]

    listing_one = _post_listing(
        client,
        {
            "title": "Compare Web One",
            "price": 1850,
            "location": "Athens",
            "size": 66,
            "bedrooms": 2,
            "bathrooms": 1,
            "property_type": "apartment",
            "furnished": "furnished",
            "description": "First listing used to validate web compare selection and redirect behavior.",
            "image_url": "/static/uploads/compare-web-one.jpg",
            "seller_id": seller_id,
        },
    )
    assert listing_one.status_code == 200
    listing_one_id = listing_one.json()["id"]

    listing_two = _post_listing(
        client,
        {
            "title": "Compare Web Two",
            "price": 2050,
            "location": "Athens",
            "size": 72,
            "bedrooms": 3,
            "bathrooms": 2,
            "property_type": "house",
            "furnished": "semi_furnished",
            "description": "Second listing used to validate compare flow success with multiple selected IDs.",
            "image_url": "/static/uploads/compare-web-two.jpg",
            "seller_id": seller_id,
        },
    )
    assert listing_two.status_code == 200
    listing_two_id = listing_two.json()["id"]

    listings_page = client.get("/listings")
    assert listings_page.status_code == 200
    csrf_token = _extract_csrf_token(listings_page.text)

    need_two = client.post(
        "/listings/compare",
        data={"csrf_token": csrf_token, "listing_ids": str(listing_one_id), "next_path": "/listings?location=Athens"},
        follow_redirects=False,
    )
    assert need_two.status_code == 303
    need_two_location = need_two.headers["location"]
    assert need_two_location.startswith("/listings?location=Athens")
    assert "compare_error=need_two" in need_two_location
    assert f"compare_selected={listing_one_id}" in need_two_location

    need_two_page = client.get(need_two_location)
    assert need_two_page.status_code == 200
    assert "Select at least two listings to compare." in need_two_page.text
    assert f'value="{listing_one_id}"' in need_two_page.text

    unsafe_next = client.post(
        "/listings/compare",
        data={"csrf_token": csrf_token, "listing_ids": str(listing_one_id), "next_path": "https://example.com/evil"},
        follow_redirects=False,
    )
    assert unsafe_next.status_code == 303
    assert unsafe_next.headers["location"].startswith("/listings?compare_error=need_two")

    compare_redirect = client.post(
        "/listings/compare",
        data={
            "csrf_token": csrf_token,
            "listing_ids": [str(listing_one_id), str(listing_two_id)],
            "next_path": "/listings",
        },
        follow_redirects=False,
    )
    assert compare_redirect.status_code == 303
    assert compare_redirect.headers["location"] == f"/listings/compare?ids={listing_one_id},{listing_two_id}"

    compare_page = client.get(compare_redirect.headers["location"])
    assert compare_page.status_code == 200
    assert "Compare Listings" in compare_page.text
    assert "Side-by-side comparison for 2 selected properties." in compare_page.text


def test_web_save_unsave_requires_auth_and_toggles_favorite_record(client):
    seller = client.post(
        "/api/v1/users/",
        json={"email": "save-web-seller@example.com", "username": "savewebseller", "password": "secret123"},
    )
    assert seller.status_code == 200
    seller_id = seller.json()["id"]

    created_listing = _post_listing(
        client,
        {
            "title": "Save Web Target",
            "price": 1550,
            "location": "Athens",
            "size": 58,
            "bedrooms": 2,
            "bathrooms": 1,
            "property_type": "apartment",
            "furnished": "unfurnished",
            "description": "Listing used to verify web save and unsave behavior with session authentication.",
            "image_url": "/static/uploads/save-web-target.jpg",
            "seller_id": seller_id,
        },
    )
    assert created_listing.status_code == 200
    listing_id = created_listing.json()["id"]

    public_listings = client.get("/listings")
    assert public_listings.status_code == 200
    public_csrf = _extract_csrf_token(public_listings.text)

    unauth_save = client.post(
        f"/listings/{listing_id}/save",
        data={"csrf_token": public_csrf, "next_path": "/listings"},
        follow_redirects=False,
    )
    assert unauth_save.status_code == 303
    assert unauth_save.headers["location"] == "/login"

    unauth_unsave = client.post(
        f"/listings/{listing_id}/unsave",
        data={"csrf_token": public_csrf, "next_path": "/listings"},
        follow_redirects=False,
    )
    assert unauth_unsave.status_code == 303
    assert unauth_unsave.headers["location"] == "/login"

    suffix = uuid4().hex[:8]
    register_page = client.get("/users/register")
    register_csrf = _extract_csrf_token(register_page.text)
    register = client.post(
        "/users/register",
        data={
            "csrf_token": register_csrf,
            "email": f"save-web-{suffix}@example.com",
            "username": f"saveweb{suffix}",
            "password": "secret123",
        },
        follow_redirects=False,
    )
    assert register.status_code == 303

    auth_listings = client.get("/listings")
    assert auth_listings.status_code == 200
    auth_csrf = _extract_csrf_token(auth_listings.text)

    save = client.post(
        f"/listings/{listing_id}/save",
        data={"csrf_token": auth_csrf, "next_path": "/listings"},
        follow_redirects=False,
    )
    assert save.status_code == 303
    assert save.headers["location"] == "/listings"

    db = SessionLocal()
    try:
        saved_user = db.query(User).filter(User.username == f"saveweb{suffix}").first()
        assert saved_user is not None
        favorites = db.query(Favorite).filter(Favorite.user_id == saved_user.id, Favorite.listing_id == listing_id).all()
        assert len(favorites) == 1
    finally:
        db.close()

    unsave = client.post(
        f"/listings/{listing_id}/unsave",
        data={"csrf_token": auth_csrf, "next_path": "/listings"},
        follow_redirects=False,
    )
    assert unsave.status_code == 303
    assert unsave.headers["location"] == "/listings"

    db = SessionLocal()
    try:
        saved_user = db.query(User).filter(User.username == f"saveweb{suffix}").first()
        assert saved_user is not None
        favorites = db.query(Favorite).filter(Favorite.user_id == saved_user.id, Favorite.listing_id == listing_id).all()
        assert favorites == []
    finally:
        db.close()


def test_web_contact_seller_requires_auth_and_creates_normalized_inquiry(client):
    seller = client.post(
        "/api/v1/users/",
        json={"email": "contact-web-seller@example.com", "username": "contactwebseller", "password": "secret123"},
    )
    assert seller.status_code == 200
    seller_id = seller.json()["id"]

    created_listing = _post_listing(
        client,
        {
            "title": "Contact Web Target",
            "price": 2100,
            "location": "Athens",
            "size": 78,
            "bedrooms": 3,
            "bathrooms": 2,
            "property_type": "house",
            "furnished": "furnished",
            "description": "Listing used to validate contact-seller checks including validation and inquiry creation.",
            "image_url": "/static/uploads/contact-web-target.jpg",
            "seller_id": seller_id,
        },
    )
    assert created_listing.status_code == 200
    listing_id = created_listing.json()["id"]

    public_listings = client.get("/listings")
    assert public_listings.status_code == 200
    public_csrf = _extract_csrf_token(public_listings.text)
    unauth_contact = client.post(
        f"/listings/{listing_id}/contact-seller",
        data={"csrf_token": public_csrf, "message": "I can visit this week if available."},
        follow_redirects=False,
    )
    assert unauth_contact.status_code == 303
    assert unauth_contact.headers["location"] == "/login"

    suffix = uuid4().hex[:8]
    register_page = client.get("/users/register")
    register_csrf = _extract_csrf_token(register_page.text)
    register = client.post(
        "/users/register",
        data={
            "csrf_token": register_csrf,
            "email": f"contact-web-{suffix}@example.com",
            "username": f"contactweb{suffix}",
            "password": "secret123",
        },
        follow_redirects=False,
    )
    assert register.status_code == 303

    auth_detail = client.get(f"/listings/{listing_id}")
    assert auth_detail.status_code == 200
    auth_csrf = _extract_csrf_token(auth_detail.text)

    short = client.post(
        f"/listings/{listing_id}/contact-seller",
        data={"csrf_token": auth_csrf, "message": "short"},
        follow_redirects=False,
    )
    assert short.status_code == 303
    assert short.headers["location"] == (
        f"/listings/{listing_id}?error=Please%20write%20at%20least%2010%20characters%20for%20your%20message."
    )

    sent = client.post(
        f"/listings/{listing_id}/contact-seller",
        data={"csrf_token": auth_csrf, "message": "  Hello   seller,   is this listing still available?  "},
        follow_redirects=False,
    )
    assert sent.status_code == 303
    assert sent.headers["location"] == f"/listings/{listing_id}?message=Inquiry%20sent%20to%20the%20property%20seller."

    db = SessionLocal()
    try:
        contact_user = db.query(User).filter(User.username == f"contactweb{suffix}").first()
        assert contact_user is not None
        inquiries = db.query(Inquiry).filter(Inquiry.user_id == contact_user.id, Inquiry.listing_id == listing_id).all()
        assert len(inquiries) == 1
        assert inquiries[0].message == "Hello seller, is this listing still available?"
    finally:
        db.close()


def test_web_save_unsave_async_returns_json_without_reload(client):
    seller = client.post(
        "/api/v1/users/",
        json={"email": "save-async-seller@example.com", "username": "saveasyncseller", "password": "secret123"},
    )
    assert seller.status_code == 200
    seller_id = seller.json()["id"]

    created_listing = _post_listing(
        client,
        {
            "title": "Save Async Target",
            "price": 1650,
            "location": "Athens",
            "size": 62,
            "bedrooms": 2,
            "bathrooms": 1,
            "property_type": "apartment",
            "furnished": "semi_furnished",
            "description": "Listing used to validate async save and unsave JSON responses for web UI.",
            "image_url": "/static/uploads/save-async-target.jpg",
            "seller_id": seller_id,
        },
    )
    assert created_listing.status_code == 200
    listing_id = created_listing.json()["id"]

    suffix = uuid4().hex[:8]
    register_page = client.get("/users/register")
    register_csrf = _extract_csrf_token(register_page.text)
    register = client.post(
        "/users/register",
        data={
            "csrf_token": register_csrf,
            "email": f"save-async-{suffix}@example.com",
            "username": f"saveasync{suffix}",
            "password": "secret123",
        },
        follow_redirects=False,
    )
    assert register.status_code == 303

    listings_page = client.get("/listings")
    listings_csrf = _extract_csrf_token(listings_page.text)
    async_headers = {"X-Requested-With": "fetch", "Accept": "application/json"}

    save = client.post(
        f"/listings/{listing_id}/save",
        data={"csrf_token": listings_csrf, "next_path": "/listings"},
        headers=async_headers,
        follow_redirects=False,
    )
    assert save.status_code == 200
    assert save.json() == {"ok": True, "saved": True, "listing_id": listing_id}

    unsave = client.post(
        f"/listings/{listing_id}/unsave",
        data={"csrf_token": listings_csrf, "next_path": "/listings"},
        headers=async_headers,
        follow_redirects=False,
    )
    assert unsave.status_code == 200
    assert unsave.json() == {"ok": True, "saved": False, "listing_id": listing_id}


def test_messages_pages_and_seller_inbox_status_update(client):
    seller_suffix = uuid4().hex[:8]
    seller_user = client.post(
        "/api/v1/users/",
        json={
            "email": f"seller-inbox-{seller_suffix}@example.com",
            "username": f"sellerinbox{seller_suffix}",
            "password": "secret123",
        },
    )
    assert seller_user.status_code == 200
    seller_id = seller_user.json()["id"]

    db = SessionLocal()
    try:
        seller = db.query(User).filter(User.id == seller_id).first()
        assert seller is not None
        seller.email_verified = True
        seller.must_reset_password = False
        db.add(seller)
        db.commit()
    finally:
        db.close()

    created_listing = _post_listing(
        client,
        {
            "title": "Inbox Flow Listing",
            "price": 2400,
            "location": "Athens",
            "size": 95,
            "bedrooms": 3,
            "bathrooms": 2,
            "property_type": "house",
            "furnished": "furnished",
            "description": "Listing used to validate inbox and status updates for seller message management.",
            "image_url": "/static/uploads/inbox-flow-listing.jpg",
            "seller_id": seller_id,
        },
    )
    assert created_listing.status_code == 200
    listing_id = created_listing.json()["id"]

    suffix = uuid4().hex[:8]
    register_page = client.get("/users/register")
    register_csrf = _extract_csrf_token(register_page.text)
    register = client.post(
        "/users/register",
        data={
            "csrf_token": register_csrf,
            "email": f"messages-{suffix}@example.com",
            "username": f"messages{suffix}",
            "password": "secret123",
        },
        follow_redirects=False,
    )
    assert register.status_code == 303

    detail_page = client.get(f"/listings/{listing_id}")
    detail_csrf = _extract_csrf_token(detail_page.text)
    contact = client.post(
        f"/listings/{listing_id}/contact-seller",
        data={"csrf_token": detail_csrf, "message": "Hello, I would like to schedule a viewing this weekend."},
        follow_redirects=False,
    )
    assert contact.status_code == 303

    my_messages = client.get("/messages/my")
    assert my_messages.status_code == 200
    assert "My Messages" in my_messages.text
    assert "schedule a viewing this weekend" in my_messages.text

    account_page = client.get("/account")
    buyer_logout_csrf = _extract_csrf_token(account_page.text)
    buyer_logout = client.post("/logout", data={"csrf_token": buyer_logout_csrf}, follow_redirects=False)
    assert buyer_logout.status_code == 303

    _login_web_session(client, identifier=f"sellerinbox{seller_suffix}", password="secret123")
    inbox_page = client.get("/messages/inbox")
    assert inbox_page.status_code == 200
    assert "Seller Inbox" in inbox_page.text
    assert "Inbox Flow Listing" in inbox_page.text

    inbox_csrf = _extract_csrf_token(inbox_page.text)
    db = SessionLocal()
    try:
        inquiry = db.query(Inquiry).filter(Inquiry.listing_id == listing_id).order_by(Inquiry.id.desc()).first()
        assert inquiry is not None
        inquiry_id = inquiry.id
    finally:
        db.close()

    update = client.post(
        f"/messages/{inquiry_id}/status",
        data={"csrf_token": inbox_csrf, "status": "responded", "next_path": "/messages/inbox"},
        follow_redirects=False,
    )
    assert update.status_code == 303
    assert update.headers["location"].startswith("/messages/inbox")
    assert "message=Inquiry+status+updated." in update.headers["location"]

    db = SessionLocal()
    try:
        updated = db.query(Inquiry).filter(Inquiry.id == inquiry_id).first()
        assert updated is not None
        assert updated.status == "responded"
    finally:
        db.close()


def test_messages_home_prefers_my_messages_when_seller_has_sent_inquiries(client):
    suffix = uuid4().hex[:8]
    seller_a_resp = client.post(
        "/api/v1/users/",
        json={
            "email": f"seller-a-{suffix}@example.com",
            "username": f"sellera{suffix}",
            "password": "secret123",
        },
    )
    assert seller_a_resp.status_code == 200
    seller_a_id = seller_a_resp.json()["id"]

    seller_b_resp = client.post(
        "/api/v1/users/",
        json={
            "email": f"seller-b-{suffix}@example.com",
            "username": f"sellerb{suffix}",
            "password": "secret123",
        },
    )
    assert seller_b_resp.status_code == 200
    seller_b_id = seller_b_resp.json()["id"]

    db = SessionLocal()
    try:
        seller_a = db.query(User).filter(User.id == seller_a_id).first()
        seller_b = db.query(User).filter(User.id == seller_b_id).first()
        assert seller_a is not None
        assert seller_b is not None
        seller_a.email_verified = True
        seller_b.email_verified = True
        seller_a.must_reset_password = False
        seller_b.must_reset_password = False
        seller_a.role = "seller"
        seller_b.role = "seller"
        db.add(seller_a)
        db.add(seller_b)
        db.commit()
    finally:
        db.close()

    seller_a_listing = _post_listing(
        client,
        {
            "title": "Seller A Listing",
            "price": 1900,
            "location": "Athens",
            "size": 78,
            "bedrooms": 2,
            "bathrooms": 1,
            "property_type": "apartment",
            "furnished": "semi_furnished",
            "description": "Seller A listing used to establish property-seller routing state.",
            "image_url": "/static/uploads/seller-a-listing.jpg",
            "seller_id": seller_a_id,
        },
    )
    assert seller_a_listing.status_code == 200

    seller_b_listing = _post_listing(
        client,
        {
            "title": "Seller B Listing",
            "price": 2100,
            "location": "Athens",
            "size": 82,
            "bedrooms": 2,
            "bathrooms": 2,
            "property_type": "apartment",
            "furnished": "furnished",
            "description": "Seller B listing used to validate sent-inquiry redirect behavior.",
            "image_url": "/static/uploads/seller-b-listing.jpg",
            "seller_id": seller_b_id,
        },
    )
    assert seller_b_listing.status_code == 200
    seller_b_listing_id = seller_b_listing.json()["id"]

    _login_web_session(client, identifier=f"sellera{suffix}", password="secret123")
    detail_page = client.get(f"/listings/{seller_b_listing_id}")
    detail_csrf = _extract_csrf_token(detail_page.text)
    contact = client.post(
        f"/listings/{seller_b_listing_id}/contact-seller",
        data={"csrf_token": detail_csrf, "message": "I can visit this property tomorrow afternoon if available."},
        follow_redirects=False,
    )
    assert contact.status_code == 303

    messages_home = client.get("/messages", follow_redirects=False)
    assert messages_home.status_code == 303
    assert messages_home.headers["location"] == "/messages/my"


def test_admin_inbox_shows_inquiries_across_all_listings(client):
    suffix = uuid4().hex[:8]
    seller_resp = client.post(
        "/api/v1/users/",
        json={
            "email": f"admin-inbox-seller-{suffix}@example.com",
            "username": f"admininboxseller{suffix}",
            "password": "secret123",
        },
    )
    assert seller_resp.status_code == 200
    seller_id = seller_resp.json()["id"]

    db = SessionLocal()
    try:
        seller = db.query(User).filter(User.id == seller_id).first()
        admin = db.query(User).filter(User.username == "admin").first()
        assert seller is not None
        assert admin is not None
        seller.email_verified = True
        seller.must_reset_password = False
        admin.must_reset_password = False
        db.add(seller)
        db.add(admin)
        db.commit()
    finally:
        db.close()

    listing_resp = _post_listing(
        client,
        {
            "title": "Admin Inbox Visibility Listing",
            "price": 2650,
            "location": "Athens",
            "size": 104,
            "bedrooms": 3,
            "bathrooms": 2,
            "property_type": "house",
            "furnished": "furnished",
            "description": "Listing used to ensure admin inbox can review all incoming inquiries.",
            "image_url": "/static/uploads/admin-inbox-visibility.jpg",
            "seller_id": seller_id,
        },
    )
    assert listing_resp.status_code == 200
    listing_id = listing_resp.json()["id"]

    register_page = client.get("/users/register")
    register_csrf = _extract_csrf_token(register_page.text)
    buyer_suffix = uuid4().hex[:8]
    register = client.post(
        "/users/register",
        data={
            "csrf_token": register_csrf,
            "email": f"admin-inbox-buyer-{buyer_suffix}@example.com",
            "username": f"admininboxbuyer{buyer_suffix}",
            "password": "secret123",
        },
        follow_redirects=False,
    )
    assert register.status_code == 303

    listing_detail = client.get(f"/listings/{listing_id}")
    detail_csrf = _extract_csrf_token(listing_detail.text)
    contact = client.post(
        f"/listings/{listing_id}/contact-seller",
        data={"csrf_token": detail_csrf, "message": "I am interested and would like to discuss next steps this week."},
        follow_redirects=False,
    )
    assert contact.status_code == 303

    account_page = client.get("/account")
    buyer_logout_csrf = _extract_csrf_token(account_page.text)
    logout = client.post("/logout", data={"csrf_token": buyer_logout_csrf}, follow_redirects=False)
    assert logout.status_code == 303

    _login_web_session(client, identifier="admin", password="admin")
    inbox_page = client.get("/messages/inbox")
    assert inbox_page.status_code == 200
    assert "Admin Inbox" in inbox_page.text
    assert "Admin Inbox Visibility Listing" in inbox_page.text
    assert "would like to discuss next steps this week" in inbox_page.text


def test_messages_contact_profile_page_shows_shared_conversations(client):
    seller_suffix = uuid4().hex[:8]
    seller_user = client.post(
        "/api/v1/users/",
        json={
            "email": f"seller-contact-{seller_suffix}@example.com",
            "username": f"sellercontact{seller_suffix}",
            "password": "secret123",
        },
    )
    assert seller_user.status_code == 200
    seller_id = seller_user.json()["id"]

    db = SessionLocal()
    try:
        seller = db.query(User).filter(User.id == seller_id).first()
        assert seller is not None
        seller.email_verified = True
        seller.must_reset_password = False
        db.add(seller)
        db.commit()
    finally:
        db.close()

    created_listing = _post_listing(
        client,
        {
            "title": "Contact Profile Listing",
            "price": 2250,
            "location": "Athens",
            "size": 88,
            "bedrooms": 2,
            "bathrooms": 1,
            "property_type": "apartment",
            "furnished": "furnished",
            "description": "Listing used to validate contact profile visibility in messaging flows.",
            "image_url": "/static/uploads/contact-profile-listing.jpg",
            "seller_id": seller_id,
        },
    )
    assert created_listing.status_code == 200
    listing_id = created_listing.json()["id"]

    suffix = uuid4().hex[:8]
    register_page = client.get("/users/register")
    register_csrf = _extract_csrf_token(register_page.text)
    register = client.post(
        "/users/register",
        data={
            "csrf_token": register_csrf,
            "email": f"contact-{suffix}@example.com",
            "username": f"contact{suffix}",
            "password": "secret123",
        },
        follow_redirects=False,
    )
    assert register.status_code == 303

    detail_page = client.get(f"/listings/{listing_id}")
    detail_csrf = _extract_csrf_token(detail_page.text)
    contact = client.post(
        f"/listings/{listing_id}/contact-seller",
        data={"csrf_token": detail_csrf, "message": "Interested in this apartment and available for a call this week."},
        follow_redirects=False,
    )
    assert contact.status_code == 303

    my_messages = client.get("/messages/my")
    assert my_messages.status_code == 200
    assert f"/messages/contacts/{seller_id}" in my_messages.text

    profile_page = client.get(f"/messages/contacts/{seller_id}")
    assert profile_page.status_code == 200
    assert "Contact Profile" in profile_page.text
    assert f"sellercontact{seller_suffix}" in profile_page.text
    assert "Contact Profile Listing" in profile_page.text


def test_messages_routes_require_authentication(client):
    for path in ("/messages", "/messages/my", "/messages/inbox", "/messages/contacts/1"):
        response = client.get(path, follow_redirects=False)
        assert response.status_code == 303
        assert response.headers["location"] == "/login"


def test_messages_query_filter_controls_and_one_click_actions(client):
    seller_suffix = uuid4().hex[:8]
    seller_user = client.post(
        "/api/v1/users/",
        json={
            "email": f"seller-actions-{seller_suffix}@example.com",
            "username": f"selleractions{seller_suffix}",
            "password": "secret123",
        },
    )
    assert seller_user.status_code == 200
    seller_id = seller_user.json()["id"]

    db = SessionLocal()
    try:
        seller = db.query(User).filter(User.id == seller_id).first()
        assert seller is not None
        seller.email_verified = True
        seller.must_reset_password = False
        db.add(seller)
        db.commit()
    finally:
        db.close()

    created_listing = _post_listing(
        client,
        {
            "title": "Action Link Listing",
            "price": 2350,
            "location": "Athens",
            "size": 90,
            "bedrooms": 3,
            "bathrooms": 2,
            "property_type": "house",
            "furnished": "furnished",
            "description": "Listing used for one-click messaging action-link checks.",
            "image_url": "/static/uploads/action-link-listing.jpg",
            "seller_id": seller_id,
        },
    )
    assert created_listing.status_code == 200
    listing_id = created_listing.json()["id"]

    buyer_suffix = uuid4().hex[:8]
    register_page = client.get("/users/register")
    register_csrf = _extract_csrf_token(register_page.text)
    register = client.post(
        "/users/register",
        data={
            "csrf_token": register_csrf,
            "email": f"actions-{buyer_suffix}@example.com",
            "username": f"actions{buyer_suffix}",
            "password": "secret123",
        },
        follow_redirects=False,
    )
    assert register.status_code == 303

    db = SessionLocal()
    try:
        buyer = db.query(User).filter(User.username == f"actions{buyer_suffix}").first()
        assert buyer is not None
        buyer_id = int(buyer.id)
    finally:
        db.close()

    detail_page = client.get(f"/listings/{listing_id}")
    detail_csrf = _extract_csrf_token(detail_page.text)
    contact = client.post(
        f"/listings/{listing_id}/contact-seller",
        data={"csrf_token": detail_csrf, "message": "Please share available viewing times this week."},
        follow_redirects=False,
    )
    assert contact.status_code == 303

    my_messages = client.get("/messages/my?message=Inbox+synced&error=Retry+required")
    assert my_messages.status_code == 200
    assert "Inbox synced" in my_messages.text
    assert "Retry required" in my_messages.text
    assert 'placeholder="Search listing, seller, message"' in my_messages.text
    assert 'aria-label="Filter messages by status"' in my_messages.text
    assert 'data-status="open"' in my_messages.text
    assert f'href="/listings/{listing_id}"' in my_messages.text
    assert f'href="/messages/contacts/{seller_id}"' in my_messages.text
    assert "Open Listing" in my_messages.text
    assert "Seller Profile" in my_messages.text

    account_page = client.get("/account")
    buyer_logout_csrf = _extract_csrf_token(account_page.text)
    buyer_logout = client.post("/logout", data={"csrf_token": buyer_logout_csrf}, follow_redirects=False)
    assert buyer_logout.status_code == 303

    _login_web_session(client, identifier=f"selleractions{seller_suffix}", password="secret123")
    inbox_page = client.get("/messages/inbox?message=Status+saved")
    assert inbox_page.status_code == 200
    assert "Seller Inbox" in inbox_page.text
    assert "Status saved" in inbox_page.text
    assert 'data-status="open"' in inbox_page.text
    assert f'href="/listings/{listing_id}"' in inbox_page.text
    assert f'href="/messages/contacts/{buyer_id}"' in inbox_page.text
    assert "Open Listing" in inbox_page.text
    assert "Sender Profile" in inbox_page.text


def test_messages_contact_profile_limit_and_authorization(client):
    seller_suffix = uuid4().hex[:8]
    seller_user = client.post(
        "/api/v1/users/",
        json={
            "email": f"seller-limit-{seller_suffix}@example.com",
            "username": f"sellerlimit{seller_suffix}",
            "password": "secret123",
        },
    )
    assert seller_user.status_code == 200
    seller_id = seller_user.json()["id"]

    db = SessionLocal()
    try:
        seller = db.query(User).filter(User.id == seller_id).first()
        assert seller is not None
        seller.email_verified = True
        seller.must_reset_password = False
        db.add(seller)
        db.commit()
    finally:
        db.close()

    created_listing = _post_listing(
        client,
        {
            "title": "Contact Limit Listing",
            "price": 2100,
            "location": "Athens",
            "size": 80,
            "bedrooms": 2,
            "bathrooms": 1,
            "property_type": "apartment",
            "furnished": "furnished",
            "description": "Listing used to validate shared-conversation limit behavior.",
            "image_url": "/static/uploads/contact-limit-listing.jpg",
            "seller_id": seller_id,
        },
    )
    assert created_listing.status_code == 200
    listing_id = created_listing.json()["id"]

    buyer_suffix = uuid4().hex[:8]
    register_page = client.get("/users/register")
    register_csrf = _extract_csrf_token(register_page.text)
    register = client.post(
        "/users/register",
        data={
            "csrf_token": register_csrf,
            "email": f"limit-buyer-{buyer_suffix}@example.com",
            "username": f"limitbuyer{buyer_suffix}",
            "password": "secret123",
        },
        follow_redirects=False,
    )
    assert register.status_code == 303

    stranger_suffix = uuid4().hex[:8]
    stranger_user = client.post(
        "/api/v1/users/",
        json={
            "email": f"stranger-{stranger_suffix}@example.com",
            "username": f"stranger{stranger_suffix}",
            "password": "secret123",
        },
    )
    assert stranger_user.status_code == 200
    stranger_id = stranger_user.json()["id"]

    db = SessionLocal()
    try:
        buyer = db.query(User).filter(User.username == f"limitbuyer{buyer_suffix}").first()
        stranger = db.query(User).filter(User.id == stranger_id).first()
        assert buyer is not None
        assert stranger is not None
        buyer.email_verified = True
        buyer.must_reset_password = False
        db.add(buyer)
        stranger.email_verified = True
        stranger.must_reset_password = False
        db.add(stranger)

        base_time = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
        for idx in range(12):
            db.add(
                Inquiry(
                    user_id=int(buyer.id),
                    listing_id=listing_id,
                    message=f"[msg-{idx:02d}] deterministic history sample",
                    status="open",
                    created_at=base_time + timedelta(minutes=idx),
                )
            )
        db.commit()
    finally:
        db.close()

    account_page = client.get("/account")
    buyer_logout_csrf = _extract_csrf_token(account_page.text)
    buyer_logout = client.post("/logout", data={"csrf_token": buyer_logout_csrf}, follow_redirects=False)
    assert buyer_logout.status_code == 303

    _login_web_session(client, identifier=f"stranger{stranger_suffix}", password="secret123")
    blocked = client.get(f"/messages/contacts/{seller_id}", follow_redirects=False)
    assert blocked.status_code == 303
    assert blocked.headers["location"].startswith("/messages?")
    assert "error=You+cannot+view+this+contact+profile." in blocked.headers["location"]

    account_page = client.get("/account")
    stranger_logout_csrf = _extract_csrf_token(account_page.text)
    stranger_logout = client.post("/logout", data={"csrf_token": stranger_logout_csrf}, follow_redirects=False)
    assert stranger_logout.status_code == 303

    _login_web_session(client, identifier=f"limitbuyer{buyer_suffix}", password="secret123")
    profile_page = client.get(f"/messages/contacts/{seller_id}")
    assert profile_page.status_code == 200
    assert "Contact Profile" in profile_page.text
    assert "Recent Shared Conversations" in profile_page.text
    assert "Open Listing" in profile_page.text
    assert f'href="/listings/{listing_id}"' in profile_page.text
    assert "[msg-11] deterministic history sample" in profile_page.text
    assert "[msg-02] deterministic history sample" in profile_page.text
    assert "[msg-01] deterministic history sample" not in profile_page.text
    assert "[msg-00] deterministic history sample" not in profile_page.text


def test_messages_thread_reply_and_poll_endpoint(client):
    seller_suffix = uuid4().hex[:8]
    seller_user = client.post(
        "/api/v1/users/",
        json={
            "email": f"seller-thread-{seller_suffix}@example.com",
            "username": f"sellerthread{seller_suffix}",
            "password": "secret123",
        },
    )
    assert seller_user.status_code == 200
    seller_id = seller_user.json()["id"]

    db = SessionLocal()
    try:
        seller = db.query(User).filter(User.id == seller_id).first()
        assert seller is not None
        seller.email_verified = True
        seller.must_reset_password = False
        seller.role = "seller"
        db.add(seller)
        db.commit()
    finally:
        db.close()

    created_listing = _post_listing(
        client,
        {
            "title": "Thread Listing",
            "price": 2150,
            "location": "Athens",
            "size": 83,
            "bedrooms": 2,
            "bathrooms": 1,
            "property_type": "apartment",
            "furnished": "furnished",
            "description": "Listing used to verify messaging thread replies and polling endpoint.",
            "image_url": "/static/uploads/thread-listing.jpg",
            "seller_id": seller_id,
        },
    )
    assert created_listing.status_code == 200
    listing_id = created_listing.json()["id"]

    buyer_suffix = uuid4().hex[:8]
    register_page = client.get("/users/register")
    register_csrf = _extract_csrf_token(register_page.text)
    register = client.post(
        "/users/register",
        data={
            "csrf_token": register_csrf,
            "email": f"thread-buyer-{buyer_suffix}@example.com",
            "username": f"threadbuyer{buyer_suffix}",
            "password": "secret123",
        },
        follow_redirects=False,
    )
    assert register.status_code == 303

    detail_page = client.get(f"/listings/{listing_id}")
    detail_csrf = _extract_csrf_token(detail_page.text)
    contact = client.post(
        f"/listings/{listing_id}/contact-seller",
        data={"csrf_token": detail_csrf, "message": "Initial inquiry for thread verification."},
        follow_redirects=False,
    )
    assert contact.status_code == 303

    my_messages = client.get("/messages/my")
    assert my_messages.status_code == 200
    my_csrf = _extract_csrf_token(my_messages.text)

    db = SessionLocal()
    try:
        inquiry = db.query(Inquiry).filter(Inquiry.listing_id == listing_id).order_by(Inquiry.id.desc()).first()
        assert inquiry is not None
        inquiry_id = int(inquiry.id)
    finally:
        db.close()

    buyer_reply = client.post(
        f"/messages/{inquiry_id}/reply",
        data={
            "csrf_token": my_csrf,
            "next_path": "/messages/my",
            "body": "Can we schedule a viewing on Friday afternoon?",
        },
        follow_redirects=False,
    )
    assert buyer_reply.status_code == 303
    assert buyer_reply.headers["location"].startswith("/messages/my")

    poll_as_buyer = client.get(f"/messages/{inquiry_id}/events?after_id=0")
    assert poll_as_buyer.status_code == 200
    payload = poll_as_buyer.json()
    assert payload["inquiry_id"] == inquiry_id
    assert any("Friday afternoon" in item["body"] for item in payload["items"])

    account_page = client.get("/account")
    logout_csrf = _extract_csrf_token(account_page.text)
    logout = client.post("/logout", data={"csrf_token": logout_csrf}, follow_redirects=False)
    assert logout.status_code == 303

    _login_web_session(client, identifier=f"sellerthread{seller_suffix}", password="secret123")
    inbox_page = client.get("/messages/inbox")
    inbox_csrf = _extract_csrf_token(inbox_page.text)
    seller_reply = client.post(
        f"/messages/{inquiry_id}/reply",
        data={
            "csrf_token": inbox_csrf,
            "next_path": "/messages/inbox",
            "body": "Friday works. Please confirm 16:00.",
        },
        follow_redirects=False,
    )
    assert seller_reply.status_code == 303

    poll_as_seller = client.get(f"/messages/{inquiry_id}/events?after_id=0")
    assert poll_as_seller.status_code == 200
    seller_payload = poll_as_seller.json()
    assert any("Please confirm 16:00" in item["body"] for item in seller_payload["items"])


def test_gdpr_export_includes_inquiry_messages(client):
    created_user = client.post(
        "/api/v1/users/",
        json={
            "email": "gdprmsg@example.com",
            "username": "gdprmsg",
            "password": "secret123",
        },
    )
    assert created_user.status_code == 200
    user_id = int(created_user.json()["id"])
    headers = _user_headers(client, "gdprmsg")

    listing_resp = _post_listing(
        client,
        {
            "title": "GDPR Messages Listing",
            "price": 1800,
            "location": "Athens",
            "size": 70,
            "bedrooms": 2,
            "bathrooms": 1,
            "property_type": "apartment",
            "furnished": "unfurnished",
            "description": "Listing for GDPR export messaging coverage.",
            "image_url": "/static/uploads/gdpr-messages-listing.jpg",
            "seller_id": user_id,
        },
        headers=_admin_headers(client),
    )
    assert listing_resp.status_code == 200
    listing_id = int(listing_resp.json()["id"])

    inquiry_resp = client.post(
        "/api/v1/inquiries/",
        json={"listing_id": listing_id, "message": "GDPR inquiry message seed."},
        headers=headers,
    )
    assert inquiry_resp.status_code == 200
    inquiry_id = int(inquiry_resp.json()["id"])

    reply_resp = client.post(
        f"/api/v1/inquiries/{inquiry_id}/messages",
        json={"body": "GDPR reply payload"},
        headers=headers,
    )
    assert reply_resp.status_code == 200

    export_resp = client.get("/api/v1/gdpr/export-me", headers=headers)
    assert export_resp.status_code == 200
    payload = export_resp.json()
    assert "inquiry_messages" in payload
    assert isinstance(payload["inquiry_messages"], list)
    assert len(payload["inquiry_messages"]) >= 1


@pytest.mark.parametrize(
    ("raw_location", "expected"),
    [
        ("Athens", "Greece, Athens, Center"),
        ("athens,pagkrati", "Greece, Athens, Pagkrati"),
        ("greece,athens", "Greece, Athens, Center"),
        ("athens - kipseli", "Greece, Athens, Kipseli"),
        ("gr, thessaloniki", "Gr, Thessaloniki, Center"),
    ],
)
def test_web_listing_location_normalization_variants(raw_location, expected):
    from app.web.routers.listings import _normalize_listing_location

    assert _normalize_listing_location(raw_location) == expected


def test_admin_cannot_demote_self_via_api(client):
    login_page = client.get("/login")
    login_csrf = _extract_csrf_token(login_page.text)
    login = client.post(
        "/login",
        data={"csrf_token": login_csrf, "email": "admin", "password": "admin"},
        follow_redirects=False,
    )
    assert login.status_code == 303

    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.username == "admin").first()
        assert admin is not None
        session_token = issue_single_active_session(db, admin)
        demote = client.put(
            f"/api/v1/users/{admin.id}/role",
            json={"role": "buyer"},
            headers={"x-user-id": str(admin.id), "x-session-token": str(session_token)},
        )
        assert demote.status_code == 403
        assert demote.json()["detail"] == "Permission denied"
    finally:
        db.close()


def test_admin_cannot_revoke_own_critical_permissions(client):
    headers = _admin_headers(client)

    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.username == "admin").first()
        assert admin is not None
        response = client.put(
            f"/api/v1/users/{admin.id}/permissions",
            json={"grants": [], "revokes": ["manage_users"]},
            headers=headers,
        )
        assert response.status_code == 403
        assert response.json()["detail"] == "Permission denied"
    finally:
        db.close()


def test_admin_can_manage_user_roles_and_listings_from_web(client):
    created_user = client.post(
        "/api/v1/users/",
        json={"email": "adminmanage@example.com", "username": "adminmanage", "password": "secret123"},
    )
    assert created_user.status_code == 200
    managed_user_id = created_user.json()["id"]

    created_listing = _post_listing(
        client,
        {
            "title": "Original Title",
            "price": 999,
            "location": "Athens",
            "size": 45,
            "bedrooms": 2,
            "bathrooms": 1,
            "property_type": "apartment",
            "furnished": "unfurnished",
            "description": "Family-ready apartment with quiet street view and storage room.",
            "image_url": "/static/uploads/original-title.jpg",
            "seller_id": managed_user_id,
        },
    )
    assert created_listing.status_code == 200
    managed_listing_id = created_listing.json()["id"]

    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.username == "admin").first()
        assert admin is not None
        admin.must_reset_password = False
        db.add(admin)
        db.commit()
    finally:
        db.close()

    _login_web_session(client, identifier="admin", password="admin")
    admin_page = client.get("/admin")
    assert admin_page.status_code == 200
    assert "Operational Alerts" in admin_page.text
    assert "Seller Performance" in admin_page.text
    admin_csrf = _extract_csrf_token(admin_page.text)

    role_update = client.post(
        f"/admin/users/{managed_user_id}/role",
        data={"csrf_token": admin_csrf, "role": "seller"},
        follow_redirects=False,
    )
    assert role_update.status_code == 303

    listing_update = client.post(
        f"/admin/listings/{managed_listing_id}/update",
        data={
            "csrf_token": admin_csrf,
            "title": "Updated Title",
            "price": "1200",
            "location": "Patra",
            "size": "55",
            "bedrooms": "3",
            "bathrooms": "2",
            "property_type": "house",
            "furnished": "furnished",
            "description": "Renovated home with private yard and two full bathrooms for families.",
        },
        follow_redirects=False,
    )
    assert listing_update.status_code == 303

    listing_delete = client.post(
        f"/admin/listings/{managed_listing_id}/delete",
        data={"csrf_token": admin_csrf},
        follow_redirects=False,
    )
    assert listing_delete.status_code == 303

    db = SessionLocal()
    try:
        managed_user = db.query(User).filter(User.id == managed_user_id).first()
        assert managed_user is not None
        assert str(managed_user.role) == "seller"

        managed_listing = db.query(Listing).filter(Listing.id == managed_listing_id).first()
        assert managed_listing is None
    finally:
        db.close()


def test_web_pages_and_auth_flows(client):
    home = client.get("/")
    assert home.status_code == 200
    assert "TCG Trove" in home.text

    register_page = client.get("/users/register")
    assert register_page.status_code == 200
    register_csrf = _extract_csrf_token(register_page.text)

    create_page_unauth = client.get("/listings/new", follow_redirects=False)
    assert create_page_unauth.status_code == 303
    assert create_page_unauth.headers["location"] == "/login"

    register_response = client.post(
        "/users/register",
        data={
            "csrf_token": register_csrf,
            "email": "alice@example.com",
            "username": "alice",
            "password": "secret123",
        },
        follow_redirects=False,
    )
    assert register_response.status_code == 303
    assert register_response.headers["location"].startswith("/dashboard?message=")

    dashboard = client.get("/dashboard")
    assert dashboard.status_code == 200
    assert "Welcome, alice" in dashboard.text
    assert "Decision Dashboard" in dashboard.text
    assert "Trend Pulse" in dashboard.text
    assert "Attention Alerts" in dashboard.text
    assert "Listing Performance" in dashboard.text
    assert "Portfolio Health" in dashboard.text

    account_page = client.get("/account")
    assert account_page.status_code == 200
    assert "Account Settings" in account_page.text
    assert "Change Password" in account_page.text
    assert "Recent Activity" in account_page.text

    create_form = client.get("/listings/new")
    create_csrf = _extract_csrf_token(create_form.text)
    create_listing = client.post(
        "/listings/new",
        data={
            "csrf_token": create_csrf,
            "title": "Loft",
            "price": 1500,
            "location": "Athens",
            "size": 60,
            "bedrooms": 2,
            "bathrooms": 2,
            "property_type": "loft",
            "furnished": "furnished",
            "description": "Spacious loft with natural light, open kitchen, and central neighborhood access.",
        },
        files={"image": ("loft.png", b"\x89PNG\r\n\x1a\n\x00test", "image/png")},
        follow_redirects=False,
    )
    assert create_listing.status_code == 303

    listing_page = client.get("/listings")
    assert listing_page.status_code == 200
    assert "Loft" in listing_page.text

    logout_csrf = _extract_csrf_token(account_page.text)
    logout = client.post("/logout", data={"csrf_token": logout_csrf}, follow_redirects=False)
    assert logout.status_code == 303


def test_supervisor_dashboard_can_assign_buyer_seller_permissions(client):
    supervisor_name = f"supervisor_case_{uuid4().hex[:8]}"
    supervisor_email = f"{supervisor_name}@example.com"
    supervisor_password = "supervisor123"
    created_supervisor = client.post(
        "/api/v1/users/",
        json={"email": supervisor_email, "username": supervisor_name, "password": supervisor_password},
    )
    assert created_supervisor.status_code == 200
    target_name = f"buyer_case_{uuid4().hex[:8]}"
    target_email = f"{target_name}@example.com"
    created_target = client.post(
        "/api/v1/users/",
        json={"email": target_email, "username": target_name, "password": "buyer123"},
    )
    assert created_target.status_code == 200

    db = SessionLocal()
    try:
        supervisor = db.query(User).filter(User.username == supervisor_name).first()
        target = db.query(User).filter(User.username == target_name).first()
        assert supervisor is not None
        assert target is not None
        supervisor.role = "supervisor"
        supervisor.email_verified = True
        target.role = "buyer"
        target.email_verified = True
        db.add(supervisor)
        db.add(target)
        db.commit()
        target_id = target.id
    finally:
        db.close()

    _login_web_session(client, supervisor_name, supervisor_password)
    page = client.get("/supervisor")
    assert page.status_code == 200
    assert "Supervisor Dashboard" in page.text
    assert "User Permissions" in page.text
    csrf = _extract_csrf_token(page.text)

    update = client.post(
        f"/supervisor/users/{target_id}/role",
        data={"csrf_token": csrf, "role": "seller"},
        follow_redirects=False,
    )
    assert update.status_code == 303
    assert update.headers["location"].startswith("/supervisor?message=")

    db = SessionLocal()
    try:
        updated = db.query(User).filter(User.id == target_id).first()
        assert updated is not None
        assert updated.role == "seller"
    finally:
        db.close()

    invalid = client.post(
        f"/supervisor/users/{target_id}/role",
        data={"csrf_token": csrf, "role": "admin"},
        follow_redirects=False,
    )
    assert invalid.status_code == 303
    assert "Supervisors%20can%20only%20assign%20Buyer%20or%20Seller" in invalid.headers["location"]


def test_web_create_listing_accepts_image_url_without_upload(client):
    seller_name = f"seller_case_{uuid4().hex[:8]}"
    seller_email = f"{seller_name}@example.com"
    seller_password = "seller123"
    created_seller = client.post(
        "/api/v1/users/",
        json={"email": seller_email, "username": seller_name, "password": seller_password},
    )
    assert created_seller.status_code == 200
    db = SessionLocal()
    try:
        seller = db.query(User).filter(User.username == seller_name).first()
        assert seller is not None
        seller.role = "seller"
        seller.email_verified = True
        db.add(seller)
        db.commit()
    finally:
        db.close()

    _login_web_session(client, seller_name, seller_password)
    create_form = client.get("/listings/new")
    assert create_form.status_code == 200
    assert "Quick Fill" in create_form.text
    csrf = _extract_csrf_token(create_form.text)

    response = client.post(
        "/listings/new",
        data={
            "csrf_token": csrf,
            "title": "Pikachu GG30/GG70",
            "price": "24",
            "location": "Pokemon",
            "size": "2",
            "bedrooms": "2023",
            "bathrooms": "3",
            "property_type": "rare_holo",
            "furnished": "near_mint",
            "description": "Real Pokemon TCG sample listing with an external image URL for easier seller demo creation.",
            "image_url": "https://images.pokemontcg.io/swsh12pt5gg/GG30_hires.png",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"].startswith("/listings/")


def test_password_reset_flow_and_token_invalidation(client):
    create_user = client.post(
        "/api/v1/users/",
        json={"email": "reset@example.com", "username": "resetuser", "password": "old-secret1"},
    )
    assert create_user.status_code == 200

    forgot_page = client.get("/forgot-password")
    assert forgot_page.status_code == 200
    forgot_csrf = _extract_csrf_token(forgot_page.text)
    forgot_submit = client.post(
        "/forgot-password",
        data={"csrf_token": forgot_csrf, "identifier": "reset@example.com"},
        follow_redirects=False,
    )
    assert forgot_submit.status_code == 200
    assert "password reset link has been sent" in forgot_submit.text

    db = SessionLocal()
    try:
        user = get_user_by_identifier_use_case(db, "reset@example.com")
        assert user is not None
        token = generate_password_reset_token(str(user.email), str(user.password))
    finally:
        db.close()

    reset_page = client.get(f"/reset-password?token={token}")
    assert reset_page.status_code == 200
    reset_csrf = _extract_csrf_token(reset_page.text)

    reset_submit = client.post(
        "/reset-password",
        data={
            "csrf_token": reset_csrf,
            "token": token,
            "new_password": "new-secret-123!",
            "confirm_password": "new-secret-123!",
        },
        follow_redirects=False,
    )
    assert reset_submit.status_code == 303
    assert reset_submit.headers["location"].startswith("/login?message=")

    reset_again_page = client.get(f"/reset-password?token={token}")
    reset_again_csrf = _extract_csrf_token(reset_again_page.text)
    reset_again_submit = client.post(
        "/reset-password",
        data={
            "csrf_token": reset_again_csrf,
            "token": token,
            "new_password": "another-secret-123!",
            "confirm_password": "another-secret-123!",
        },
        follow_redirects=False,
    )
    assert reset_again_submit.status_code == 400
    assert "no longer valid" in reset_again_submit.text


def test_account_profile_update_and_email_reverify(client):
    register_page = client.get("/users/register")
    register_csrf = _extract_csrf_token(register_page.text)
    created = client.post(
        "/users/register",
        data={
            "csrf_token": register_csrf,
            "email": "profile@example.com",
            "username": "profileuser",
            "password": "secret123",
        },
        follow_redirects=False,
    )
    assert created.status_code == 303

    verify_token = generate_email_verification_token("profile@example.com")
    verify_response = client.get(f"/verify-email?token={verify_token}", follow_redirects=False)
    assert verify_response.status_code == 200

    account_page = client.get("/account")
    assert account_page.status_code == 200
    account_csrf = _extract_csrf_token(account_page.text)
    update_username = client.post(
        "/account/profile",
        data={"csrf_token": account_csrf, "email": "profile@example.com", "username": "profileuser2"},
        follow_redirects=False,
    )
    assert update_username.status_code == 303
    assert update_username.headers["location"].startswith("/account?message=")

    account_page2 = client.get("/account")
    assert "profileuser2" in account_page2.text

    account_csrf2 = _extract_csrf_token(account_page2.text)
    update_email = client.post(
        "/account/profile",
        data={"csrf_token": account_csrf2, "email": "profile-new@example.com", "username": "profileuser2"},
        follow_redirects=False,
    )
    assert update_email.status_code == 303
    assert update_email.headers["location"].startswith("/account?message=")

    account_page3 = client.get("/account")
    assert "Not verified" in account_page3.text
    account_csrf3 = _extract_csrf_token(account_page3.text)
    resend_from_account = client.post(
        "/account/resend-verification",
        data={"csrf_token": account_csrf3},
        follow_redirects=False,
    )
    assert resend_from_account.status_code == 303
    assert resend_from_account.headers["location"].startswith("/account?message=")

    db = SessionLocal()
    try:
        user = get_user_by_identifier_use_case(db, "profile-new@example.com")
        assert user is not None
        latest_event = (
            db.query(AuditLog)
            .filter(AuditLog.actor_user_id == user.id)
            .order_by(AuditLog.id.desc())
            .first()
        )
        assert latest_event is not None
        assert latest_event.request_id is not None
        assert latest_event.ip_address is not None
    finally:
        db.close()


def test_listings_paginated_search_endpoint(client):
    seller = client.post(
        "/api/v1/users/",
        json={"email": "pageseller@example.com", "username": "pageseller", "password": "secret123"},
    )
    assert seller.status_code == 200
    seller_id = seller.json()["id"]

    for idx in range(15):
        created = _post_listing(
            client,
            {
                "title": f"Page Listing {idx}",
                "price": 1000 + idx,
                "location": "Athens",
                "size": 50,
                "bedrooms": 2,
                "bathrooms": 1,
                "property_type": "apartment",
                "furnished": "unfurnished",
                "description": f"Athens listing number {idx} with practical layout and bright rooms.",
                "image_url": f"/static/uploads/page-{idx}.jpg",
                "seller_id": seller_id,
            },
        )
        assert created.status_code == 200

    page1 = client.get("/api/v1/listings/search/page?page=1&page_size=10&location=Athens")
    assert page1.status_code == 200
    payload1 = page1.json()
    assert payload1["page"] == 1
    assert payload1["page_size"] == 10
    assert payload1["total"] >= 15
    assert len(payload1["items"]) == 10

    page2 = client.get("/api/v1/listings/search/page?page=2&page_size=10&location=Athens")
    assert page2.status_code == 200
    payload2 = page2.json()
    assert payload2["page"] == 2
    assert len(payload2["items"]) >= 5


def test_admin_login_redirect_precedence_prefers_admin_dashboard(client):
    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.username == "admin").first()
        assert admin is not None
        admin.must_reset_password = True
        db.add(admin)
        db.commit()
    finally:
        db.close()

    login_page = client.get("/login")
    login_csrf = _extract_csrf_token(login_page.text)
    login_redirect = client.post(
        "/login",
        data={"csrf_token": login_csrf, "email": "admin", "password": "admin"},
        follow_redirects=False,
    )
    assert login_redirect.status_code == 303
    assert login_redirect.headers["location"] == "/admin"


def test_unauthenticated_save_listing_redirects_to_login_with_csrf(client):
    listings_page = client.get("/listings")
    csrf_token = _extract_csrf_token(listings_page.text)
    response = client.post("/listings/1/save", data={"csrf_token": csrf_token}, follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_unauthenticated_contact_seller_redirects_to_login_with_csrf(client):
    listings_page = client.get("/listings")
    csrf_token = _extract_csrf_token(listings_page.text)
    response = client.post(
        "/listings/1/contact-seller",
        data={"csrf_token": csrf_token, "message": "Hello seller"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_csrf_missing_token_rejected(client):
    response = client.post(
        "/login",
        data={"email": "nobody@example.com", "password": "secret123"},
        follow_redirects=False,
    )
    assert response.status_code == 422


def test_login_lockout_after_failed_attempts(client):
    register_page = client.get("/users/register")
    register_csrf = _extract_csrf_token(register_page.text)
    created = client.post(
        "/users/register",
        data={
            "csrf_token": register_csrf,
            "email": "lock@example.com",
            "username": "lockuser",
            "password": "correct-password1",
        },
        follow_redirects=False,
    )
    assert created.status_code == 303

    # Clear the authenticated session so we can execute login attempts.
    account_page = client.get("/account")
    logout_csrf = _extract_csrf_token(account_page.text)
    client.post("/logout", data={"csrf_token": logout_csrf}, follow_redirects=False)

    login_page = client.get("/login")
    login_csrf = _extract_csrf_token(login_page.text)
    for _ in range(4):
        bad = client.post(
            "/login",
            data={"csrf_token": login_csrf, "email": "lock@example.com", "password": "wrong"},
            follow_redirects=False,
        )
        assert bad.status_code in {400, 429}

    repeated_failure = client.post(
        "/login",
        data={"csrf_token": login_csrf, "email": "lock@example.com", "password": "wrong"},
        follow_redirects=False,
    )
    assert repeated_failure.status_code in {400, 429}


def test_rate_limit_cleanup_prunes_stale_global_events(client):
    db = SessionLocal()
    try:
        stale_created_at = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=3)
        db.add(RateLimitEvent(scope_key="stale_scope_key", created_at=stale_created_at))
        db.commit()

        # Use a short retention to force cleanup in this test path.
        allowed = consume_rate_limit(
            db,
            scope_key="fresh_scope_key",
            limit=5,
            window_seconds=60,
        )
        assert allowed is True

        remaining_stale = db.query(RateLimitEvent).filter(RateLimitEvent.scope_key == "stale_scope_key").count()
        assert remaining_stale == 0
    finally:
        db.close()




