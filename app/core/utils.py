import logging

logger = logging.getLogger("tcg_trove.utils")


def parse_optional_int_query(value: str | None) -> int | None:
    """Parses an optional integer query parameter, returning None if empty or invalid."""
    if value is None:
        return None
    raw = value.strip()
    if not raw:
        return None
    try:
        return int(raw)
    except (ValueError, TypeError):
        return None


def parse_listing_ids(ids: str) -> list[int]:
    """Parses a comma-separated string of integer IDs into a unique list of integers.
    Raises ValueError if no valid IDs are found.
    """
    if not ids.strip():
        raise ValueError("Empty ID string")
    values: list[int] = []
    for raw in ids.split(","):
        token = raw.strip()
        if not token:
            continue
        try:
            values.append(int(token))
        except (ValueError, TypeError):
            raise ValueError(f"Invalid ID token: {token}")
    deduped = list(dict.fromkeys(values))
    if not deduped:
        raise ValueError("No valid IDs found")
    return deduped
