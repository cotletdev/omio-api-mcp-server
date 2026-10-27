"""Delete passenger: `DELETE /passenger-service/users/me/passengers/{id}`."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from omio_api_mcp.core.errors import ErrorCode, ToolError
from omio_api_mcp.core.tools import tool
from omio_api_mcp.omio.client import PASSENGERS, api
from omio_api_mcp.omio.tools._passengers import PASSENGER_ID, one

if TYPE_CHECKING:
    from omio_api_mcp.core.context import ToolContext

INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {"passenger_id": PASSENGER_ID},
    "required": ["passenger_id"],
    "additionalProperties": False,
}


@tool(
    name="delete_passenger",
    title="Delete passenger",
    access="write",
    description="Remove a saved traveler from the account. The account holder cannot be removed.",
    details="Deletes one saved passenger and their discount cards. Bookings already made keep their travelers.",
    input_schema=INPUT_SCHEMA,
    route="DELETE /passengers/{passenger_id}",
    example_response={"passenger_id": "5d2e8c71-1b9a-4f3e-8c6d-0a7b9e4f2c13", "deleted": True},
)
async def delete_passenger(ctx: ToolContext, args: dict[str, Any]) -> Any:
    passenger_id = args["passenger_id"]
    record = await one(ctx, passenger_id)
    if record.get("id") == record.get("userId"):
        raise ToolError("The account holder cannot be deleted.", ErrorCode.INVALID_INPUT)
    await api(ctx, "DELETE", f"{PASSENGERS}/{passenger_id}", body={}, what="the passenger removal")
    return {"passenger_id": passenger_id, "deleted": True}
