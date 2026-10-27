#!/usr/bin/env python3
"""List the travelers saved on your Omio account with their discount cards, or find a discount card to add.

python saved_travelers.py
python saved_travelers.py --cards bahncard
"""

import argparse

from omio_api_mcp.scripting import call, run


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--cards", metavar="SEARCH", help="Search Omio's discount cards instead, e.g. bahncard")
    args = parser.parse_args()

    if args.cards:
        for operator in call("list_discount_cards", {"search": args.cards})["operators"]:
            for card in operator["cards"]:
                print(f"{operator['provider']}:{card['card_id']:24} {card['name']}")
        return
    for p in call("list_passengers")["passengers"]:
        cards = ", ".join(f"{c['provider']}:{c['code']}" for c in p.get("discount_cards") or [])
        holder = " (account holder)" if p.get("account_holder") else ""
        print(f"{p['first_name']} {p['last_name']}{holder}  born {p.get('date_of_birth') or '?'}  {cards}")
        print(f"  passenger_id: {p['passenger_id']}")


if __name__ == "__main__":
    run(main)
