"""List passengers: `GET /passenger-service/users/me/passengers`."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from omio_api_mcp.core.tools import tool
from omio_api_mcp.omio.tools._passengers import EXAMPLE_PASSENGER, passenger_row, saved

if TYPE_CHECKING:
    from omio_api_mcp.core.context import ToolContext

INPUT_SCHEMA: dict[str, Any] = {"type": "object", "properties": {}, "additionalProperties": False}


@tool(
    name="list_passengers",
    title="List passengers",
    access="read",
    description="Travelers saved on the account, the account holder first, with their details and discount cards.",
    details=(
        "Lists the passengers saved under Passenger details: name, title, date of birth, contact, address, ID "
        "document and discount cards. account_holder marks the account's own profile. start_booking can fill a "
        "booking from saved_passenger_ids."
    ),
    input_schema=INPUT_SCHEMA,
    route="GET /passengers",
    example_response={"passengers": [EXAMPLE_PASSENGER]},
)
async def list_passengers(ctx: ToolContext, args: dict[str, Any]) -> Any:
    del args
    return {"passengers": [passenger_row(record) for record in await saved(ctx)]}
