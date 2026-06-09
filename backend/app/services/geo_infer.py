"""Geo inference (WP10): infer a city/area from mention text using a known-place
table. Meta gives only city-level geo, and free text rarely has finer detail, so
we infer at city granularity. CITY_COORDS also powers the India map (WP4)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models.mention import Mention

log = get_logger("services.geo_infer")

# Major Indian cities -> (lat, lon). Extend as needed; used for inference + the map.
CITY_COORDS: dict[str, tuple[float, float]] = {
    "Mumbai": (19.0760, 72.8777),
    "Pune": (18.5204, 73.8567),
    "Nagpur": (21.1458, 79.0882),
    "Nashik": (19.9975, 73.7898),
    "Aurangabad": (19.8762, 75.3433),
    "Thane": (19.2183, 72.9781),
    "Delhi": (28.7041, 77.1025),
    "Bengaluru": (12.9716, 77.5946),
    "Hyderabad": (17.3850, 78.4867),
    "Chennai": (13.0827, 80.2707),
    "Kolkata": (22.5726, 88.3639),
    "Ahmedabad": (23.0225, 72.5714),
    "Jaipur": (26.9124, 75.7873),
    "Lucknow": (26.8467, 80.9462),
}

# Demo constituency lookup (city -> constituency/area). Replace with a real table.
CITY_TO_AREA: dict[str, str] = {
    "Pune": "Pune Cantonment",
    "Mumbai": "Mumbai South",
    "Nagpur": "Nagpur West",
    "Nashik": "Nashik Central",
    "Aurangabad": "Aurangabad East",
    "Thane": "Thane City",
}


def infer_location(text: str) -> tuple[str | None, str | None]:
    """Return (city, area) inferred from text, or (None, None) if no known city found."""
    low = (text or "").lower()
    for city in CITY_COORDS:
        if city.lower() in low:
            return city, CITY_TO_AREA.get(city)
    return None, None


def assign_geo_recent(db: Session, politician_id: int, limit: int = 500) -> int:
    """Infer + store city/area for recent mentions that have none yet."""
    mentions = (
        db.execute(
            select(Mention)
            .where(
                Mention.politician_id == politician_id,
                Mention.inferred_city.is_(None),
                Mention.raw_text.is_not(None),
            )
            .limit(limit)
        )
        .scalars()
        .all()
    )
    updated = 0
    for m in mentions:
        city, area = infer_location(m.raw_text or "")
        if city:
            m.inferred_city = city
            m.inferred_area = area
            updated += 1
    db.commit()
    log.info("geo_assigned", politician_id=politician_id, updated=updated)
    return updated
