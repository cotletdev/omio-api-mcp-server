"""Get trip: GraphQL `getTrip` and `getAncillariesConfig` for one fare."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from omio_api_mcp.core.errors import ErrorCode, ToolError
from omio_api_mcp.core.tools import tool
from omio_api_mcp.omio.tools._search import TRIP_ID, decode_trip
from omio_api_mcp.omio.tools._trip import extras, fare_row, fetch_trip, leg_row, offers

if TYPE_CHECKING:
    from omio_api_mcp.core.context import ToolContext

INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "trip_id": {**TRIP_ID, "description": "trip_id from search_trips (one way) or list_return_trips."},
        "fare_id": {
            "type": "string",
            "description": "A fare_id of this trip to read its seat reservation and ticket options. Default: the "
            "cheapest fare bookable on Omio.",
        },
    },
    "required": ["trip_id"],
    "additionalProperties": False,
}

EXAMPLE_RESPONSE: dict[str, Any] = {
    "trip_id": "E3B02A2F5BF1045CD90E06B981AD2E45C.-1936373539.1524867295158618159.train",
    "trip_type": "oneway",
    "from": "Berlin",
    "to": "Munich",
    "travelers": 1,
    "legs": [
        {
            "direction": "outbound",
            "mode": "train",
            "operator": "Deutsche Bahn",
            "service": "ICE 1007",
            "from": "Berlin Hbf",
            "to": "München Hbf",
            "departs": "2026-11-17T10:37:00.000+01:00",
            "arrives": "2026-11-17T15:20:00.000+01:00",
            "duration_minutes": 283,
        }
    ],
    "fares": [
        {
            "fare_id": "R::4c2b8e19-bc9c-4e19-8835-c4b49b59ef3c::3eda3049-e345-4fd7-a5cf-00f65104c169",
            "direction": "outbound",
            "class": "2nd Class",
            "name": "Super Saver Fare",
            "price": {"amount": 86.0, "currency": "EUR"},
            "seller": "Deutsche Bahn",
            "refundable": False,
            "exchangeable": False,
            "refund_policy": "non_refundable",
            "exchange_policy": "non_exchangeable",
            "conditions": "This ticket cannot be refunded or exchanged.",
            "validity": "Ticket is valid for both selected train and any local transport for the same route.",
            "tickets_left": 10,
            "bookable_on_omio": True,
            "partner_url": None,
        }
    ],
    "extras": {
        "fare_id": "R::4c2b8e19-bc9c-4e19-8835-c4b49b59ef3c::3eda3049-e345-4fd7-a5cf-00f65104c169",
        "seat_reservation": {"available": True, "required": False, "price": {"amount": 5.5, "currency": "EUR"}},
        "ticket_collection": [],
        "fare_terms": None,
    },
}


@tool(
    name="get_trip",
    title="Get trip",
    access="read",
    description="Legs of one trip and its fare options with their conditions: class, price, refundable, exchangeable.",
    details=(
        "Returns the legs of one search result and every fare Omio offers for it, per direction on a round "
        "trip: class, fare name, price for all travelers, whether it can be refunded or exchanged, the "
        "conditions in Omio's words and tickets left. Prices are refreshed with the operator. extras shows "
        "the seat reservation price and ticket options of fare_id (default: the cheapest fare). A fare with "
        "bookable_on_omio false is sold on the partner's site at partner_url. Pass fare_ids to start_booking."
    ),
    input_schema=INPUT_SCHEMA,
    route="GET /trips/{trip_id}",
    example_response=EXAMPLE_RESPONSE,
)
async def get_trip(ctx: ToolContext, args: dict[str, Any]) -> Any:
    ref = decode_trip(args["trip_id"])
    trip = await fetch_trip(ctx, ref, refresh=True)
    found = offers(trip)
    fares = [fare_row(*item) for item in found]
    wanted = args.get("fare_id")
    if wanted:
        chosen = next((item for item in found if item[2].get("offerId") == wanted), None)
        if chosen is None:
            raise ToolError("No fare with that fare_id on this trip: take one from fares.", ErrorCode.INVALID_INPUT)
    else:
        onsite = [item for item in found if item[2].get("bookingType") == "ONSITE"]
        chosen = min(onsite, key=lambda item: (item[2].get("priceAmount") or {}).get("valueInCents") or 0, default=None)
    overview = trip.get("overview") or {}
    count = ((overview.get("passengersMeta") or {}).get("count") or {}).get("total")
    return {
        "trip_id": ref.encode(),
        "trip_type": overview.get("tripType"),
        "from": overview.get("departureLocationName"),
        "to": overview.get("arrivalLocationName"),
        "travelers": count,
        "legs": [
            leg_row(segment) for journey in trip.get("journeys") or [] for segment in journey.get("segments") or []
        ],
        "fares": fares,
        "extras": await extras(ctx, ref, chosen[0], chosen[2]) if chosen else None,
    }
