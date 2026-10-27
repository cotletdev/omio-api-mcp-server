"""Get price calendar: `GET /bff-core-service/discovery/summary-cheapest/v1`."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING, Any

from omio_api_mcp.core.errors import ErrorCode, ToolError
from omio_api_mcp.core.tools import tool
from omio_api_mcp.omio.client import LOCALE, WEB, api, money
from omio_api_mcp.omio.tools._search import MODES, MODES_INPUT, PLACE, parse_day, resolve_place

if TYPE_CHECKING:
    from omio_api_mcp.core.context import ToolContext

MAX_DAYS = 31

INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "from": {**PLACE, "description": f"Departure. {PLACE['description']}"},
        "to": {**PLACE, "description": f"Arrival. {PLACE['description']}"},
        "start_date": {"type": "string", "format": "date", "description": "First day, e.g. 2026-11-10."},
        "end_date": {
            "type": "string",
            "format": "date",
            "description": f"Last day, at most {MAX_DAYS} days after start_date. Default: start_date + 13 days.",
        },
        "adults": {"type": "integer", "minimum": 1, "maximum": 9, "description": "Adult travelers. Default: 1."},
        "modes": MODES_INPUT,
        "currency": {"type": "string", "pattern": "^[A-Z]{3}$", "description": "Default: EUR."},
    },
    "required": ["from", "to", "start_date"],
    "additionalProperties": False,
}

EXAMPLE_RESPONSE: dict[str, Any] = {
    "from": {"place_id": "376217", "name": "Berlin"},
    "to": {"place_id": "376946", "name": "Munich"},
    "days": [
        {
            "date": "2026-11-10",
            "cheapest": {"amount": 21.98, "currency": "EUR"},
            "modes": {
                "train": {"price": {"amount": 60.99, "currency": "EUR"}, "results": 26},
                "bus": {"price": {"amount": 21.98, "currency": "EUR"}, "results": 11},
                "flight": {"price": {"amount": 139.73, "currency": "EUR"}, "results": 32},
            },
        }
    ],
}


@tool(
    name="get_price_calendar",
    title="Get price calendar",
    access="read",
    description="Cheapest one-way price per day and mode between two places, for up to a month.",
    details=(
        "Reads Omio's price calendar: for each day the lowest one-way price per mode and how many results it "
        "had, from searches Omio ran recently, so a price can be some hours old. A mode with no trips that day "
        "is left out. Use it to pick a cheap day, then search_trips for live prices."
    ),
    input_schema=INPUT_SCHEMA,
    route="GET /price-calendar",
    example_response=EXAMPLE_RESPONSE,
)
async def get_price_calendar(ctx: ToolContext, args: dict[str, Any]) -> Any:
    start = parse_day(args["start_date"], "start_date")
    first = date.fromisoformat(start)
    end = parse_day(args["end_date"], "end_date") if args.get("end_date") else None
    last = date.fromisoformat(end) if end else first.fromordinal(first.toordinal() + 13)
    if last < first or (last - first).days > MAX_DAYS:
        raise ToolError(f"end_date must be 0 to {MAX_DAYS} days after start_date.", ErrorCode.INVALID_INPUT)
    modes = list(args.get("modes") or MODES)
    origin = await resolve_place(ctx, args["from"], "from")
    destination = await resolve_place(ctx, args["to"], "to")
    currency = args.get("currency") or "EUR"
    answer = await api(
        ctx,
        "GET",
        f"{WEB}/bff-core-service/discovery/summary-cheapest/v1",
        params={
            "fromId": origin["place_id"],
            "toId": destination["place_id"],
            "locale": LOCALE,
            "currency": currency,
            "adults": int(args.get("adults") or 1),
            "children": 0,
            "infants": 0,
            "travelModes": ",".join(modes),
            "outboundDateStart": first.isoformat(),
            "outboundDateEnd": last.isoformat(),
        },
        what="the price calendar",
    )
    days: list[dict[str, Any]] = []
    for day, by_mode in sorted(((answer or {}).get("data") or {}).items()):
        rows = {
            mode: {"price": money(info.get("priceCents"), currency), "results": info.get("numberOfResults")}
            for mode, info in (by_mode or {}).items()
            if mode in modes and isinstance(info, dict) and info.get("priceCents") and info.get("numberOfResults")
        }
        prices = [row["price"] for row in rows.values() if row["price"]]
        days.append(
            {"date": day, "cheapest": min(prices, key=lambda p: p["amount"]) if prices else None, "modes": rows}
        )
    return {"from": origin, "to": destination, "days": days}
