"""Start booking: `POST /trip-service/booking/v1` (draft), `GET booking-experience/bookings/{id}/v1`, `PUT
.../passengers/v1`. Stops before payment: no payment method is chosen or sent, nothing is
paid (owner, 26.10.2026). The person pays at checkout_url in a browser.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from omio_api_mcp.core.errors import ErrorCode, ToolError
from omio_api_mcp.core.tools import tool
from omio_api_mcp.omio.client import BOOKING_EXPERIENCE, LOCALE, WEB, api
from omio_api_mcp.omio.tools._booking import booking_row, details_url, read_booking
from omio_api_mcp.omio.tools._passengers import PROPERTIES, saved
from omio_api_mcp.omio.tools._search import TRIP_ID, decode_trip
from omio_api_mcp.omio.tools._trip import direction_of, fetch_trip, offers

if TYPE_CHECKING:
    from omio_api_mcp.core.context import ToolContext

# Booking components this tool fills; any other one (date of birth, ID document, phone ...) goes to the page.
_FILLED = {"name", "email", "countryOfResidence"}
_COMPONENT_NAMES = {
    "dateOfBirth": "date of birth",
    "travelDocument": "ID document",
    "placeOfBirth": "place of birth",
    "phoneNumberV2": "phone number",
    "address": "address",
    "loyaltyCard": "loyalty card",
    "citizenship": "citizenship",
    "visaDocument": "visa",
    "discountCard": "discount card number",
    "selectCard": "card choice",
}

INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "trip_id": {**TRIP_ID, "description": "trip_id from search_trips (one way) or list_return_trips."},
        "fare_ids": {
            "type": "array",
            "items": {"type": "string"},
            "minItems": 1,
            "maxItems": 2,
            "uniqueItems": True,
            "description": "fare_id from get_trip: one, or for a round trip one outbound and one inbound fare.",
        },
        "passengers": {
            "type": "array",
            "minItems": 1,
            "maxItems": 9,
            "items": {
                "type": "object",
                "properties": {
                    "first_name": PROPERTIES["first_name"],
                    "last_name": PROPERTIES["last_name"],
                    "title": PROPERTIES["title"],
                    "country_of_residence": PROPERTIES["country_of_residence"],
                },
                "required": ["first_name", "last_name"],
                "additionalProperties": False,
            },
            "description": "One per traveler of the search, in the search's order. Default: the saved passengers "
            "from list_passengers, account holder first.",
        },
        "saved_passenger_ids": {
            "type": "array",
            "items": {"type": "string", "pattern": "^[0-9a-f-]{36}$"},
            "minItems": 1,
            "maxItems": 9,
            "description": "Instead of passengers: passenger_ids from list_passengers, one per traveler.",
        },
        "email": {
            "type": "string",
            "format": "email",
            "description": "Where Omio sends the tickets after payment. Default: the account's email.",
        },
    },
    "required": ["trip_id", "fare_ids"],
    "additionalProperties": False,
}

EXAMPLE_RESPONSE: dict[str, Any] = {
    "booking_id": "3c1f9b2e-7a4d-4e55-9b0c-2f8e6d1a4b70",
    "status": "reserved",
    "paid": False,
    "route": "Berlin Hbf to Munich Hbf",
    "departs": "2026-11-17T10:37:00+01:00",
    "arrives": "2026-11-17T15:20:00+01:00",
    "legs": [],
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
    "reserved_until": "2026-10-26T20:42:11Z",
    "checkout_url": "https://www.omio.com/app/search-frontend/booking/3c1f9b2e-7a4d-4e55-9b0c-2f8e6d1a4b70/checkout?locale=en&origin_domain=com",
    "missing_details": [],
    "next_step": "Open checkout_url in a browser signed in to this Omio account to review and pay. Nothing is paid "
    "until then.",
}


def _chosen(trip: dict[str, Any], fare_ids: list[str]) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    """(journey, offer) per fare_id; one per journey, all sold on Omio."""
    by_id = {offer.get("offerId"): (journey, offer) for journey, _, offer in offers(trip)}
    picked: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for fare_id in fare_ids:
        if fare_id not in by_id:
            raise ToolError(f"No fare {fare_id} on this trip any more: call get_trip again.", ErrorCode.INVALID_INPUT)
        journey, offer = by_id[fare_id]
        if offer.get("bookingType") != "ONSITE":
            raise ToolError(
                f"This fare is sold on the partner's site, not on Omio: {offer.get('deeplinkUrl')}",
                ErrorCode.INVALID_INPUT,
            )
        picked.append((journey, offer))
    directions = [direction_of(journey) for journey, _ in picked]
    if len(set(directions)) != len(directions) or len(picked) != len(trip.get("journeys") or []):
        raise ToolError("Give one fare_id for each direction of the trip.", ErrorCode.INVALID_INPUT)
    return picked


async def _travelers(ctx: ToolContext, args: dict[str, Any], count: int) -> list[dict[str, Any]]:
    """`{first, last, title, country}` per traveler, from the input or the saved passengers."""
    if args.get("passengers"):
        given = [
            {
                "first": p["first_name"].strip(),
                "last": p["last_name"].strip(),
                "title": p.get("title"),
                "country": p.get("country_of_residence"),
            }
            for p in args["passengers"]
        ]
    else:
        records = await saved(ctx)
        if ids := args.get("saved_passenger_ids"):
            by_id = {record.get("id"): record for record in records}
            if missing := [i for i in ids if i not in by_id]:
                raise ToolError(f"No saved passenger {missing[0]}: see list_passengers.", ErrorCode.INVALID_INPUT)
            records = [by_id[i] for i in ids]
        given = [
            {
                "first": r.get("firstName"),
                "last": r.get("lastName"),
                "title": r.get("title") or None,
                "country": r.get("countryOfResidence") or None,
            }
            for r in records[:count]
        ]
    if len(given) != count:
        raise ToolError(
            f"This trip was searched for {count} traveler(s): give exactly {count} in passengers or "
            "saved_passenger_ids.",
            ErrorCode.INVALID_INPUT,
        )
    return given


def _components(draft: dict[str, Any], traveler: dict[str, Any], email: str, configs: dict[str, Any]) -> dict[str, Any]:
    components: dict[str, Any] = {}
    for kind, entries in (draft.get("components") or {}).items():
        filled: list[dict[str, Any]] = []
        for entry in entries or []:
            if kind == "name":
                config = next((c for c in configs.get("name") or [] if c.get("id") == entry.get("configId")), {})
                title = traveler["title"] or ((config.get("titles") or ["Mr"])[0] if config.get("showTitle") else None)
                filled.append({**entry, "first": traveler["first"], "last": traveler["last"], "titleKey": title})
            elif kind == "email":
                filled.append({**entry, "address": email})
            else:
                config = next((c for c in configs.get(kind) or [] if c.get("id") == entry.get("configId")), {})
                country = traveler["country"] or (config.get("defaultValues") or {}).get("countryCode")
                filled.append({**entry, "countryCode": country})
        components[kind] = filled
    return components


@tool(
    name="start_booking",
    title="Start booking",
    access="write",
    description="Reserve fares with the travelers' names and get the price breakdown and a checkout link. Pays "
    "nothing: the person finishes payment at checkout_url.",
    details=(
        "Starts Omio's checkout for the fares picked in get_trip and fills in the travelers (names, the email "
        "for the tickets, country of residence), then stops before payment: no payment method is chosen and "
        "nothing is charged. Returns the price breakdown (fare and Omio's service fee), the total, how long "
        "Omio holds the seats (reserved_until, about 15 minutes) and checkout_url, where the person reviews "
        "the booking and pays in a browser signed in to this Omio account. When the fare needs more than "
        "names (date of birth, ID document, phone), missing_details lists it and checkout_url opens the "
        "passenger details page to complete them."
    ),
    input_schema=INPUT_SCHEMA,
    route="POST /bookings",
    example_response=EXAMPLE_RESPONSE,
    timeout_s=60,
)
async def start_booking(ctx: ToolContext, args: dict[str, Any]) -> Any:
    ref = decode_trip(args["trip_id"])
    trip = await fetch_trip(ctx, ref, refresh=False)
    picked = _chosen(trip, list(args["fare_ids"]))
    meta = {"journeyId": ref.journey_id, "outboundId": ref.outbound_id, "searchId": ref.search_id}
    if ref.inbound_id:
        meta["inboundId"] = ref.inbound_id
    draft = await api(
        ctx,
        "POST",
        f"{WEB}/trip-service/booking/v1",
        body={
            "journeyId": ref.journey_id,
            "searchId": ref.search_id,
            "locale": LOCALE,
            "platform": "MW",
            "travelMode": ref.mode,
            "offers": [
                {
                    "clickoutMetaData": meta,
                    "offerStoreId": offer.get("offerId"),
                    "provider": (offer.get("provider") or {}).get("name"),
                    "seatReservationOptions": {"selected": False, "preferences": {}},
                }
                for _, offer in picked
            ],
        },
        what="the booking",
    )
    booking_id = (draft or {}).get("bookingTransactionId") if isinstance(draft, dict) else None
    if not booking_id:
        raise ToolError("Omio did not start the booking.", ErrorCode.TARGET_ERROR)
    transaction = (await read_booking(ctx, booking_id)).get("bookingTransaction") or {}
    drafts = transaction.get("passengers") or []
    needed = {kind for p in drafts for kind, entries in (p.get("components") or {}).items() if entries}
    if missing := sorted(needed - _FILLED):
        row = booking_row(await read_booking(ctx, booking_id), booking_id)
        return {
            **row,
            "checkout_url": details_url(booking_id),
            "missing_details": [_COMPONENT_NAMES.get(kind, kind) for kind in missing],
            "next_step": "This fare needs more traveler details. Open checkout_url in a browser signed in to this "
            "Omio account, complete them and pay there. Nothing is paid until then.",
        }
    travelers = await _travelers(ctx, args, len(drafts))
    email = args.get("email") or ""
    if not email:
        me = await api(ctx, "GET", f"{WEB}/iam/users/me/v2", what="the account")
        email = (me or {}).get("email") or ""
    configs = transaction.get("componentConfigs") or {}
    body = {
        "passengers": [
            {"id": d.get("id"), "components": _components(d, t, email, configs), "ageInfo": d.get("ageInfo")}
            for d, t in zip(drafts, travelers, strict=True)
        ],
        "additionalComponents": {"promotionalEmails": {}},
    }
    await api(ctx, "PUT", f"{BOOKING_EXPERIENCE}/{booking_id}/passengers/v1", body=body, what="the travelers")
    row = booking_row(await read_booking(ctx, booking_id), booking_id)
    moved = row["status"] == "price_change"
    return {
        **row,
        "missing_details": [],
        "next_step": ("The operator changed the price since get_trip: total is the new price. " if moved else "")
        + "Open checkout_url in a browser signed in to this Omio account to review and pay. Nothing is paid until "
        "then.",
    }
