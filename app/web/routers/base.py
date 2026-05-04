import logging
from collections import Counter
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.listing_service import list_listings_use_case
from app.web.deps import template_response

router = APIRouter()
logger = logging.getLogger("tcg_trove.web.ux")


@router.get("/", response_class=HTMLResponse)
def home(request: Request, db: Session = Depends(get_db)):
    listings = list_listings_use_case(db)
    games = Counter(item.location for item in listings if item.location)
    seller_ids = {item.seller_id for item in listings if item.seller_id is not None}
    stats = {
        "cards": len(listings),
        "listings": len(listings),
        "sellers": len(seller_ids),
        "games": len(games),
    }
    return template_response(
        request,
        "home.html",
        {
            "listings": listings[:8],
            "stats": stats,
            "popular_games": games.most_common(6),
        },
    )


@router.post("/api/ux-events")
async def capture_ux_events(request: Request):
    payload = await request.json()
    events = payload.get("events")
    if not isinstance(events, list):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"ok": False, "detail": "Invalid events payload"},
        )

    request_id = getattr(request.state, "request_id", None)
    user_id = request.session.get("user_id")
    sanitized_events: list[dict] = []
    for event in events[:25]:
        if not isinstance(event, dict):
            continue
        event_name = str(event.get("name", ""))[:64]
        if not event_name:
            continue
        sanitized_events.append(
            {
                "name": event_name,
                "path": str(event.get("path", ""))[:200],
                "value": event.get("value"),
                "client_ts": event.get("ts"),
                "unit": str(event.get("unit", ""))[:24],
                "severity": str(event.get("severity", ""))[:16],
                "meta": event.get("meta") if isinstance(event.get("meta"), dict) else {},
                "received_at": datetime.now(UTC).isoformat(),
            }
        )

    if sanitized_events:
        ux_events_store = getattr(request.app.state, "ux_events", None)
        if ux_events_store is not None:
            ux_events_store.extend(sanitized_events)
        logger.info(
            "Captured UX telemetry batch",
            extra={
                "request_id": request_id,
                "user_id": user_id,
                "event_count": len(sanitized_events),
                "events": sanitized_events,
            },
        )

    return {"ok": True, "accepted": len(sanitized_events)}
