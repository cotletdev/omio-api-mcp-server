"""A booking transaction as the tools return it.

`booking-experience/bookings/{id}/v1` answers for drafts (`INITIALISED`, `RESERVED` after passengers) with the
journey (`ticketReservations[].segments`), fares, passengers and `priceBreakdown`. A paid booking was never
seen (the owner forbids payments, 26.10.2026): `post-booking-api .../v4` is the fallback and carries no segments.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from omio_api_mcp.core.errors import ErrorCode, ToolError
from omio_api_mcp.omio.client import BOOKING_EXPERIENCE, LOCALE, POST_BOOKING, WEB, amount, api_status

if TYPE_CHECKING:
    from omio_api_mcp.core.context import ToolContext

BOOKING_ID: dict[str, Any] = {
    "type": "string",
    "pattern": "^[0-9a-f-]{36}$",
    "description": "booking_id from list_bookings or start_booking.",
}
# Seen on drafts (26.10.2026). PRICE_CHANGE: the operator's price moved since get_trip; the checkout shows the new one.
UNPAID = {"INITIALISED", "RESERVED", "PRICE_CHANGE"}
_TYPES = {"FARE": "fare", "SERVICE_FEE": "service_fee"}


def checkout_url(booking_id: str) -> str:
    return f"{WEB}/app/search-frontend/booking/{booking_id}/checkout?locale={LOCALE}&origin_domain=com"


def details_url(booking_id: str) -> str:
    return f"{WEB}/app/search-frontend/booking/{booking_id}/passenger-details?locale={LOCALE}&origin_domain=com"


async def read_booking(ctx: ToolContext, booking_id: str) -> dict[str, Any]:
    """`{bookingTransaction, ticketReservations}` from booking-experience, else the post-booking v4 record."""
    status, answer = await api_status(ctx, "GET", f"{BOOKING_EXPERIENCE}/{booking_id}/v1")
    if status == 200 and isinstance(answer, dict) and answer.get("bookingTransaction"):
        return answer
    status, answer = await api_status(ctx, "GET", f"{POST_BOOKING}/bookings/booking-transaction/{booking_id}/v4")
    if status == 200 and isinstance(answer, dict) and answer.get("status"):
        return {"bookingTransaction": answer, "ticketReservations": []}
    if status in (400, 404):
        raise ToolError("No booking with that booking_id on this account.", ErrorCode.INVALID_INPUT)
    raise ToolError("Omio did not answer for this booking.", ErrorCode.TARGET_ERROR)


def _name(passenger: dict[str, Any]) -> dict[str, Any]:
    name = ((passenger.get("components") or {}).get("name") or [{}])[0] or {}
    age = (passenger.get("ageInfo") or {}).get("age")
    return {"first_name": name.get("first"), "last_name": name.get("last"), "title": name.get("titleKey"), "age": age}


def booking_row(answer: dict[str, Any], booking_id: str) -> dict[str, Any]:
    transaction = answer.get("bookingTransaction") or {}
    reservations = answer.get("ticketReservations") or []
    segments = sorted(
        (segment for reservation in reservations for segment in reservation.get("segments") or []),
        key=lambda s: (s.get("direction") != "outbound", str(s.get("departureDateTime") or "")),
    )
    breakdown = [
        {
            "type": _TYPES.get(str(item.get("type")), str(item.get("type") or "").lower()),
            "price": amount(item.get("price")),
            "quantity": item.get("quantity"),
        }
        for item in transaction.get("priceBreakdown") or []
    ]
    status = str(transaction.get("status") or "")
    first, last = (segments[0], segments[-1]) if segments else ({}, {})
    outbound = [s for s in segments if s.get("direction") == "outbound"] or segments
    route = None
    if outbound:
        route = f"{outbound[0].get('departureStationName')} to {outbound[-1].get('arrivalStationName')}"
    return {
        "booking_id": booking_id,
        "status": status.lower() or None,
        "paid": status not in UNPAID,
        "route": route,
        "departs": first.get("departureDateTime"),
        "arrives": last.get("arrivalDateTime"),
        "legs": [
            {
                "direction": segment.get("direction"),
                "mode": segment.get("travelMode"),
                "operator": segment.get("carrierName"),
                "service": segment.get("vehicleId"),
                "from": segment.get("departureStationName"),
                "to": segment.get("arrivalStationName"),
                "departs": segment.get("departureDateTime"),
                "arrives": segment.get("arrivalDateTime"),
            }
            for segment in segments
        ],
        "fares": [
            {
                "class": ", ".join(c.get("name") or "" for c in reservation.get("classes") or []) or None,
                "name": ", ".join(f.get("name") or "" for f in reservation.get("fares") or []) or None,
                "refund_policy": str(reservation.get("refundPolicyType") or "").lower() or None,
                "exchange_policy": str(reservation.get("exchangePolicyType") or "").lower() or None,
                "conditions": ((reservation.get("fares") or [{}])[0].get("cancellationPolicy") or "").strip() or None,
            }
            for reservation in reservations
        ],
        "passengers": [_name(p) for p in transaction.get("passengers") or []],
        "price_breakdown": breakdown,
        "total": amount(
            transaction.get("totalPriceInPaymentCurrency") or transaction.get("totalPriceInDisplayCurrency")
        ),
        "confirmation_email": transaction.get("confirmationEmail"),
        "reserved_until": transaction.get("reservationValidUntil") if status in UNPAID else None,
        "checkout_url": checkout_url(booking_id) if status in UNPAID else None,
    }
