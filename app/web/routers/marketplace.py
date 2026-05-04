import secrets
from collections import Counter, defaultdict
from datetime import UTC, datetime
from urllib.parse import quote

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy import extract
from sqlalchemy.orm import Session

from app.db.models.listing import Listing
from app.db.models.order import Order
from app.db.models.user import User
from app.db.session import get_db
from app.services.user_service import get_user_profile
from app.web.auth import SESSION_ROLE_KEY
from app.web.deps import get_session_user_id, is_valid_active_session, is_valid_csrf, template_response

router = APIRouter()

ROLE_PERMISSIONS = [
    {
        "role": "buyer",
        "label": "Buyer",
        "summary": "Browse, save, contact sellers, and buy cards using the simulated wallet.",
        "permissions": [
            "Browse card marketplace",
            "Search and filter cards",
            "View card details and same-game listings",
            "Add/remove wishlist cards",
            "Add/remove cards from cart",
            "Top up virtual wallet balance",
            "Checkout with wallet funds",
            "View order history",
            "Contact sellers",
        ],
    },
    {
        "role": "seller",
        "label": "Seller",
        "summary": "Includes buyer permissions plus listing creation and seller message handling.",
        "permissions": [
            "All buyer permissions",
            "Create card listings",
            "Upload listing image placeholders/files",
            "View seller dashboard metrics",
            "Open seller inbox",
            "Reply to buyer messages",
            "Receive simulated wallet proceeds after sales",
        ],
    },
    {
        "role": "supervisor",
        "label": "Supervisor",
        "summary": "Reviews sales analytics and monthly marketplace reporting.",
        "permissions": [
            "Browse marketplace",
            "View monthly sales report",
            "View total sales and cards sold",
            "View revenue by month",
            "View top-selling cards",
            "View top sellers",
            "View payment/order log summary",
        ],
    },
    {
        "role": "admin",
        "label": "Admin",
        "summary": "Full project management role for demonstration and grading.",
        "permissions": [
            "All buyer, seller, and supervisor visibility",
            "Access admin dashboard",
            "Manage user roles",
            "View users, listings, favorites, inquiries, and payment logs",
            "Edit listing details",
            "Remove listings",
            "Delete non-self users",
            "Review operational alerts and UX metrics",
        ],
    },
]


def _require_user(request: Request, db: Session) -> User | RedirectResponse:
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
    request.session[SESSION_ROLE_KEY] = str(user.role)
    return user


def _cart_ids(request: Request) -> list[int]:
    raw = request.session.get("cart_listing_ids", [])
    if not isinstance(raw, list):
        return []
    ids: list[int] = []
    for item in raw:
        try:
            ids.append(int(item))
        except (TypeError, ValueError):
            continue
    return list(dict.fromkeys(ids))


def _save_cart_ids(request: Request, ids: list[int]) -> None:
    request.session["cart_listing_ids"] = list(dict.fromkeys(ids))


def _is_async_request(request: Request) -> bool:
    return request.headers.get("X-Requested-With") == "fetch"


def _orders_for_user(db: Session, user: User) -> tuple[list[Order], list[Order]]:
    purchases = (
        db.query(Order)
        .filter(Order.buyer_id == user.id)
        .order_by(Order.created_at.desc(), Order.id.desc())
        .limit(20)
        .all()
    )
    sales = (
        db.query(Order)
        .filter(Order.seller_id == user.id)
        .order_by(Order.created_at.desc(), Order.id.desc())
        .limit(20)
        .all()
    )
    return purchases, sales


@router.get("/permissions", response_class=HTMLResponse)
def permissions_page(request: Request, db: Session = Depends(get_db)):
    user = None
    current_user_id = get_session_user_id(request)
    if current_user_id is not None:
        candidate = get_user_profile(db, current_user_id)
        if candidate is not None and is_valid_active_session(request, candidate):
            user = candidate
            request.session[SESSION_ROLE_KEY] = str(user.role)
    return template_response(
        request,
        "permissions.html",
        {
            "user": user,
            "role_permissions": ROLE_PERMISSIONS,
        },
    )


@router.get("/wallet", response_class=HTMLResponse)
def wallet_page(request: Request, db: Session = Depends(get_db), message: str | None = None, error: str | None = None):
    user_or_redirect = _require_user(request, db)
    if isinstance(user_or_redirect, RedirectResponse):
        return user_or_redirect
    user = user_or_redirect
    purchases, sales = _orders_for_user(db, user)
    return template_response(
        request,
        "wallet.html",
        {
            "user": user,
            "purchases": purchases,
            "sales": sales,
            "total_spent": sum(int(order.total_price) for order in purchases),
            "total_earned": sum(int(order.total_price) for order in sales),
            "message": message,
            "error": error,
        },
    )


