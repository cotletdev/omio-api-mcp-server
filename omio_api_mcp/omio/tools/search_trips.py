"""Search trips: `POST /GoEuroAPI/rest/api/v5/searches`, then results v2 until complete."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from omio_api_mcp.core.errors import ErrorCode, ToolError
from omio_api_mcp.core.helpers import limit
from omio_api_mcp.core.tools import tool
from omio_api_mcp.omio.tools._search import (
    MODES,
    MODES_INPUT,
    PASSENGERS_INPUT,
    PLACE,
    collect,
    currency_of,
    parse_day,
    passengers_body,
    poll,
    resolve_place,
    results_block,
    start_search,
)

if TYPE_CHECKING:
    from omio_api_mcp.core.context import ToolContext

INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "from": {**PLACE, "description": f"Departure. {PLACE['description']}"},
        "to": {**PLACE, "description": f"Arrival. {PLACE['description']}"},
        "date": {"type": "string", "format": "date", "description": "Departure date, e.g. 2026-11-17."},
        "return_date": {
            "type": "string",
            "format": "date",
            "description": "Return date for a round trip. Pick the return leg with list_return_trips.",
        },
        "passengers": PASSENGERS_INPUT,
        "modes": MODES_INPUT,
        "currency": {
            "type": "string",
            "pattern": "^[A-Z]{3}$",
            "description": "Price currency, e.g. EUR, GBP, USD. Default: EUR.",
        },
        "limit": {"type": "integer", "minimum": 1, "maximum": 100, "description": "1 to 100. Default: 20."},
    },
    "required": ["from", "to", "date"],
    "additionalProperties": False,
}

EXAMPLE_RESPONSE: dict[str, Any] = {
    "search_id": "E3B02A2F5BF1045CD90E06B981AD2E45C",
    "from": {"place_id": "376217", "name": "Berlin"},
    "to": {"place_id": "376946", "name": "Munich"},
    "date": "2026-11-17",
    "return_date": None,
    "complete": True,
    "trips": [
        {
            "trip_id": "E3B02A2F5BF1045CD90E06B981AD2E45C.-1936373539.1524867295158618159.train",
            "mode": "train",
            "operator": "Deutsche Bahn",
            "from": "Berlin Hbf",
            "to": "Munich Hbf",
            "departs": "2026-11-17T10:37:00.000+01:00",
            "arrives": "2026-11-17T15:20:00.000+01:00",
            "duration": "4h 43m",
            "duration_minutes": 283,
            "changes": 0,
            "services": ["ICE 1007"],
            "price": {"amount": 86.0, "currency": "EUR"},
            "bookable_on_omio": True,
        }
    ],
    "modes": {
        "train": {
            "status": "done",
            "results": 5,
            "time_window": [["08:00", "11:55"]],
            "can_extend_earlier": True,
            "can_extend_later": True,
        }
    },
    "total": 1,
}


@tool(
    name="search_trips",
    title="Search trips",
    access="read",
    description="Trains, buses, flights and ferries between two places on a date, with times, duration, changes, "
    "operator and price.",
    details=(
        "Runs an Omio search for one route and date and waits up to 20 seconds for every mode to answer "
        "(complete says whether all did). Each trip has the operator, departure and arrival with their offset, "
        "duration, number of changes and the lowest price for all travelers together. Give each traveler's age "
        "and discount cards (list_discount_cards) in passengers: they change the price. Trains come in a time "
        "window: list_more_trips loads later or earlier ones. With return_date the trips are outbound legs: "
        "pass one to list_return_trips to pick the return. Pass a trip_id to get_trip for its fares."
    ),
    input_schema=INPUT_SCHEMA,
    route="GET /trips/search",
    example_response=EXAMPLE_RESPONSE,
    timeout_s=60,
)
async def search_trips(ctx: ToolContext, args: dict[str, Any]) -> Any:
    day = parse_day(args["date"], "date")
    return_day = parse_day(args["return_date"], "return_date") if args.get("return_date") else None
    if return_day and return_day < day:
        raise ToolError("return_date is before date.", ErrorCode.INVALID_INPUT)
    modes = list(args.get("modes") or MODES)
    origin = await resolve_place(ctx, args["from"], "from")
    destination = await resolve_place(ctx, args["to"], "to")
    if origin["place_id"] == destination["place_id"]:
        raise ToolError("from and to are the same place.", ErrorCode.INVALID_INPUT)
    currency = args.get("currency") or "EUR"
    search_id = await start_search(
        ctx,
        origin=origin["place_id"],
        destination=destination["place_id"],
        day=day,
        return_day=return_day,
        passengers=passengers_body(args.get("passengers")),
        currency=currency,
        first_mode=modes[0],
    )
    answer = await poll(ctx, search_id)
    block = results_block(answer, None)
    trips, per_mode = collect(block, search_id, modes, currency_of(block, currency), round_trip=return_day is not None)
    size = limit(args, 20, 100)
    return {
        "search_id": search_id,
        "from": origin,
        "to": destination,
        "date": day,
        "return_date": return_day,
        "complete": answer.get("status") == "complete",
        "trips": trips[:size],
        "modes": per_mode,
        "total": len(trips),
    }
