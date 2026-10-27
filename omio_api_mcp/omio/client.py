"""Omio web API on www.omio.com, recorded on the dev account (26.10.2026).

The session is the httpOnly `Authorization` cookie. Every call sends the page's origin, `x-app-id: b2c` and the
two constants the page's request interceptor adds (`x-omio-rnauth`, `x-omio-native`). `passenger-service`
answers 404 without `x-api-version: v1` and `/iam`, `/payment-methods-service`, `/crm-proxy` answer 404 with it,
so only passenger-service calls send it. GraphQL (`/graphql`)
is Apollo with free-text queries and introspection off. Prices are integer cents.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from omio_api_mcp.core.errors import ErrorCode, ToolError

if TYPE_CHECKING:
    from omio_api_mcp.core.context import HttpResponse, ToolContext

WEB = "https://www.omio.com"
GRAPHQL = f"{WEB}/graphql"
POST_BOOKING = f"{WEB}/bff-core-service/post-booking-api"
BOOKING_EXPERIENCE = f"{WEB}/bff-core-service/booking-experience/bookings"
PASSENGERS = f"{WEB}/passenger-service/users/me/passengers"
LOCALE = "en"
HEADERS = {
    "origin": WEB,
    "referer": f"{WEB}/",
    "x-app-id": "b2c",
    "accept": "application/json",
    "x-omio-rnauth": "true",
    "x-omio-native": "false",
}
_PASSENGER_SERVICE = {"x-api-version": "v1"}


def headers_for(url: str) -> dict[str, str]:
    return {**HEADERS, **_PASSENGER_SERVICE} if url.startswith(PASSENGERS) else dict(HEADERS)


def _message(body: Any) -> str | None:
    """Omio's own short message: `message`, `error`, or the first GraphQL `errors[].message`."""
    if not isinstance(body, dict):
        return None
    errors = body.get("errors")
    if isinstance(errors, list) and errors and isinstance(errors[0], dict):
        return str(errors[0].get("message") or "")[:200] or None
    for key in ("message", "error", "detail"):
        if isinstance(body.get(key), str) and body[key]:
            return body[key][:200]
    return None


def _parse(response: HttpResponse) -> Any:
    if not response.text.strip():
        return None
    try:
        return response.json()
    except ToolError:
        return None


async def api(
    ctx: ToolContext,
    method: str,
    url: str,
    *,
    params: dict[str, Any] | None = None,
    body: Any = None,
    what: str,
    ok: tuple[int, ...] = (200, 201, 202, 204),
) -> Any:
    """One JSON call; returns the parsed answer (None for an empty body). Another status raises with
    Omio's message, worded as "Omio refused {what}"."""
    response = await ctx.call(method, url, params=params, json=body, headers=headers_for(url))
    answer = _parse(response)
    if response.status not in ok:
        detail = _message(answer)
        raise ToolError(f"Omio refused {what}" + (f": {detail}" if detail else "."), ErrorCode.TARGET_ERROR)
    return answer


async def api_status(
    ctx: ToolContext, method: str, url: str, *, params: dict[str, Any] | None = None
) -> tuple[int, Any]:
    """A call whose status the tool reads itself (404 = not found)."""
    response = await ctx.call(method, url, params=params, headers=headers_for(url))
    return response.status, _parse(response)


async def gql(ctx: ToolContext, operation: str, query: str, variables: dict[str, Any], *, what: str) -> dict[str, Any]:
    """One GraphQL query; returns `data`. `errors[]` with no data raises with Omio's first message."""
    answer = await api(
        ctx,
        "POST",
        GRAPHQL,
        body={"operationName": operation, "query": query, "variables": variables},
        what=what,
    )
    data = answer.get("data") if isinstance(answer, dict) else None
    if not data:
        detail = _message(answer)
        raise ToolError(f"Omio refused {what}" + (f": {detail}" if detail else "."), ErrorCode.TARGET_ERROR)
    return data


def money(cents: Any, currency: Any) -> dict[str, Any] | None:
    """`{amount, currency}` from integer cents; None when Omio gave no price."""
    if cents is None or not isinstance(cents, int | float):
        return None
    return {"amount": round(cents / 100, 2), "currency": currency}


def amount(value: Any) -> dict[str, Any] | None:
    """`{valueInCents, currency}` or `{lowestUnitValue, currency}` as `{amount, currency}`."""
    if not isinstance(value, dict):
        return None
    cents = value.get("valueInCents", value.get("lowestUnitValue"))
    return money(cents, value.get("currency"))


async def request_headers(ctx: ToolContext) -> dict[str, str]:
    """`docker/prod-run ... request`: the headers every Omio call sends."""
    del ctx
    return dict(HEADERS)
