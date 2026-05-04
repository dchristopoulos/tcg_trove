import re
import sys
from pathlib import Path

from sqlalchemy import select

# Ensure `app` is importable when this script is run as `python scripts/normalize_listing_locations.py`.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.db.models.listing import Listing
from app.db.session import SessionLocal

_GREEK_CITY_AREA_MAP: dict[tuple[str, str], tuple[str, str]] = {
    ("athens", "kolonaki"): ("Athens", "Kolonaki"),
    ("athens", "chalandri"): ("Athens", "Chalandri"),
    ("athens", "glyfada"): ("Athens", "Glyfada"),
    ("athens", "kifisia"): ("Athens", "Kifisia"),
    ("athens", "marousi"): ("Athens", "Marousi"),
    ("athens", "nea smyrni"): ("Athens", "Nea Smyrni"),
    ("thessaloniki", "center"): ("Thessaloniki", "Center"),
    ("thessaloniki", "kalamaria"): ("Thessaloniki", "Kalamaria"),
    ("thessaloniki", "panorama"): ("Thessaloniki", "Panorama"),
    ("patra", "center"): ("Patra", "Center"),
    ("patra", "waterfront"): ("Patra", "Waterfront"),
    ("piraeus", "center"): ("Piraeus", "Center"),
    ("heraklion", "center"): ("Heraklion", "Center"),
    ("volos", "center"): ("Volos", "Center"),
    ("chania", "old town"): ("Chania", "Old Town"),
    ("corfu", "kanoni"): ("Corfu", "Kanoni"),
    ("ioannina", "lakefront"): ("Ioannina", "Lakefront"),
    ("kalamata", "verga"): ("Kalamata", "Verga"),
    ("larisa", "neapolis"): ("Larisa", "Neapolis"),
    ("mykonos", "ornos"): ("Mykonos", "Ornos"),
    ("nafplio", "old town"): ("Nafplio", "Old Town"),
    ("rethymno", "coast"): ("Rethymno", "Coast"),
    ("rhodes", "old town"): ("Rhodes", "Old Town"),
    ("santorini", "fira"): ("Santorini", "Fira"),
}

_GREEK_CITIES = {city for city, _ in _GREEK_CITY_AREA_MAP}
_DASH_SPLIT_RE = re.compile(r"\s*[-–—]\s*")


def _clean_token(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip())


def _format_token(value: str) -> str:
    return _clean_token(value).title()


def _build_detailed_location(city: str, area: str | None) -> str:
    city_clean = _clean_token(city)
    area_clean = _clean_token(area) if area else "Center"
    key = (city_clean.casefold(), area_clean.casefold())
    mapped = _GREEK_CITY_AREA_MAP.get(key)
    if mapped:
        return f"Greece, {mapped[0]}, {mapped[1]}"
    return f"Greece, {_format_token(city_clean)}, {_format_token(area_clean)}"


def _normalize_location(raw_location: str) -> str | None:
    location = _clean_token(raw_location)
    if not location:
        return None

    parts = [_clean_token(part) for part in location.split(",")]
    if len(parts) >= 3 and parts[0].casefold() == "greece":
        return _build_detailed_location(parts[1], parts[2])

    if len(parts) >= 2:
        if parts[0].casefold() == "greece":
            city = parts[1]
            area = parts[2] if len(parts) >= 3 else "Center"
            return _build_detailed_location(city, area)
        if len(parts) == 2 and parts[0].casefold() in _GREEK_CITIES:
            return _build_detailed_location(parts[0], parts[1])
        return None

    dash_parts = _DASH_SPLIT_RE.split(location, maxsplit=1)
    if len(dash_parts) == 2:
        return _build_detailed_location(dash_parts[0], dash_parts[1] or "Center")

    if location.casefold() in _GREEK_CITIES:
        return _build_detailed_location(location, "Center")

    return None


def main() -> int:
    updated_rows = 0
    with SessionLocal() as db:
        listings = db.execute(select(Listing)).scalars().all()
        for listing in listings:
            normalized = _normalize_location(listing.location)
            if normalized and normalized != listing.location:
                listing.location = normalized
                updated_rows += 1

        if updated_rows > 0:
            db.commit()

    print(f"Updated {updated_rows} listing location rows.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
