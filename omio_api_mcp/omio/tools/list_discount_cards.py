"""List discount cards: `GET /discount-cards-search/discountcards`."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from omio_api_mcp.core.tools import tool
from omio_api_mcp.omio.client import LOCALE, WEB, api

if TYPE_CHECKING:
    from omio_api_mcp.core.context import ToolContext

INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "search": {"type": "string", "description": "Keep cards or operators whose name contains this text."},
    },
    "additionalProperties": False,
}

EXAMPLE_RESPONSE: dict[str, Any] = {
    "operators": [
        {
            "provider": "deutscheBahnPst",
            "name": "Deutsche Bahn",
            "several_cards": False,
            "cards": [
                {"card_id": "BAHNCARD50-2", "name": "BahnCard 50 (2nd class)", "number_required": False},
                {"card_id": "BAHNCARD25-2", "name": "BahnCard 25 (2nd class)", "number_required": False},
            ],
        }
    ]
}


def _text(names: Any) -> str | None:
    if isinstance(names, dict):
        return names.get(LOCALE) or next(iter(names.values()), None)
    return None


@tool(
    name="list_discount_cards",
    title="List discount cards",
    access="read",
    description="Rail and coach discount cards Omio prices in, such as BahnCard or Railcards, by operator.",
    details=(
        "Lists the discount and loyalty cards Omio can apply to a search, grouped by operator. Give a "
        "traveler's cards to search_trips as passengers[].discount_cards with provider and card_id as code; "
        "the prices then include the discount. several_cards says whether one traveler can hold more than one "
        "card of that operator."
    ),
    input_schema=INPUT_SCHEMA,
    route="GET /discount-cards",
    example_response=EXAMPLE_RESPONSE,
)
async def list_discount_cards(ctx: ToolContext, args: dict[str, Any]) -> Any:
    answer = await api(
        ctx, "GET", f"{WEB}/discount-cards-search/discountcards", params={"lang": LOCALE}, what="the discount cards"
    )
    needle = (args.get("search") or "").strip().lower()
    operators: list[dict[str, Any]] = []
    for group in answer or []:
        if not isinstance(group, dict):
            continue
        name = _text(group.get("groupNames")) or group.get("serviceProvider")
        cards = [
            {
                "card_id": card.get("id"),
                "name": _text(card.get("descriptions")),
                "number_required": bool(card.get("isNumberRequired")),
            }
            for card in group.get("cards") or []
        ]
        if needle and needle not in str(name).lower():
            cards = [card for card in cards if needle in str(card["name"]).lower()]
            if not cards:
                continue
        operators.append(
            {
                "provider": group.get("serviceProvider"),
                "name": name,
                "several_cards": bool(group.get("multipleSelection")),
                "cards": cards,
            }
        )
    return {"operators": operators}