@router.get("/cart", response_class=HTMLResponse)
def cart_page(request: Request, db: Session = Depends(get_db), message: str | None = None, error: str | None = None):
    user_or_redirect = _require_user(request, db)
    if isinstance(user_or_redirect, RedirectResponse):
        return user_or_redirect
    user = user_or_redirect
    ids = _cart_ids(request)
    listings = db.query(Listing).filter(Listing.id.in_(ids)).all() if ids else []
    total = sum(int(item.price) for item in listings)
    orders = (
        db.query(Order)
        .filter(Order.buyer_id == user.id)
        .order_by(Order.created_at.desc(), Order.id.desc())
        .limit(20)
        .all()
    )
    return template_response(
        request,
        "cart.html",
        {
            "user": user,
            "listings": listings,
            "total": total,
            "orders": orders,
            "message": message,
            "error": error,
        },
    )


@router.post("/cart/add/{listing_id}")
def add_to_cart(request: Request, listing_id: int, csrf_token: str = Form(...), db: Session = Depends(get_db)):
    is_async = _is_async_request(request)
    user_or_redirect = _require_user(request, db)
    if isinstance(user_or_redirect, RedirectResponse):
        if is_async:
            return JSONResponse(status_code=401, content={"ok": False, "redirect": "/login"})
        return user_or_redirect
    if not is_valid_csrf(request, csrf_token):
        if is_async:
            return JSONResponse(status_code=400, content={"ok": False, "message": "Invalid CSRF token"})
        raise HTTPException(status_code=400, detail="Invalid CSRF token")
    listing = db.query(Listing).filter(Listing.id == listing_id).first()
    if listing is None:
        if is_async:
            return JSONResponse(status_code=404, content={"ok": False, "message": "Listing not found"})
        raise HTTPException(status_code=404, detail="Listing not found")
    ids = _cart_ids(request)
    ids.append(listing_id)
    _save_cart_ids(request, ids)
    if is_async:
        return JSONResponse(
            status_code=200,
            content={
                "ok": True,
                "message": "Card added to cart.",
                "cart_count": len(_cart_ids(request)),
                "listing_id": listing_id,
            },
        )
    return RedirectResponse(url=f"/cart?message={quote('Card added to cart.')}", status_code=303)


@router.post("/cart/remove/{listing_id}")
def remove_from_cart(request: Request, listing_id: int, csrf_token: str = Form(...), db: Session = Depends(get_db)):
    user_or_redirect = _require_user(request, db)
    if isinstance(user_or_redirect, RedirectResponse):
        return user_or_redirect
    if not is_valid_csrf(request, csrf_token):
        raise HTTPException(status_code=400, detail="Invalid CSRF token")
    _save_cart_ids(request, [item for item in _cart_ids(request) if item != listing_id])
    return RedirectResponse(url=f"/cart?message={quote('Card removed from cart.')}", status_code=303)


@router.post("/wallet/add")
def add_wallet_funds(
    request: Request,
    csrf_token: str = Form(...),
    amount: int = Form(...),
    next_path: str = Form(default="/cart"),
    db: Session = Depends(get_db),
):
    user_or_redirect = _require_user(request, db)
    if isinstance(user_or_redirect, RedirectResponse):
        return user_or_redirect
    redirect_target = next_path if next_path in {"/cart", "/wallet"} else "/cart"
    if not is_valid_csrf(request, csrf_token):
        raise HTTPException(status_code=400, detail="Invalid CSRF token")
    user = user_or_redirect
    if amount <= 0 or amount > 1000000:
        return RedirectResponse(
            url=f"{redirect_target}?error={quote('Enter a valid wallet top-up amount.')}",
            status_code=303,
        )
    user.balance = int(user.balance or 0) + amount
    db.add(user)
    db.commit()
    return RedirectResponse(url=f"{redirect_target}?message={quote('Wallet balance updated.')}", status_code=303)


@router.post("/wallet/withdraw")
def withdraw_wallet_funds(
    request: Request,
    csrf_token: str = Form(...),
    amount: int = Form(...),
    db: Session = Depends(get_db),
):
    user_or_redirect = _require_user(request, db)
    if isinstance(user_or_redirect, RedirectResponse):
        return user_or_redirect
    if not is_valid_csrf(request, csrf_token):
        raise HTTPException(status_code=400, detail="Invalid CSRF token")
    if amount <= 0:
        return RedirectResponse(
            url=f"/wallet?error={quote('Enter a valid withdrawal amount.')}",
            status_code=303,
        )
    return RedirectResponse(
        url=f"/wallet?error={quote('Withdrawals are shown for UX completeness, but are not supported in this university payment simulation.')}",
        status_code=303,
    )


