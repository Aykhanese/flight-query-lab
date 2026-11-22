"""Validate and execute flight database queries."""

import math
from validator import _parse_datetime

_RECORD_KEYS = frozenset({
    "flight_id", "origin", "destination",
    "departure_datetime", "arrival_datetime", "price",
})
_QUERY_KEYS = _RECORD_KEYS | {"min_price", "sort_by", "order", "limit"}
_STRING_KEYS = frozenset({"flight_id", "origin", "destination"})
_TIME_KEYS = frozenset({"departure_datetime", "arrival_datetime"})


def _is_number(value: object) -> bool:
    return (
        isinstance(value, (float, int))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def _valid_query(query: object) -> bool:
    if not isinstance(query, dict):
        return False
    if any(key not in _QUERY_KEYS for key in query):
        return False
    if "order" in query and "sort_by" not in query:
        return False

    for key, value in query.items():
        if key in _STRING_KEYS and not isinstance(value, str):
            return False
        if key in _TIME_KEYS and (
            not isinstance(value, str) or _parse_datetime(value) is None
        ):
            return False
        if key in {"price", "min_price"} and not _is_number(value):
            return False
        if key == "sort_by" and (
            not isinstance(value, str) or value not in _RECORD_KEYS
        ):
            return False
        if key == "order" and value not in ("asc", "desc"):
            return False
        if key == "limit" and (
            not isinstance(value, int)
            or isinstance(value, bool)
            or value < 0
        ):
            return False
    return True


def run_query(db: list[dict], query: dict) -> dict:
    """Return a response object for one query, including invalid queries."""
    if not _valid_query(query):
        return {"query": query, "error": "INVALID_QUERY", "matches": []}

    matching = []
    for flight in db:
        if any(flight[key] != query[key] for key in _STRING_KEYS if key in query):
            continue
        if (
            "departure_datetime" in query
            and flight["departure_datetime"] < query["departure_datetime"]
        ):
            continue
        if (
            "arrival_datetime" in query
            and flight["arrival_datetime"] > query["arrival_datetime"]
        ):
            continue
        if "price" in query and flight["price"] > query["price"]:
            continue
        if "min_price" in query and flight["price"] < query["min_price"]:
            continue
        matching.append(flight)

    if "sort_by" in query:
        matching.sort(
            key=lambda flight: flight[query["sort_by"]],
            reverse=(query.get("order", "asc") == "desc"),
        )
    if "limit" in query:
        matching = matching[:query["limit"]]
    return {"query": query, "matches": matching}


def run_queries(db: list[dict], queries: dict | list) -> list[dict]:
    """Accept a single query or a list; always return a list of responses."""
    if isinstance(queries, dict):
        queries = [queries]
    elif not isinstance(queries, list) or any(
        not isinstance(query, dict) for query in queries
    ):
        raise ValueError("queries must be an object or an array of objects")
    return [run_query(db, query) for query in queries]
