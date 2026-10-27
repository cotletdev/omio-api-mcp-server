"""Places, passengers, searches and results the Omio search tools share.

A trip id packs what the journey page needs: `{search_id}.{journey_id}.{outbound_id}.{mode}` for a one-way trip,
`...{mode}.r` for an outbound leg of a round-trip search (a return leg still to pick) and `...{mode}.{inbound_id}`
for a picked round trip. The results endpoint answers the full snapshot so far to a plain GET, so polling repeats
it until `status` is `complete`.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING, Any

from omio_api_mcp.core.errors import ErrorCode, ToolError
from omio_api_mcp.omio.client import LOCALE, WEB, api, money

if TYPE_CHECKING:
    from omio_api_mcp.core.context import ToolContext

SUGGESTER = f"{WEB}/suggester-api/v5/position"
SEARCHES = f"{WEB}/GoEuroAPI/rest/api/v5/searches"
RESULTS = f"{WEB}/bff-core-service/search-experience/results/v2"
MODES: tuple[str, ...] = ("train", "bus", "flight", "ferry")
POLL_FOR_S = 20.0
ROUND_TRIP_PENDING = "r"

PLACE: dict[str, Any] = {
    "type": "string",
    "minLength": 2,
    "description": "A place_id from search_places, or a city, station or airport name (the first match is used).",
}
TRIP_ID: dict[str, Any] = {"type": "string", "pattern": r"^[A-Za-z0-9]+\.-?[0-9]+\.-?[0-9]+\.[a-z]+(\.(r|-?[0-9]+))?$"}
MODES_INPUT: dict[str, Any] = {
    "type": "array",
    "items": {"type": "string", "enum": list(MODES)},
    "uniqueItems": True,
    "description": "Any of train, bus, flight, ferry. Default: all.",
}
PASSENGERS_INPUT: dict[str, Any] = {
    "type": "array",
    "minItems": 1,
    "maxItems": 9,
    "items": {
        "type": "object",
        "properties": {
            "age": {"type": "integer", "minimum": 0, "maximum": 120, "description": "Age on the travel date."},
            "discount_cards": {
                "type": "array",
                "maxItems": 3,
                "items": {
                    "type": "object",
                    "properties": {
                        "provider": {"type": "string", "description": "provider from list_discount_cards."},
                        "code": {"type": "string", "description": "card_id from list_discount_cards."},
                    },
                    "required": ["provider", "code"],
                    "additionalProperties": False,
                },
                "description": "Rail and coach discount cards this traveler holds.",
            },
        },
        "required": ["age"],
        "additionalProperties": False,
    },
    "description": "One entry per traveler with their age. Default: one adult aged 30.",
}

# Omio's age ranges (search bundle, 26.10.2026): youth 0-25, adult 26-57, senior 58+. The search refuses the
# types `youth` and `senior` (400): the range carries the group, the type is adult, child or infant.
_RANGES = ((0, 25), (26, 57), (58, 199))
_PLACE_TYPES = {"location": "city", "station": "train_station", "busstation": "bus_station"}


@dataclass(frozen=True)
class TripRef:
    search_id: str
    journey_id: str
    outbound_id: str
    mode: str
    inbound_id: str | None = None
    return_pending: bool = False

    def encode(self) -> str:
        tail = ROUND_TRIP_PENDING if self.return_pending else self.inbound_id
        base = f"{self.search_id}.{self.journey_id}.{self.outbound_id}.{self.mode}"
        return f"{base}.{tail}" if tail else base


def decode_trip(trip_id: str) -> TripRef:
    parts = trip_id.strip().split(".")
    if len(parts) not in (4, 5) or parts[3] not in MODES:
        raise ToolError("trip_id must be a trip_id from search_trips or list_return_trips.", ErrorCode.INVALID_INPUT)
    tail = parts[4] if len(parts) == 5 else None
    return TripRef(
        search_id=parts[0],
        journey_id=parts[1],
        outbound_id=parts[2],
        mode=parts[3],
        inbound_id=tail if tail and tail != ROUND_TRIP_PENDING else None,
        return_pending=tail == ROUND_TRIP_PENDING,
    )


def parse_day(value: str, field: str) -> str:
    try:
        return date.fromisoformat(value.strip()).isoformat()
    except ValueError:
        raise ToolError(f"{field} is a date like 2026-11-17.", ErrorCode.INVALID_INPUT) from None


def place_row(hit: dict[str, Any]) -> dict[str, Any]:
    kind = str(hit.get("type") or "")
    return {
        "place_id": str(hit.get("positionId")),
        "name": hit.get("displayName"),
        "type": _PLACE_TYPES.get(kind, kind),
        "city": hit.get("defaultCityName") or (hit.get("displayName") if kind == "location" else None),
        "country_code": hit.get("countryCode"),
        "time_zone": hit.get("timeZone"),
        "latitude": hit.get("latitude"),
        "longitude": hit.get("longitude"),
    }


async def suggest(ctx: ToolContext, term: str) -> list[dict[str, Any]]:
    answer = await api(ctx, "GET", SUGGESTER, params={"locale": LOCALE, "term": term}, what="the place search")
    return [hit for hit in answer or [] if isinstance(hit, dict) and hit.get("positionId")]


async def resolve_place(ctx: ToolContext, value: str, field: str) -> dict[str, Any]:
    """A place id or name as `{place_id, name}`; a name takes Omio's first suggestion."""
    value = value.strip()
    if value.isdigit():
        answer = await api(ctx, "GET", SUGGESTER, params={"locale": LOCALE, "id": value}, what="the place lookup")
        hits = [hit for hit in answer or [] if isinstance(hit, dict)]
        name = hits[0].get("displayName") if hits else None
        return {"place_id": value, "name": name}
    hits = await suggest(ctx, value)
    if not hits:
        raise ToolError(f"Omio knows no place called {value!r} ({field}). Try search_places.", ErrorCode.INVALID_INPUT)
    return {"place_id": str(hits[0]["positionId"]), "name": hits[0].get("displayName")}


