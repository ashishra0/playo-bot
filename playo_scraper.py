import asyncio
import logging
from dataclasses import dataclass

import httpx

from config import (
    MAX_SEARCH_RESULTS,
    PLAYO_AVAILABILITY_API,
    PLAYO_MOBILE,
    PLAYO_SEARCH_API,
    SCRAPER_BACKOFF_BASE,
    SCRAPER_RETRIES,
)
from models import Court, CourtAvailability, SearchParams, SlotInfo

log = logging.getLogger(__name__)

DEFAULT_CITY = "pune"

SPORT_IDS: dict[str, str] = {
    "badminton": "SP5",
    "football": "SP2",
    "cricket": "SP3",
    "basketball": "SP3",
    "tennis": "SP4",
    "squash": "SP6",
    "tabletennis": "SP7",
    "tt": "SP7",
    "volleyball": "SP8",
    "swimming": "SP9",
}
DEFAULT_SPORT = "badminton"

# City center coordinates for Playo API (lat, lng)
CITY_COORDS: dict[str, tuple[float, float]] = {
    "bangalore": (12.9716, 77.5946),
    "bengaluru": (12.9716, 77.5946),
    "pune": (18.5204, 73.8567),
    "mumbai": (19.0760, 72.8777),
    "delhi": (28.6139, 77.2090),
    "hyderabad": (17.3850, 78.4867),
    "chennai": (13.0827, 80.2707),
    "kolkata": (22.5726, 88.3639),
    "gurgaon": (28.4595, 77.0266),
    "noida": (28.5355, 77.3910),
}


@dataclass
class SearchResult:
    courts: list[Court]
    exact_area_match: bool


def _venue_to_court(venue: dict) -> Court:
    timings = venue.get("timings") or ""
    return Court(
        name=venue.get("name", "Unknown"),
        area=venue.get("area", ""),
        price="See venue page",
        time_slots=[timings] if timings else [],
        rating=f"{venue['avgRating']:.1f} ({venue.get('ratingCount', 0)})"
        if venue.get("avgRating")
        else None,
        url=venue.get("fullLink"),
        venue_id=venue.get("venueId"),
    )


async def _fetch_availability(
    client: httpx.AsyncClient, venue_id: str, date_str: str, time_filter: str | None
) -> list[CourtAvailability] | None:
    """Fetch court availability for a venue on a given date.

    Returns None on API error, empty list if venue has no online court bookings.
    """
    url = f"{PLAYO_AVAILABILITY_API}/{venue_id}/{BADMINTON_SPORT_ID}/{date_str}"
    try:
        resp = await client.get(
            url,
            params={"mobile": PLAYO_MOBILE},
            headers={"User-Agent": "Mozilla/5.0"},
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        log.warning("Availability fetch failed for %s: %s", venue_id, exc)
        return None

    if data.get("requestStatus") != 1:
        return None

    courts: list[CourtAvailability] = []
    for court_info in data.get("data", {}).get("courtInfo", []):
        court_name = court_info.get("courtName", "Court")
        slots: list[SlotInfo] = []
        for slot in court_info.get("slotInfo", []):
            slot_time = slot["time"][:5]  # "06:00:00" -> "06:00"
            available = slot["status"] == 1
            price = slot["price"]

            if time_filter:
                if slot_time != time_filter:
                    continue

            slots.append(SlotInfo(time=slot_time, price=price, available=available))

        if slots:
            courts.append(CourtAvailability(court_name=court_name, slots=slots))

    return courts


async def search_courts(params: SearchParams, city: str = DEFAULT_CITY) -> SearchResult:
    """Search for badminton courts via Playo API."""
    coords = CITY_COORDS.get(city.lower())
    if not coords:
        raise ValueError(
            f"Unknown city '{city}'. Supported: {', '.join(sorted(CITY_COORDS))}"
        )

    sport_key = (params.sport or DEFAULT_SPORT).lower().replace(" ", "")
    sport_id = SPORT_IDS.get(sport_key)
    if not sport_id:
        raise ValueError(
            f"Unknown sport '{params.sport}'. Supported: {', '.join(SPORT_IDS)}"
        )

    api_params = {
        "lat": coords[0],
        "lng": coords[1],
        "searchQuery": params.area,
        "category": "venue",
        "sportId": sport_id,
    }
    log.info("Searching Playo API: %s", api_params)

    last_exc: Exception | None = None
    for attempt in range(1, SCRAPER_RETRIES + 1):
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
                resp = await client.get(
                    PLAYO_SEARCH_API,
                    params=api_params,
                    headers={"User-Agent": "Mozilla/5.0"},
                )
                resp.raise_for_status()

                data = resp.json()
                venues = data.get("data", {}).get("venueList", [])
                log.info("API returned %d venues for '%s'", len(venues), params.area)

                courts = [_venue_to_court(v) for v in venues[:MAX_SEARCH_RESULTS]]
                exact_match = len(venues) > 0

                # If date + time given, fetch availability for each venue
                if params.date and params.time:
                    tasks = [
                        _fetch_availability(client, c.venue_id, params.date, params.time)
                        for c in courts
                        if c.venue_id
                    ]
                    results = await asyncio.gather(*tasks)
                    for court, avail in zip(courts, results):
                        court.availability = avail

                return SearchResult(courts=courts, exact_area_match=exact_match)

        except Exception as exc:
            last_exc = exc
            if attempt < SCRAPER_RETRIES:
                wait = SCRAPER_BACKOFF_BASE**attempt
                log.warning("Attempt %d failed (%s), retrying in %ds...", attempt, exc, wait)
                await asyncio.sleep(wait)
            else:
                log.error("All %d attempts failed", SCRAPER_RETRIES)

    raise RuntimeError(f"Failed after {SCRAPER_RETRIES} attempts: {last_exc}")
