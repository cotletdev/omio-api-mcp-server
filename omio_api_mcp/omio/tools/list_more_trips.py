"""List more trips: results v2 `extend_from` for one mode's time window, then the snapshot until the tab is done."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from omio_api_mcp.core.errors import ErrorCode, ToolError
from omio_api_mcp.core.tools import tool
from omio_api_mcp.omio.tools._search import collect, currency_of, poll, results, results_block

if TYPE_CHECKING:
    from omio_api_mcp.core.context import ToolContext

INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "search_id": {"type": "string", "pattern": "^[A-Za-z0-9]+$", "description": "search_id from search_trips."},
        "mode": {
            "type": "string",
            "enum": ["train", "bus"],
            "description": "Which results to extend. Omio extends trains (and some coach searches). Default: train.",
        },
        "direction": {
            "type": "string",
            "enum": ["later", "earlier"],
            "description": "later or earlier departures than those loaded. Default: later.",
        },
    },
    "required": ["search_id"],
    "additionalProperties": False,
}

EXAMPLE_RESPONSE: dict[str, Any] = {
    "search_id": "E3B02A2F5BF1045CD90E06B981AD2E45C",
    "mode": "train",
    "time_window": [["08:00", "15:36"]],
    "can_extend_earlier": True,
    "can_extend_later": True,
    "trips": [
        {
            "trip_id": "E3B02A2F5BF1045CD90E06B981AD2E45C.-1689911470.4518877563394719090.train",
            "mode": "train",
            "operator": "Deutsche Bahn",
            "from": "Berlin Hbf",
            "to": "Munich Hbf",
            "departs": "2026-11-17T12:37:00.000+01:00",
            "arrives": "2026-11-17T17:20:00.000+01:00",
            "duration": "4h 43m",
            "duration_minutes": 283,
            "changes": 0,
            "services": ["ICE 1009"],
            "price": {"amount": 79.0, "currency": "EUR"},
            "bookable_on_omio": True,
        }
    ],
}


def _key(card: dict[str, Any]) -> tuple[str, str]:
    return str(card.get("journeyId")), str(card.get("outboundId"))


@tool(
    name="list_more_trips",
    title="List more trips",
    access="read",
    description="Load later or earlier departures of a search's trains beyond the time window search_trips returned.",
    details=(
        "search_trips loads trains for a window of the day (modes.train.time_window). This tool widens that "
        "window once, later or earlier, waits up to 20 seconds for Omio and returns only the trips that "
        "appeared, with the new window. can_extend_later and can_extend_earlier say whether there is more. "
        "Works on the outbound legs of a search, for 2 hours after it was made."
    ),
    input_schema=INPUT_SCHEMA,
    route="GET /searches/{search_id}/more-trips",
    example_response=EXAMPLE_RESPONSE,
    timeout_s=60,
)
async def list_more_trips(ctx: ToolContext, args: dict[str, Any]) -> Any:
    search_id, mode = args["search_id"].strip(), args.get("mode") or "train"
    later = (args.get("direction") or "later") == "later"
    before = await results(ctx, search_id)
    block = results_block(before, None)
    tab = (block.get("tabs") or {}).get(mode) or {}
    windows = [list(w) for w in tab.get("timeWindows") or [] if isinstance(w, list) and len(w) == 2]
    if not windows or not tab.get("canExtendLater" if later else "canExtendEarlier"):
        raise ToolError(
            f"Omio has no {'later' if later else 'earlier'} {mode} departures to load for this search.",
            ErrorCode.TARGET_ERROR,
        )
    # Card ids carry a version suffix that changes between snapshots: the journey and outbound ids do not.
    seen = {_key((block.get("cards") or {}).get(card_id) or {}) for card_id in tab.get("cardIds") or []}
    await results(
        ctx,
        search_id,
        extra={
            "tab_id": mode,
            "extend_from": windows[-1][1] if later else windows[0][0],
            "extension_direction": "later" if later else "earlier",
            "updated_since": before.get("updatedSince") or 0,
            "is_extension_poll": "true",
            "pending_modes": mode,
        },
    )
    after = await poll(ctx, search_id, until_mode=mode)
    after_block = results_block(after, None)
    round_trip = bool((after_block.get("searchDetails") or {}).get("roundTrip"))
    new_tab = (after_block.get("tabs") or {}).get(mode) or {}
    cards = after_block.get("cards") or {}
    new_ids = [c for c in new_tab.get("cardIds") or [] if _key(cards.get(c) or {}) not in seen]
    fresh = {**after_block, "tabs": {mode: {**new_tab, "cardIds": new_ids}}}
    trips, per_mode = collect(fresh, search_id, [mode], currency_of(after_block), round_trip=round_trip)
    info = per_mode[mode]
    return {
        "search_id": search_id,
        "mode": mode,
        "time_window": info["time_window"],
        "can_extend_earlier": info["can_extend_earlier"],
        "can_extend_later": info["can_extend_later"],
        "trips": trips,
    }
