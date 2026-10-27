"""Who is signed in: Omio's own session probe (/iam/sso/v2), for "Signed in as ..."."""

from __future__ import annotations

from typing import TYPE_CHECKING

from omio_api_mcp.core.errors import AuthExpiredError, ErrorCode, ToolError

if TYPE_CHECKING:
    from omio_api_mcp.core.context import ToolContext

WEB = "https://www.omio.com"


async def whoami(ctx: ToolContext) -> str | None:
    """None only when Omio says signed out; any other failure raises (detection tries again later)."""
    try:
        response = await ctx.call(
            "GET", f"{WEB}/iam/sso/v2", headers={"accept": "application/json", "referer": f"{WEB}/"}
        )
    except AuthExpiredError:
        return None
    if response.status in (204, 401, 403):
        return None
    if response.status != 200:
        raise ToolError(f"Omio answered {response.status} to who am I.", ErrorCode.TARGET_ERROR)
    me = response.json()
    name = f"{me.get('firstName') or ''} {me.get('lastName') or ''}".strip()
    email = me.get("email")
    return f"{name} ({email})" if name and email else name or email or None