def passengers_body(passengers: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """The search body's `passengers`: type and age range from the age, discount cards as given."""
    body: list[dict[str, Any]] = []
    for traveler in passengers or [{"age": 30}]:
        age = int(traveler["age"])
        low, high = next(r for r in _RANGES if r[0] <= age <= r[1])
        kind = "infant" if age < 2 else "child" if age < 16 else "adult"
        cards = [{"provider": c["provider"], "code": c["code"]} for c in traveler.get("discount_cards") or []]
        body.append(
            {"age": age, "type": kind, "passengerAge": {"min": low, "max": high, "age": age}, "discountCards": cards}
        )
    return body


async def start_search(
    ctx: ToolContext,
    *,
    origin: str,
    destination: str,
    day: str,
    return_day: str | None,
    passengers: list[dict[str, Any]],
    currency: str,
    first_mode: str,
) -> str:
    options: dict[str, Any] = {
        "departurePosition": {"id": int(origin)},
        "arrivalPosition": {"id": int(destination)},
        "departureDate": day,
        "passengers": passengers,
        "userInfo": {"currency": currency, "domain": "com", "identifier": "-", "locale": LOCALE},
        "requestInfo": {"domain": "com"},
        "travelMode": first_mode,
        "travelModes": ["Ferry", "Train", "Bus", "Flight"],
        "abTestParameters": [],
        "includeRoutedConnections": True,
        "enableSplitRoundTrip": True,
        "isRebrand": True,
    }
    if return_day:
        options["returnDate"] = return_day
    answer = await api(ctx, "POST", SEARCHES, body={"searchOptions": options}, what="the search")
    search_id = answer.get("searchId") if isinstance(answer, dict) else None
    if not search_id:
        raise ToolError("Omio did not start the search.", ErrorCode.TARGET_ERROR)
    return str(search_id)


async def results(
    ctx: ToolContext, search_id: str, *, outbound_id: str | None = None, extra: dict[str, Any] | None = None
) -> dict[str, Any]:
    """One results read: outbound, or the return legs of one outbound."""
    params: dict[str, Any] = {"search_id": search_id, "direction": "inbound" if outbound_id else "outbound"}
    if outbound_id:
        params["outbound_id"] = outbound_id
    answer = await api(ctx, "GET", RESULTS, params={**params, **(extra or {})}, what="the search results")
    if not isinstance(answer, dict):
        raise ToolError("Omio answered the search results with nothing.", ErrorCode.TARGET_ERROR)
    return answer


async def poll(
    ctx: ToolContext, search_id: str, *, outbound_id: str | None = None, until_mode: str | None = None
) -> dict[str, Any]:
    """Full snapshots until `complete` (or `until_mode`'s tab is no longer loading), at most POLL_FOR_S."""
    deadline = time.monotonic() + POLL_FOR_S
    while True:
        answer = await results(ctx, search_id, outbound_id=outbound_id)
        done = answer.get("status") == "complete"
        if until_mode:
            tab = (results_block(answer, outbound_id).get("tabs") or {}).get(until_mode) or {}
            done = done or (tab.get("status") != "inprogress" and not tab.get("isLoading"))
        if done or time.monotonic() >= deadline:
            return answer
        await asyncio.sleep(min(max((answer.get("pollAfterMs") or 500) / 1000, 0.3), 2.0))


def results_block(answer: dict[str, Any], outbound_id: str | None) -> dict[str, Any]:
    data = answer.get("data") or {}
    if outbound_id:
        return (data.get("inbounds") or {}).get(outbound_id) or {}
    return data.get("outbounds") or {}


def _duration(minutes: Any) -> str | None:
    if not isinstance(minutes, int):
        return None
    return f"{minutes // 60}h {minutes % 60:02d}m"


def trip_row(card: dict[str, Any], ref: TripRef, currency: str, *, round_trip: bool) -> dict[str, Any]:
    stops = card.get("stops")
    row: dict[str, Any] = {
        "trip_id": ref.encode(),
        "mode": card.get("travelMode"),
        "operator": card.get("carrierCode") or None,
        "from": card.get("departureStationName"),
        "to": card.get("arrivalStationName"),
        "departs": card.get("departureTime"),
        "arrives": card.get("arrivalTime"),
        "duration": _duration(card.get("duration")),
        "duration_minutes": card.get("duration"),
        "changes": int(str(stops)) if str(stops or "").isdigit() else None,
        "services": card.get("trainTypes") or [],
        "price": money(card.get("price"), currency),
        "bookable_on_omio": bool(card.get("isBookable") and card.get("isGoEuroBooking")),
    }
    if round_trip:
        row["round_trip_price"] = money(card.get("totalPrice"), currency)
    return row


def collect(
    block: dict[str, Any], search_id: str, modes: list[str], currency: str, *, round_trip: bool, inbound: bool = False
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Trips of the chosen modes, by departure time, and per mode: total and why it is empty."""
    cards, tabs = block.get("cards") or {}, block.get("tabs") or {}
    trips: list[dict[str, Any]] = []
    per_mode: dict[str, Any] = {}
    for mode in modes:
        tab = tabs.get(mode) or {}
        per_mode[mode] = {
            "status": tab.get("status"),
            "results": tab.get("resultsQty", len(tab.get("cardIds") or [])),
            "time_window": [list(w) for w in tab.get("timeWindows") or []],
            "can_extend_earlier": bool(tab.get("canExtendEarlier")),
            "can_extend_later": bool(tab.get("canExtendLater")),
        }
        for card_id in tab.get("cardIds") or []:
            card = cards.get(card_id)
            if not card:
                continue
            ref = TripRef(
                search_id=search_id,
                journey_id=str(card.get("journeyId")),
                outbound_id=str(card.get("outboundId")),
                mode=mode,
                inbound_id=str(card["inboundId"]) if inbound and card.get("inboundId") else None,
                return_pending=round_trip and not inbound,
            )
            trips.append(trip_row(card, ref, currency, round_trip=round_trip))
    trips.sort(key=lambda trip: str(trip.get("departs") or ""))
    return trips, per_mode


def currency_of(block: dict[str, Any], default: str = "EUR") -> str:
    return str((block.get("searchDetails") or {}).get("currencyCode") or default)
