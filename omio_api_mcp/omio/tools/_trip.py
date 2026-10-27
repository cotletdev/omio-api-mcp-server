"""One trip's journeys, classes and fare offers: GraphQL `getTrip` and `getAncillariesConfig`.

The page's `getTrip` query is about 9 kB; this one asks only for what the tools return. A round trip on Omio is
two journeys (outbound and inbound), each with its own offers. An offer id is a fare_id.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from omio_api_mcp.core.errors import ErrorCode, ToolError
from omio_api_mcp.omio.client import LOCALE, amount, gql

if TYPE_CHECKING:
    from omio_api_mcp.core.context import ToolContext
    from omio_api_mcp.omio.tools._search import TripRef

TRIP_QUERY = """query getTrip($tripId: ID!, $searchId: ID!, $outboundId: ID!, $inboundId: ID, $locale: String,
    $travelMode: TravelMode, $refreshOffers: Boolean) {
  trip(tripId: $tripId, searchId: $searchId, outboundId: $outboundId, inboundId: $inboundId, locale: $locale,
      refreshOnExpiry: false, travelMode: $travelMode, whiteLabel: false, refreshOffers: $refreshOffers,
      allRoundtrip: false, useCarrierImagesV2: true) {
    overview(withChangeovers: true) {
      tripType arrivalLocationName departureLocationName
      passengersMeta(searchId: $searchId) { count { adult youth senior total } }
    }
    journeys(locale: $locale) {
      id journeyId
      segments { id duration direction travelMode transportId companyName operatingCompanyName
        departureDetails { positionName cityName dateTime positionId }
        arrivalDetails { positionName cityName dateTime positionId } }
      ticketOptions {
        classInfo { details { key title } }
        ticketOffers { bookingType offerId companyName deeplinkUrl
          provider { name displayName }
          priceAmount { currency valueInCents }
          fareDetails { title cancellationDescription validityDescription }
          farePolicies { refundPolicyType exchangePolicyType }
          ticketsLeft }
      }
    }
  }
}"""

ANCILLARIES_QUERY = """query getAncillariesConfig($offerId: ID!, $searchId: ID!, $journeyId: ID!, $outboundId: ID,
    $inboundId: ID) {
  ancillariesConfig(offerId: $offerId, searchId: $searchId, journeyId: $journeyId, outboundId: $outboundId,
      inboundId: $inboundId) {
    ticketCollectionOptions { key name description }
    seatingOption { type required price { currency valueInCents } }
    fareTerms
  }
}"""


async def fetch_trip(ctx: ToolContext, ref: TripRef, *, refresh: bool) -> dict[str, Any]:
    if ref.return_pending:
        raise ToolError(
            "This is the outbound leg of a round trip: pick the return with list_return_trips first.",
            ErrorCode.INVALID_INPUT,
        )
    variables = {
        "tripId": ref.journey_id,
        "searchId": ref.search_id,
        "outboundId": ref.outbound_id,
        "inboundId": ref.inbound_id,
        "locale": LOCALE,
        "travelMode": ref.mode,
        "refreshOffers": refresh,
    }
    data = await gql(ctx, "getTrip", TRIP_QUERY, variables, what="the trip")
    trip = data.get("trip")
    if not isinstance(trip, dict) or not trip.get("journeys"):
        raise ToolError("Omio has no such trip any more: search again.", ErrorCode.TARGET_ERROR)
    return trip


def _policy(value: Any) -> str | None:
    return str(value).lower() if value else None


def _allowed(value: Any) -> bool:
    return bool(value) and not str(value).upper().startswith("NON")


def leg_row(segment: dict[str, Any]) -> dict[str, Any]:
    start, end = segment.get("departureDetails") or {}, segment.get("arrivalDetails") or {}
    return {
        "direction": str(segment.get("direction") or "outbound").lower(),
        "mode": segment.get("travelMode"),
        "operator": segment.get("operatingCompanyName") or segment.get("companyName"),
        "service": segment.get("transportId"),
        "from": start.get("positionName"),
        "to": end.get("positionName"),
        "departs": start.get("dateTime"),
        "arrives": end.get("dateTime"),
        "duration_minutes": segment.get("duration"),
    }


def offers(trip: dict[str, Any]) -> list[tuple[dict[str, Any], dict[str, Any], dict[str, Any]]]:
    """(journey, class info, offer) for every offer of every journey."""
    return [
        (journey, option.get("classInfo") or {}, offer)
        for journey in trip.get("journeys") or []
        for option in journey.get("ticketOptions") or []
        for offer in option.get("ticketOffers") or []
    ]


def direction_of(journey: dict[str, Any]) -> str:
    segments = journey.get("segments") or [{}]
    return str(segments[0].get("direction") or "outbound").lower()


def fare_row(journey: dict[str, Any], class_info: dict[str, Any], offer: dict[str, Any]) -> dict[str, Any]:
    details = (offer.get("fareDetails") or [{}])[0] or {}
    policies = offer.get("farePolicies") or {}
    class_details = (class_info.get("details") or [{}])[0] or {}
    onsite = offer.get("bookingType") == "ONSITE"
    return {
        "fare_id": offer.get("offerId"),
        "direction": direction_of(journey),
        "class": class_details.get("title"),
        "name": details.get("title"),
        "price": amount(offer.get("priceAmount")),
        "seller": (offer.get("provider") or {}).get("displayName") or offer.get("companyName"),
        "refundable": _allowed(policies.get("refundPolicyType")),
        "exchangeable": _allowed(policies.get("exchangePolicyType")),
        "refund_policy": _policy(policies.get("refundPolicyType")),
        "exchange_policy": _policy(policies.get("exchangePolicyType")),
        "conditions": (details.get("cancellationDescription") or "").strip() or None,
        "validity": details.get("validityDescription"),
        "tickets_left": offer.get("ticketsLeft"),
        "bookable_on_omio": onsite,
        "partner_url": None if onsite else offer.get("deeplinkUrl"),
    }


async def extras(
    ctx: ToolContext, ref: TripRef, journey: dict[str, Any], offer: dict[str, Any]
) -> dict[str, Any] | None:
    """Seat reservation, ticket collection and fare terms of one offer; None when Omio has none."""
    variables = {
        "offerId": offer.get("offerId"),
        "searchId": ref.search_id,
        "journeyId": journey.get("id"),
        "outboundId": ref.outbound_id,
        "inboundId": ref.inbound_id,
    }
    data = await gql(ctx, "getAncillariesConfig", ANCILLARIES_QUERY, variables, what="the fare's extras")
    config = data.get("ancillariesConfig")
    if not isinstance(config, dict):
        return None
    seating = config.get("seatingOption") or {}
    return {
        "fare_id": offer.get("offerId"),
        "seat_reservation": {
            "available": bool(seating),
            "required": bool(seating.get("required")),
            "price": amount(seating.get("price")),
        },
        "ticket_collection": [
            option.get("name") for option in config.get("ticketCollectionOptions") or [] if option.get("name")
        ],
        "fare_terms": config.get("fareTerms"),
    }
