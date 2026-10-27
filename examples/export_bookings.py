#!/usr/bin/env python3
"""Export your Omio bookings (Your Bookings) to CSV or JSON: route, departure, operator, status and total.

python export_bookings.py --status all --out bookings.csv
"""

import argparse

from omio_api_mcp.scripting import call, run, write_rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--status", choices=["upcoming", "past", "all"], default="upcoming")
    parser.add_argument("--out", help="Save as .csv or .json")
    args = parser.parse_args()

    write_rows(call("list_bookings", {"status": args.status, "limit": 100})["bookings"], args.out)


if __name__ == "__main__":
    run(main)
