"""Get booking: `booking-experience/bookings/{id}/v1`, else `post-booking-api .../v4`."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from omio_api_mcp.core.tools import tool
from omio_api_mcp.omio.tools._booking import BOOKING_ID, booking_row, read_booking

if TYPE_CHECKING:
    from omio_api_mcp.core.context import ToolContext

INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {"booking_id": BOOKING_ID},
    "required": ["booking_id"],
    "additionalProperties": False,
}

EXAMPLE_RESPONSE: dict[str, Any] = {
    "booking_id": "3c1f9b2e-7a4d-4e55-9b0c-2f8e6d1a4b70",
    "status": "reserved",
    "paid": False,
    "route": "Berlin Hbf to Munich Hbf",
    "departs": "2026-11-17T10:37:00+01:00",
    "arrives": "2026-11-17T15:20:00+01:00",
    "legs": [
        {
            "direction": "outbound",
            "mode": "train",
            "operator": "Deutsche Bahn",
            "service": "ICE 1007",
            "from": "Berlin Hbf",
            "to": "Munich Hbf",
            "departs": "2026-11-17T10:37:00+01:00",
            "arrives": "2026-11-17T15:20:00+01:00",
        }
    ],
    "fares": [
        {
            "class": "2nd Class",
            "name": "Super Saver Fare",
            "refund_policy": "non_refundable",
            "exchange_policy": "non_exchangeable",
            "conditions": "This ticket cannot be refunded or exchanged.",
        }
    ],
    "passengers": [{"first_name": "Alex", "last_name": "Morgan", "title": "Mr", "age": 30}],
    "price_breakdown": [
        {"type": "fare", "price": {"amount": 86.0, "currency": "EUR"}, "quantity": 1},
        {"type": "service_fee", "price": {"amount": 4.0, "currency": "EUR"}, "quantity": 1},
    ],
    "total": {"amount": 90.0, "currency": "EUR"},
    "confirmation_email": "alex.morgan@example.com",
    "reserved_until": "2026-10-26T20:42:11.176056475Z",
    "checkout_url": "https://www.omio.com/app/search-frontend/booking/3c1f9b2e-7a4d-4e55-9b0c-2f8e6d1a4b70/checkout?locale=en&origin_domain=com",
}


@tool(
    name="get_booking",
    title="Get booking",
    access="read",
    description="Journey, travelers, fare conditions, status and price of one booking, paid or not yet paid.",
    details=(
        "Returns one booking: legs, travelers, fare class and conditions (refund and exchange policy), the "
        "price breakdown with Omio's service fee and the total. A booking from start_booking stays unpaid "
        "(paid false) until the person pays at checkout_url; reserved_until is when Omio drops its hold on "
        "the seats."
    ),
    input_schema=INPUT_SCHEMA,
    route="GET /bookings/{booking_id}",
    example_response=EXAMPLE_RESPONSE,
)
async def get_booking(ctx: ToolContext, args: dict[str, Any]) -> Any:
    booking_id = args["booking_id"].strip().lower()
    return booking_row(await read_booking(ctx, booking_id), booking_id)
