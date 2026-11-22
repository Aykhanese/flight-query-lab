"""Airport loading, flight row validation, and record conversion."""

from datetime import datetime
import math
import re

_FLIGHT_ID_PATTERN = re.compile(r"[A-Za-z0-9]{2,8}\Z")
_AIRPORT_PATTERN = re.compile(r"[A-Z]{3}\Z")
_DATETIME_PATTERN = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}\Z")


def load_airports(path: str) -> set[str]:
    """Read a UTF-8 text file containing one airport code per line."""
    with open(path, "r", encoding="utf-8") as airport_file:
        return {
            code
            for line in airport_file
            if (code := line.strip()) and not code.startswith("#")
        }


def _parse_datetime(value: str) -> datetime | None:
    """Return a datetime only for real, exactly formatted YYYY-MM-DD HH:MM."""
    if _DATETIME_PATTERN.fullmatch(value) is None:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d %H:%M")
    except ValueError:
        return None


def validate_row(fields: list[str], airports: set[str]) -> str | None:
    """Return only the FIRST failing validation code (duplicates checked elsewhere)."""
    if len(fields) != 6:
        return "WRONG_FIELD_COUNT"

    flight_id, origin, destination, departure, arrival, price_text = (
        field.strip() for field in fields
    )

    if not all((flight_id, origin, destination, departure, arrival, price_text)):
        return "MISSING_FIELD"
    if _FLIGHT_ID_PATTERN.fullmatch(flight_id) is None:
        return "INVALID_FLIGHT_ID"
    if _AIRPORT_PATTERN.fullmatch(origin) is None or origin not in airports:
        return "INVALID_ORIGIN"
    if _AIRPORT_PATTERN.fullmatch(destination) is None or destination not in airports:
        return "INVALID_DESTINATION"
    if origin == destination:
        return "SAME_ORIGIN_DESTINATION"

    departure_dt = _parse_datetime(departure)
    if departure_dt is None:
        return "INVALID_DEPARTURE"
    arrival_dt = _parse_datetime(arrival)
    if arrival_dt is None:
        return "INVALID_ARRIVAL"
    if arrival_dt <= departure_dt:
        return "ARRIVAL_NOT_AFTER_DEPARTURE"

    try:
        price = float(price_text)
    except ValueError:
        return "INVALID_PRICE"
    if not math.isfinite(price):
        return "INVALID_PRICE"
    if price <= 0:
        return "NON_POSITIVE_PRICE"
    return None


def to_record(fields: list[str]) -> dict:
    """Convert an already valid row into the exactly required JSON schema."""
    flight_id, origin, destination, departure, arrival, price = (
        field.strip() for field in fields
    )
    return {
        "flight_id": flight_id,
        "origin": origin,
        "destination": destination,
        "departure_datetime": departure,
        "arrival_datetime": arrival,
        "price": float(price),
    }
