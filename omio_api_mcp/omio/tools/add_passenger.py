"""Add passenger: `POST /passenger-service/users/me/passengers`."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from omio_api_mcp.core.errors import ErrorCode, ToolError
from omio_api_mcp.core.tools import tool
from omio_api_mcp.omio.client import PASSENGERS, api
from omio_api_mcp.omio.tools._passengers import EXAMPLE_PASSENGER, PROPERTIES, changes, passenger_row

if TYPE_CHECKING:
    from omio_api_mcp.core.context import ToolContext

INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": PROPERTIES,
    "required": ["first_name", "last_name"],
    "additionalProperties": False,
}


@tool(
    name="add_passenger",
    title="Add passenger",
    access="write",
    description="Save a traveler on the account so bookings can use their details.",
    details=(
        "Adds a passenger to the account's saved passengers, as Passenger details in the account does: name, "
        "title, date of birth, contact, address and discount cards. Nobody is told; the details only fill "
        "later bookings."
    ),
    input_schema=INPUT_SCHEMA,
    route="POST /passengers",
    example_response=EXAMPLE_PASSENGER,
)
async def add_passenger(ctx: ToolContext, args: dict[str, Any]) -> Any:
    body = {"discountCards": [], "loyaltyCards": [], **changes(args)}
    record = await api(ctx, "POST", PASSENGERS, body=body, what="the new passenger")
    if not isinstance(record, dict) or not record.get("id"):
        raise ToolError("Omio did not return the new passenger.", ErrorCode.TARGET_ERROR)
    return passenger_row(record)
