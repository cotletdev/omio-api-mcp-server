"""List payment methods: `GET /payment-methods-service/payment-methods/v2`. Names and brands
only: card numbers, tokens and PSP data never leave the tool."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from omio_api_mcp.core.tools import tool
from omio_api_mcp.omio.client import WEB, api

if TYPE_CHECKING:
    from omio_api_mcp.core.context import ToolContext

INPUT_SCHEMA: dict[str, Any] = {"type": "object", "properties": {}, "additionalProperties": False}


def _first(record: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if record.get(key) not in (None, ""):
            return record[key]
    return None


@tool(
    name="list_payment_methods",
    title="List payment methods",
    access="read",
    description="Payment methods saved on the account, by type and brand. Never card numbers.",
    details=(
        "Lists what Payment methods in the account shows: the kind (card, PayPal ...), the card brand and "
        "whether it is the default. Omio saves a method only after a payment, so a new account has none. "
        "Nothing here pays: payment happens at a booking's checkout_url."
    ),
    input_schema=INPUT_SCHEMA,
    route="GET /payment-methods",
    example_response={"payment_methods": [{"type": "card", "brand": "Visa", "name": "Visa", "default": True}]},
)
async def list_payment_methods(ctx: ToolContext, args: dict[str, Any]) -> Any:
    del args
    answer = await api(ctx, "GET", f"{WEB}/payment-methods-service/payment-methods/v2", what="the payment methods")
    rows = answer if isinstance(answer, list) else (answer or {}).get("paymentMethods") or []
    return {
        "payment_methods": [
            {
                "type": _first(record, "type", "paymentMethodType", "methodType"),
                "brand": _first(record, "brand", "cardBrand", "scheme"),
                "name": _first(record, "displayName", "name", "label"),
                "default": bool(_first(record, "isDefault", "default")),
            }
            for record in rows
            if isinstance(record, dict)
        ]
    }