@router.post("/checkout")
def checkout(request: Request, csrf_token: str = Form(...), db: Session = Depends(get_db)):
    user_or_redirect = _require_user(request, db)
    if isinstance(user_or_redirect, RedirectResponse):
        return user_or_redirect
    if not is_valid_csrf(request, csrf_token):
        raise HTTPException(status_code=400, detail="Invalid CSRF token")
    buyer = user_or_redirect
    ids = _cart_ids(request)
    listings = db.query(Listing).filter(Listing.id.in_(ids)).all() if ids else []
    if not listings:
        return RedirectResponse(url=f"/cart?error={quote('Your cart is empty.')}", status_code=303)
    if any(int(item.seller_id) == int(buyer.id) for item in listings):
        return RedirectResponse(url=f"/cart?error={quote('You cannot buy your own listing.')}", status_code=303)
    if any(int(item.size) <= 0 for item in listings):
        return RedirectResponse(url=f"/cart?error={quote('One or more cards are out of stock.')}", status_code=303)
    total = sum(int(item.price) for item in listings)
    if int(buyer.balance or 0) < total:
        return RedirectResponse(url=f"/cart?error={quote('Not enough wallet balance for checkout.')}", status_code=303)

    buyer.balance = int(buyer.balance or 0) - total
    db.add(buyer)
    for listing in listings:
        seller = db.query(User).filter(User.id == listing.seller_id).first()
        if seller is not None:
            seller.balance = int(seller.balance or 0) + int(listing.price)
            db.add(seller)
        listing.size = max(0, int(listing.size) - 1)
        db.add(listing)
        db.add(
            Order(
                buyer_id=buyer.id,
                seller_id=listing.seller_id,
                listing_id=listing.id,
                quantity=1,
                unit_price=listing.price,
                total_price=listing.price,
                transaction_ref=f"TCG-{secrets.token_hex(8).upper()}",
            )
        )
    db.commit()
    _save_cart_ids(request, [])
    return RedirectResponse(url=f"/cart?message={quote('Checkout completed. Your order history was updated.')}", status_code=303)


@router.get("/reports", response_class=HTMLResponse)
def reports_page(request: Request, month: int | None = None, year: int | None = None, db: Session = Depends(get_db)):
    user_or_redirect = _require_user(request, db)
    if isinstance(user_or_redirect, RedirectResponse):
        return user_or_redirect
    user = user_or_redirect
    if user.role not in {"supervisor", "admin"}:
        return RedirectResponse(url="/dashboard", status_code=303)

    now = datetime.now(UTC)
    selected_year = year or now.year
    selected_month = month or now.month
    orders = (
        db.query(Order)
        .filter(extract("year", Order.created_at) == selected_year)
        .filter(extract("month", Order.created_at) == selected_month)
        .all()
    )
    all_orders = db.query(Order).all()
    listing_lookup = {item.id: item for item in db.query(Listing).all()}
    seller_lookup = {item.id: item for item in db.query(User).all()}

    revenue_by_month: dict[str, int] = defaultdict(int)
    for order in all_orders:
        label = order.created_at.strftime("%Y-%m") if order.created_at else "unknown"
        revenue_by_month[label] += int(order.total_price)

    top_cards = Counter()
    top_sellers = Counter()
    for order in orders:
        listing = listing_lookup.get(order.listing_id)
        seller = seller_lookup.get(order.seller_id)
        top_cards[listing.title if listing else f"Listing #{order.listing_id}"] += int(order.quantity)
        top_sellers[seller.username if seller else f"Seller #{order.seller_id}"] += int(order.total_price)

    report = {
        "total_sales": sum(int(order.total_price) for order in orders),
        "cards_sold": sum(int(order.quantity) for order in orders),
        "order_count": len(orders),
        "average_order_value": (
            sum(int(order.total_price) for order in orders) // len(orders) if orders else 0
        ),
        "active_sellers": len({int(order.seller_id) for order in orders}),
        "revenue_by_month": sorted(revenue_by_month.items()),
        "max_monthly_revenue": max(revenue_by_month.values(), default=0),
        "top_cards": top_cards.most_common(5),
        "top_sellers": top_sellers.most_common(5),
        "payment_logs": sorted(orders, key=lambda item: item.created_at or datetime.min, reverse=True)[:15],
        "month": selected_month,
        "year": selected_year,
    }
    return template_response(request, "reports.html", {"user": user, "report": report})
