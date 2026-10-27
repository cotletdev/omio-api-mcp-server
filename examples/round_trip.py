#!/usr/bin/env python3
"""Price a round trip: the cheapest outbound legs and, for the cheapest one, its return legs with the round-trip price.

python round_trip.py Berlin Munich --out 2026-11-20 --back 2026-11-22
python round_trip.py Berlin Munich --out 2026-11-20 --back 2026-11-22 --card deutscheBahnPst:BAHNCARD50-2
"""

import argparse

from omio_api_mcp.scripting import call, run


def _price(trip: dict) -> float:
    return (trip.get("price") or {}).get("amount") or float("inf")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("origin", help="From: a city or station name")
    parser.add_argument("destination", help="To: a city or station name")
    parser.add_argument("--out", dest="out_date", required=True, help="Outbound date, YYYY-MM-DD")
    parser.add_argument("--back", required=True, help="Return date, YYYY-MM-DD")
    parser.add_argument("--age", type=int, default=30, help="Traveler's age")
    parser.add_argument(
        "--card", help="Discount card as provider:card_id from list_discount_cards, e.g. deutscheBahnPst:BAHNCARD50-2"
    )
    parser.add_argument("--modes", nargs="+", choices=["train", "bus", "flight"])
    args = parser.parse_args()

    traveler: dict = {"age": args.age}
    if args.card:
        provider, code = args.card.split(":", 1)
        traveler["discount_cards"] = [{"provider": provider, "code": code}]
    found = call(
        "search_trips",
        {
            "from": args.origin,
            "to": args.destination,
            "date": args.out_date,
            "return_date": args.back,
            "passengers": [traveler],
            "modes": args.modes,
        },
    )
    outbound = sorted(found["trips"], key=_price)
    if not outbound:
        print("No outbound trips.")
        return
    best = outbound[0]
    print(f"Cheapest outbound: {best['departs'][:16]} {best['from']} -> {best['to']}, {best['operator']}")
    back = call("list_return_trips", {"trip_id": best["trip_id"], "limit": 100})
    for trip in sorted(back["trips"], key=_price)[:5]:
        price = trip.get("price") or {}
        print(
            f"  back {trip['departs'][:16]} {trip['from']} -> {trip['to']}  round trip "
            f"{price.get('amount', '?')} {price.get('currency', '')}  {trip['trip_id']}"
        )


if __name__ == "__main__":
    run(main)
