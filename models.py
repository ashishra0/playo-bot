from dataclasses import dataclass, field


@dataclass
class SearchParams:
    area: str
    date: str | None = None  # YYYY-MM-DD
    time: str | None = None  # HH:MM (24h)
    sport: str = "badminton"


@dataclass
class SlotInfo:
    time: str  # "06:00", "19:00"
    price: float
    available: bool


@dataclass
class CourtAvailability:
    court_name: str
    slots: list[SlotInfo] = field(default_factory=list)


@dataclass
class Court:
    name: str
    area: str
    price: str
    time_slots: list[str] = field(default_factory=list)
    rating: str | None = None
    url: str | None = None
    venue_id: str | None = None
    # None = not fetched/error, [] = no online booking, [...] = has courts
    availability: list[CourtAvailability] | None = None
