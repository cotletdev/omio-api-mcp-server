#!/usr/bin/env python3
"""Find the cheapest day to travel between two places in a date range, then list the cheapest trips that day.

python cheapest_day.py Berlin Munich --start 2026-11-10 --end 2026-11-30
python cheapest_day.py Berlin Munich --start 2026-11-10 --modes train
"""

import argparse

from omio_api_mcp.scripting import call, run


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("origin", help="From: a city or station name")
    parser.add_argument("destination", help="To: a city or station name")
    parser.add_argument("--start", required=True, help="First day, YYYY-MM-DD")
    parser.add_argument("--end", help="Last day, YYYY-MM-DD, up to a month after --start (default: 2 weeks)")
    parser.add_argument("--modes", nargs="+", choices=["train", "bus", "flight"])
    parser.add_argument("--currency", default="EUR")
    parser.add_argument("--trips", type=int, default=3, help="Trips to show on the cheapest day")
    args = parser.parse_args()

    calendar = call(
        "get_price_calendar",
        {
            "from": args.origin,
            "to": args.destination,
            "start_date": args.start,
            "end_date": args.end,
            "modes": args.modes,
            "currency": args.currency,
        },
    )
    days = [d for d in calendar["days"] if d.get("cheapest")]
    if not days:
        print("Omio has no prices for these days.")
        return
    for day in days:
        price = day["cheapest"]
        print(f"{day['date']}  {price['amount']:>8.2f} {price['currency']}")
    best = min(days, key=lambda d: d["cheapest"]["amount"])
    print(f"\nCheapest day: {best['date']}")
    found = call(
        "search_trips",
        {
            "from": args.origin,
            "to": args.destination,
            "date": best["date"],
            "modes": args.modes,
            "currency": args.currency,
        },
    )
    trips = sorted(found["trips"], key=lambda t: (t.get("price") or {}).get("amount") or float("inf"))
    for trip in trips[: args.trips]:
        price = trip.get("price") or {}
        print(
            f"  {trip['mode']:7} {trip['departs'][11:16]}-{trip['arrives'][11:16]}  {trip['duration']:>8}  "
            f"{price.get('amount', '?')} {price.get('currency', '')}  {trip['operator']}  {trip['trip_id']}"
        )


if __name__ == "__main__":
    run(main)
