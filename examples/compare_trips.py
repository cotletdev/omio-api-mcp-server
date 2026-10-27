#!/usr/bin/env python3
"""Compare train, bus and flight options between two places on one day: the cheapest and the fastest of each mode.

python compare_trips.py Berlin Munich 2026-11-19
python compare_trips.py Berlin Munich 2026-11-19 --modes train bus --out trips.csv
"""

import argparse

from omio_api_mcp.scripting import call, run, write_rows


def _price(trip: dict) -> float:
    return (trip.get("price") or {}).get("amount") or float("inf")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("origin", help="From: a city or station name")
    parser.add_argument("destination", help="To: a city or station name")
    parser.add_argument("date", help="Travel date, YYYY-MM-DD")
    parser.add_argument("--modes", nargs="+", choices=["train", "bus", "flight"])
    parser.add_argument("--currency", default="EUR")
    parser.add_argument("--out", help="Save every trip as .csv or .json instead of the summary")
    args = parser.parse_args()

    found = call(
        "search_trips",
        {
            "from": args.origin,
            "to": args.destination,
            "date": args.date,
            "modes": args.modes,
            "currency": args.currency,
            "limit": 100,
        },
    )
    trips = found["trips"]
    if args.out:
        write_rows(trips, args.out)
        return
    print(f"{found['from']['name']} to {found['to']['name']}, {found['date']}: {found['total']} trips")
    for mode in sorted({t["mode"] for t in trips}):
        of_mode = [t for t in trips if t["mode"] == mode]
        cheapest = min(of_mode, key=_price)
        fastest = min(of_mode, key=lambda t: t.get("duration_minutes") or 10**6)
        for label, trip in (("cheapest", cheapest), ("fastest", fastest)):
            price = trip.get("price") or {}
            print(
                f"  {mode:7} {label:9} {trip['departs'][11:16]}-{trip['arrives'][11:16]}  {trip['duration']:>8}  "
                f"{trip['changes']} changes  {price.get('amount', '?')} {price.get('currency', '')}  {trip['operator']}"
            )
    print("Fares and conditions of one trip: python examples/trip_fares.py <trip_id>")


if __name__ == "__main__":
    run(main)
