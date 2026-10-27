"""Get account: `GET /iam/users/me/v2` and `GET /crm-proxy/opt-in/me/v1`."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from omio_api_mcp.core.tools import tool
from omio_api_mcp.omio.client import WEB, api

if TYPE_CHECKING:
    from omio_api_mcp.core.context import ToolContext

INPUT_SCHEMA: dict[str, Any] = {"type": "object", "properties": {}, "additionalProperties": False}


@tool(
    name="get_account",
    title="Get account",
    access="read",
    description="The signed-in Omio account: name, email, when it was made and its marketing email setting.",
    details=(
        "Returns the account's name and email, when it was created and last active, and whether Omio may "
        "send it travel offers by email and push. Travelers and their details: list_passengers."
    ),
    input_schema=INPUT_SCHEMA,
    route="GET /account",
    example_response={
        "user_id": "8f0d2a51-3c7e-4b9a-9f12-6d3e5a7b1c40",
        "email": "alex.morgan@example.com",
        "first_name": "Alex",
        "last_name": "Morgan",
        "created_at": "2026-10-26T19:44:43.859Z",
        "last_active_at": "2026-10-26T20:15:05.207Z",
        "travel_offers": {"email": "subscribed", "push": "subscribed"},
    },
)
async def get_account(ctx: ToolContext, args: dict[str, Any]) -> Any:
    del args
    me = await api(ctx, "GET", f"{WEB}/iam/users/me/v2", what="the account") or {}
    opt_in = await api(ctx, "GET", f"{WEB}/crm-proxy/opt-in/me/v1", what="the email settings") or {}
    status = opt_in.get("optInStatus") or {}
    return {
        "user_id": me.get("userId"),
        "email": me.get("email"),
        "first_name": me.get("firstName"),
        "last_name": me.get("lastName"),
        "created_at": me.get("created"),
        "last_active_at": me.get("lastProfileActivity"),
        "travel_offers": {"email": status.get("email"), "push": status.get("push")},
    }
