#!/usr/bin/env python3
"""Find cities, train and bus stations, airports and ferry ports Omio knows, by name.

python search_places.py "Munich"
"""

import argparse

from omio_api_mcp.scripting import call, run, write_rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("query", help="A city, station or airport name")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--out", help="Save as .csv or .json")
    args = parser.parse_args()

    write_rows(call("search_places", {"query": args.query, "limit": args.limit})["places"], args.out)


if __name__ == "__main__":
    run(main)
