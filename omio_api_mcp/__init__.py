"""Self-hosted API and MCP server for one app (see app.py). Personal use only, see LICENSE.

From Python, without a server:

    from omio_api_mcp import call
    trips = call("search_trips", {"from": "Berlin", "to": "Munich", "date": "2026-11-19"})["trips"]
"""

from __future__ import annotations

import asyncio
from typing import Any

__version__ = "1.0.1"


def call(tool: str, args: dict[str, Any] | None = None, **kwargs: Any) -> Any:
    """Run one tool with the saved session and return its answer. Raises ToolError on failure."""
    from omio_api_mcp.runner import Runner

    async def go() -> Any:
        runner = Runner()
        try:
            return await runner.run(tool, {**(args or {}), **kwargs})
        finally:
            await runner.close()

    return asyncio.run(go())
