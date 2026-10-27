"""Update passenger: `PATCH /passenger-service/users/me/passengers/{id}`."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from omio_api_mcp.core.errors import ErrorCode, ToolError
from omio_api_mcp.core.tools import tool
from omio_api_mcp.omio.client import PASSENGERS, api
from omio_api_mcp.omio.tools._passengers import EXAMPLE_PASSENGER, PASSENGER_ID, PROPERTIES, changes, one, passenger_row

if TYPE_CHECKING:
    from omio_api_mcp.core.context import ToolContext

INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {"passenger_id": PASSENGER_ID, **PROPERTIES},
    "required": ["passenger_id"],
    "additionalProperties": False,
}


@tool(
    name="update_passenger",
    title="Update passenger",
    access="write",
    description="Change a saved traveler's details or discount cards, including the account holder's own.",
    details=(
        "Changes only the fields given on one saved passenger; discount_cards replaces the saved cards. Works "
        "on the account holder too (the profile). Returns the passenger as saved."
    ),
    input_schema=INPUT_SCHEMA,
    route="PATCH /passengers/{passenger_id}",
    example_response=EXAMPLE_PASSENGER,
)
async def update_passenger(ctx: ToolContext, args: dict[str, Any]) -> Any:
    passenger_id = args["passenger_id"]
    body = changes(args)
    if not body:
        raise ToolError("Give at least one field to change.", ErrorCode.INVALID_INPUT)
    await one(ctx, passenger_id)
    await api(ctx, "PATCH", f"{PASSENGERS}/{passenger_id}", body=body, what="the passenger change")
    return passenger_row(await one(ctx, passenger_id))
