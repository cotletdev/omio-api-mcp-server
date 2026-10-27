"""Search places: `GET /suggester-api/v5/position`."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from omio_api_mcp.core.helpers import limit
from omio_api_mcp.core.tools import tool
from omio_api_mcp.omio.tools._search import place_row, suggest

if TYPE_CHECKING:
    from omio_api_mcp.core.context import ToolContext

_TYPES = ["city", "train_station", "bus_station", "airport", "ferry_terminal"]

INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "query": {"type": "string", "minLength": 2, "maxLength": 100, "description": "City, station or airport name."},
        "types": {
            "type": "array",
            "items": {"type": "string", "enum": _TYPES},
            "uniqueItems": True,
            "description": "Keep only these kinds of place. Default: all.",
        },
        "limit": {"type": "integer", "minimum": 1, "maximum": 20, "description": "1 to 20. Default: 10."},
    },
    "required": ["query"],
    "additionalProperties": False,
}

EXAMPLE_RESPONSE: dict[str, Any] = {
    "places": [
        {
            "place_id": "376946",
            "name": "Munich",
            "type": "city",
            "city": "Munich",
            "country_code": "DE",
            "time_zone": "Europe/Berlin",
            "latitude": 48.13743,
            "longitude": 11.57549,
        },
        {
            "place_id": "329668",
            "name": "Munich Hbf",
            "type": "train_station",
            "city": "Munich",
            "country_code": "DE",
            "time_zone": "Europe/Berlin",
            "latitude": 48.140228,
            "longitude": 11.558338,
        },
    ]
}


@tool(
    name="search_places",
    title="Search places",
    access="read",
    description="Cities, train and bus stations, airports and ferry ports Omio knows, by name.",
    details=(
        "Looks a name up the way Omio's search box does and returns up to 20 places with their place_id, kind, "
        "country and time zone. A city covers all its stations, airports and ports in a search; a station "
        "narrows it. Pass place_id as from or to of search_trips or get_price_calendar."
    ),
    input_schema=INPUT_SCHEMA,
    route="GET /places",
    example_response=EXAMPLE_RESPONSE,
)
async def search_places(ctx: ToolContext, args: dict[str, Any]) -> Any:
    rows = [place_row(hit) for hit in await suggest(ctx, args["query"].strip())]
    if types := args.get("types"):
        rows = [row for row in rows if row["type"] in types]
    return {"places": rows[: limit(args, 10, 20)]}
