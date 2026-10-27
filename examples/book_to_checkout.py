#!/usr/bin/env python3
"""Reserve the cheapest fare of a trip for your saved travelers and print the total and the checkout link. Pays nothing.

Omio holds the fare for a short time. You review and pay on omio.com, at checkout_url, in a browser signed in to
the same account.

python book_to_checkout.py <trip_id> --dry-run
python book_to_checkout.py <trip_id> --refundable --travelers 2
"""

import argparse

from omio_api_mcp.scripting import call, run


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("trip_id", help="trip_id from search_trips (one way) or list_return_trips")
    parser.add_argument("--refundable", action="store_true", help="Cheapest refundable fare only")
    parser.add_argument(
        "--travelers", type=int, help="How many saved travelers, account holder first (default: as searched)"
    )
    parser.add_argument("--dry-run", action="store_true", help="Show the fare and travelers, reserve nothing")
    args = parser.parse_args()

    trip = call("get_trip", {"trip_id": args.trip_id})
    fares = [f for f in trip["fares"] if f.get("bookable_on_omio") and (f.get("refundable") or not args.refundable)]
    if not fares:
        raise SystemExit("No fare of this trip matches. Run trip_fares.py to see them all.")
    fare = min(fares, key=lambda f: (f.get("price") or {}).get("amount") or float("inf"))
    count = args.travelers or trip.get("travelers") or 1
    saved = call("list_passengers")["passengers"][:count]
    if len(saved) < count:
        raise SystemExit(f"Only {len(saved)} saved traveler(s); add more with add_passenger.")
    price = fare.get("price") or {}
    print(
        f"{trip['from']} to {trip['to']}: {fare.get('class')}, {fare.get('name')}, {price.get('amount')} {price.get('currency')}"
    )
    print("Travelers: " + ", ".join(f"{p['first_name']} {p['last_name']}" for p in saved))
    if args.dry_run:
        print("Dry run: nothing reserved.")
        return
    booking = call(
        "start_booking",
        {
            "trip_id": args.trip_id,
            "fare_ids": [fare["fare_id"]],
            "saved_passenger_ids": [p["passenger_id"] for p in saved],
        },
    )
    total = booking.get("total") or {}
    print(f"Reserved until {booking.get('reserved_until')}. Total {total.get('amount')} {total.get('currency')}.")
    if booking.get("missing_details"):
        print("Omio still needs: " + ", ".join(booking["missing_details"]))
    print(f"Pay here: {booking['checkout_url']}")


if __name__ == "__main__":
    run(main)
