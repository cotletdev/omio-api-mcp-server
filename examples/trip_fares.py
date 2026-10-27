#!/usr/bin/env python3
"""Show the fares of one trip with their class, price and refund and exchange conditions.

python trip_fares.py <trip_id from search_trips>
python trip_fares.py <trip_id> --refundable
"""

import argparse

from omio_api_mcp.scripting import call, run


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("trip_id", help="trip_id from search_trips or list_return_trips")
    parser.add_argument("--refundable", action="store_true", help="Only fares Omio marks refundable")
    args = parser.parse_args()

    trip = call("get_trip", {"trip_id": args.trip_id})
    print(f"{trip['from']} to {trip['to']}, {trip['trip_type']}, {trip['travelers']} traveler(s)")
    for leg in trip["legs"]:
        print(
            f"  {leg['departs'][:16]} {leg['from']} -> {leg['arrives'][11:16]} {leg['to']}  {leg.get('service') or ''}"
        )
    fares = [f for f in trip["fares"] if f.get("refundable") or not args.refundable]
    for fare in sorted(fares, key=lambda f: (f.get("price") or {}).get("amount") or float("inf")):
        price = fare.get("price") or {}
        flags = ", ".join(
            name
            for name, on in (("refundable", fare.get("refundable")), ("exchangeable", fare.get("exchangeable")))
            if on
        )
        print(f"\n{price.get('amount', '?')} {price.get('currency', '')}  {fare.get('class')}, {fare.get('name')}")
        print(f"  {flags or 'no refund, no exchange'}. {fare.get('conditions') or ''}")
        print(f"  fare_id: {fare['fare_id']}")


if __name__ == "__main__":
    run(main)
