"""Saved passengers of the account: `passenger-service`, header `x-api-version: v1` in
`client.headers_for`. The account holder is the passenger whose id equals the user id; Omio keeps it first."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from omio_api_mcp.core.errors import ErrorCode, ToolError
from omio_api_mcp.omio.client import PASSENGERS, api

if TYPE_CHECKING:
    from omio_api_mcp.core.context import ToolContext

PASSENGER_ID: dict[str, Any] = {
    "type": "string",
    "pattern": "^[0-9a-f-]{36}$",
    "description": "passenger_id from list_passengers.",
}

# Input field -> Omio field, for the fields add_passenger and update_passenger write.
FIELDS = {
    "title": "title",
    "first_name": "firstName",
    "last_name": "lastName",
    "date_of_birth": "dateOfBirth",
    "email": "email",
    "country_of_residence": "countryOfResidence",
    "country_of_birth": "countryOfBirth",
    "city_of_birth": "cityOfBirth",
    "address_line1": "addressLine1",
    "address_line2": "addressLine2",
    "city": "city",
    "state": "state",
    "zip": "zip",
    "country": "country",
}

COUNTRY: dict[str, Any] = {"type": "string", "pattern": "^[A-Z]{2}$"}
PROPERTIES: dict[str, Any] = {
    "title": {"type": "string", "enum": ["Mr", "Ms"], "description": "Mr or Ms (Mrs/Ms in Omio)."},
    "first_name": {"type": "string", "minLength": 2, "maxLength": 50, "description": "First name, Latin letters."},
    "last_name": {"type": "string", "minLength": 2, "maxLength": 50, "description": "Last name, Latin letters."},
    "date_of_birth": {"type": "string", "format": "date", "description": "Date of birth, e.g. 1980-06-02."},
    "email": {"type": "string", "format": "email", "description": "Email for this traveler's tickets."},
    "country_of_residence": {**COUNTRY, "description": "Country of residence, ISO code like US."},
    "country_of_birth": {**COUNTRY, "description": "Country of birth, ISO code."},
    "city_of_birth": {"type": "string", "maxLength": 100, "description": "City of birth."},
    "address_line1": {"type": "string", "maxLength": 200, "description": "Street and number."},
    "address_line2": {"type": "string", "maxLength": 200, "description": "Address, second line."},
    "city": {"type": "string", "maxLength": 100, "description": "City."},
    "state": {"type": "string", "maxLength": 100, "description": "State or region."},
    "zip": {"type": "string", "maxLength": 20, "description": "Postcode."},
    "country": {**COUNTRY, "description": "Country of the address, ISO code."},
    "discount_cards": {
        "type": "array",
        "maxItems": 5,
        "items": {
            "type": "object",
            "properties": {
                "provider": {"type": "string", "description": "provider from list_discount_cards."},
                "code": {"type": "string", "description": "card_id from list_discount_cards."},
            },
            "required": ["provider", "code"],
            "additionalProperties": False,
        },
        "description": "Discount cards this traveler holds; replaces the saved list.",
    },
}

EXAMPLE_PASSENGER: dict[str, Any] = {
    "passenger_id": "5d2e8c71-1b9a-4f3e-8c6d-0a7b9e4f2c13",
    "account_holder": False,
    "title": "Ms",
    "first_name": "Jamie",
    "last_name": "Morgan",
    "date_of_birth": "1980-06-02",
    "email": None,
    "phone": None,
    "country_of_residence": "US",
    "country_of_birth": None,
    "city_of_birth": None,
    "address": {"line1": None, "line2": None, "city": "Nashville", "state": None, "zip": None, "country": "US"},
    "id_document": None,
    "discount_cards": [{"provider": "deutscheBahnPst", "code": "BAHNCARD50-2"}],
}


def _value(record: dict[str, Any], key: str) -> Any:
    value = record.get(key)
    return value if value not in ("", None) else None


def passenger_row(record: dict[str, Any]) -> dict[str, Any]:
    phone = (
        f"+{record['mobilePhonePrefix'].lstrip('+')} {record['mobilePhoneNumber']}"
        if _value(record, "mobilePhoneNumber") and _value(record, "mobilePhonePrefix")
        else _value(record, "mobilePhoneNumber")
    )
    document = None
    if _value(record, "idDocumentType") or _value(record, "idNumber"):
        document = {
            "type": _value(record, "idDocumentType"),
            "number": _value(record, "idNumber"),
            "issue_country": _value(record, "issueCountry"),
            "expires": _value(record, "expirationDate"),
        }
    return {
        "passenger_id": record.get("id"),
        "account_holder": bool(record.get("id")) and record.get("id") == record.get("userId"),
        "title": _value(record, "title"),
        "first_name": _value(record, "firstName"),
        "last_name": _value(record, "lastName"),
        "date_of_birth": _value(record, "dateOfBirth"),
        "email": _value(record, "email"),
        "phone": phone,
        "country_of_residence": _value(record, "countryOfResidence"),
        "country_of_birth": _value(record, "countryOfBirth"),
        "city_of_birth": _value(record, "cityOfBirth"),
        "address": {
            "line1": _value(record, "addressLine1"),
            "line2": _value(record, "addressLine2"),
            "city": _value(record, "city"),
            "state": _value(record, "state"),
            "zip": _value(record, "zip"),
            "country": _value(record, "country"),
        },
        "id_document": document,
        "discount_cards": [
            {"provider": card.get("provider"), "code": card.get("code")}
            for card in record.get("discountCards") or []
            if isinstance(card, dict)
        ],
    }


def changes(args: dict[str, Any]) -> dict[str, Any]:
    """Omio fields from the tool input; text is trimmed."""
    body = {
        FIELDS[key]: value.strip() if isinstance(value, str) else value for key, value in args.items() if key in FIELDS
    }
    if "discount_cards" in args:
        body["discountCards"] = [{"provider": c["provider"], "code": c["code"]} for c in args["discount_cards"]]
    return body


async def saved(ctx: ToolContext) -> list[dict[str, Any]]:
    answer = await api(ctx, "GET", PASSENGERS, what="the saved passengers")
    return [record for record in answer or [] if isinstance(record, dict)]


async def one(ctx: ToolContext, passenger_id: str) -> dict[str, Any]:
    found = next((record for record in await saved(ctx) if record.get("id") == passenger_id), None)
    if found is None:
        raise ToolError("No saved passenger with that passenger_id: see list_passengers.", ErrorCode.INVALID_INPUT)
    return found
