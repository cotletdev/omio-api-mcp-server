"""List bookings: `GET post-booking-api/bookings/booking-transactions/v3`, Your Bookings.

Only an empty list was ever seen (no paid booking, 26.10.2026; unpaid drafts are not listed), so the row reads
the fields a booking transaction has elsewhere (v4) and leaves the rest None.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from omio_api_mcp.core.helpers import limit
from omio_api_mcp.core.tools import tool
from omio_api_mcp.omio.client import POST_BOOKING, amount, api

if TYPE_CHECKING:
    from omio_api_mcp.core.context import ToolContext

INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "status": {
            "type": "string",
            "enum": ["upcoming", "past", "all"],
            "description": "upcoming, past or all. Default: upcoming.",
        },
        "limit": {"type": "integer", "minimum": 1, "maximum": 100, "description": "1 to 100. Default: 20."},
    },
    "additionalProperties": False,
}

EXAMPLE_RESPONSE: dict[str, Any] = {
    "bookings": [
        {
            "booking_id": "3c1f9b2e-7a4d-4e55-9b0c-2f8e6d1a4b70",
            "status": "confirmed",
            "route": "Berlin Hbf to Munich Hbf",
            "departs": "2026-11-17T10:37:00+01:00",
            "operator": "Deutsche Bahn",
            "total": {"amount": 90.0, "currency": "EUR"},
        }
    ]
}


def _first(record: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if record.get(key) not in (None, ""):
            return record[key]
    return None


def _row(record: dict[str, Any]) -> dict[str, Any]:
    segments = [s for r in record.get("ticketReservations") or [] for s in r.get("segments") or []]
    start, end = (segments[0], segments[-1]) if segments else (record, record)
    origin = _first(start, "departureStationName", "departureLocationName", "departurePositionName")
    destination = _first(end, "arrivalStationName", "arrivalLocationName", "arrivalPositionName")
    status = _first(record, "status", "bookingStatus")
    return {
        "booking_id": _first(record, "bookingTransactionId", "bookingSessionId", "bookingId", "id"),
        "status": str(status).lower() if status else None,
        "route": f"{origin} to {destination}" if origin and destination else None,
        "departs": _first(start, "departureDateTime", "departureTime", "departureDate"),
        "operator": _first(start, "carrierName", "companyName"),
        "total": amount(_first(record, "totalPriceInPaymentCurrency", "totalPrice", "price")),
    }


def _upcoming(row: dict[str, Any]) -> bool | None:
    try:
        return datetime.fromisoformat(str(row["departs"]).replace("Z", "+00:00")) >= datetime.now(UTC)
    except (TypeError, ValueError):
        return None


@tool(
    name="list_bookings",
    title="List bookings",
    access="read",
    description="Bookings from Your Bookings with route, departure, operator and status.",
    details=(
        "Reads Your Bookings: the paid trips on the account, upcoming by default, with route, departure, "
        "operator, status and total. A booking started with start_booking and not paid yet is not listed; "
        "read it with get_booking. Use booking_id with get_booking."
    ),
    input_schema=INPUT_SCHEMA,
    route="GET /bookings",
    example_response=EXAMPLE_RESPONSE,
)
async def list_bookings(ctx: ToolContext, args: dict[str, Any]) -> Any:
    answer = await api(ctx, "GET", f"{POST_BOOKING}/bookings/booking-transactions/v3", what="Your Bookings")
    records = answer if isinstance(answer, list) else (answer or {}).get("bookingTransactions") or []
    rows = [_row(record) for record in records if isinstance(record, dict)]
    wanted = args.get("status") or "upcoming"
    if wanted != "all":
        rows = [row for row in rows if _upcoming(row) in (None, wanted == "upcoming")]
    rows.sort(key=lambda row: str(row.get("departs") or ""))
    return {"bookings": rows[: limit(args, 20, 100)]}
