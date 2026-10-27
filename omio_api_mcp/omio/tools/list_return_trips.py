"""List return trips: results v2 `direction=inbound&outbound_id=` for one outbound leg."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from omio_api_mcp.core.errors import ErrorCode, ToolError
from omio_api_mcp.core.helpers import limit
from omio_api_mcp.core.tools import tool
from omio_api_mcp.omio.tools._search import (
    MODES,
    MODES_INPUT,
    TRIP_ID,
    collect,
    currency_of,
    decode_trip,
    poll,
    results_block,
)

if TYPE_CHECKING:
    from omio_api_mcp.core.context import ToolContext

INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "trip_id": {**TRIP_ID, "description": "trip_id of an outbound leg from a search_trips with return_date."},
        "modes": MODES_INPUT,
        "limit": {"type": "integer", "minimum": 1, "maximum": 100, "description": "1 to 100. Default: 20."},
    },
    "required": ["trip_id"],
    "additionalProperties": False,
}

EXAMPLE_RESPONSE: dict[str, Any] = {
    "outbound_trip_id": "L0FF5CDD6179D4BBBB8BDDF4ECCBD6970.-1936373539.1524867295158618159.train.r",
    "complete": True,
    "trips": [
        {
            "trip_id": "L0FF5CDD6179D4BBBB8BDDF4ECCBD6970.-1337944314.1524867295158618159.train.751660458884122339",
            "mode": "train",
            "operator": "Deutsche Bahn",
            "from": "Munich Hbf",
            "to": "Berlin Hbf",
            "departs": "2026-11-20T13:12:00.000+01:00",
            "arrives": "2026-11-20T18:05:00.000+01:00",
            "duration": "4h 53m",
            "duration_minutes": 293,
            "changes": 0,
            "services": ["ICE 706"],
            "price": {"amount": 83.0, "currency": "EUR"},
            "bookable_on_omio": True,
            "round_trip_price": {"amount": 169.0, "currency": "EUR"},
        }
    ],
    "total": 1,
}


@tool(
    name="list_return_trips",
    title="List return trips",
    access="read",
    description="Return legs Omio offers with one outbound leg of a round-trip search, with the round-trip price.",
    details=(
        "For a search_trips run with return_date: the return legs that go with the chosen outbound trip, by "
        "departure time. price is the return leg alone, round_trip_price both legs together. Each trip_id here "
        "covers the whole round trip: pass it to get_trip for the fares of both directions."
    ),
    input_schema=INPUT_SCHEMA,
    route="GET /trips/{trip_id}/return-trips",
    example_response=EXAMPLE_RESPONSE,
    timeout_s=60,
)
async def list_return_trips(ctx: ToolContext, args: dict[str, Any]) -> Any:
    ref = decode_trip(args["trip_id"])
    if not ref.return_pending:
        raise ToolError(
            "trip_id is not an outbound leg of a round trip: run search_trips with return_date.",
            ErrorCode.INVALID_INPUT,
        )
    answer = await poll(ctx, ref.search_id, outbound_id=ref.outbound_id)
    block = results_block(answer, ref.outbound_id)
    trips, _ = collect(
        block,
        ref.search_id,
        list(args.get("modes") or MODES),
        currency_of(block),
        round_trip=True,
        inbound=True,
    )
    size = limit(args, 20, 100)
    return {
        "outbound_trip_id": ref.encode(),
        "complete": answer.get("status") == "complete",
        "trips": trips[:size],
        "total": len(trips),
    }
