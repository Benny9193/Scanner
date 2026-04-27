from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

from .core import Scraper


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="scanner",
        description="Scrape one or more URLs and emit structured results.",
    )
    parser.add_argument("urls", nargs="+", help="URLs to scrape.")
    parser.add_argument(
        "-s",
        "--selector",
        help="Optional CSS selector; matched elements are returned in 'matches'.",
    )
    parser.add_argument(
        "-o",
        "--output",
        help="Write results to FILE instead of stdout.",
    )
    parser.add_argument(
        "-f",
        "--format",
        choices=("json", "csv"),
        default="json",
        help="Output format (default: json).",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=15.0,
        help="Request timeout in seconds (default: 15).",
    )
    return parser


def write_csv(results: list[dict], stream) -> None:
    writer = csv.writer(stream)
    writer.writerow(
        ["url", "status_code", "title", "description", "num_links", "num_images", "error"]
    )
    for r in results:
        writer.writerow(
            [
                r["url"],
                r["status_code"],
                r.get("title") or "",
                r.get("description") or "",
                len(r.get("links") or []),
                len(r.get("images") or []),
                r.get("error") or "",
            ]
        )


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    scraper = Scraper(timeout=args.timeout)

    results = [scraper.scrape(url, selector=args.selector).to_dict() for url in args.urls]

    if args.output:
        path = Path(args.output)
        with path.open("w", encoding="utf-8", newline="") as fh:
            if args.format == "csv":
                write_csv(results, fh)
            else:
                json.dump(results, fh, indent=2, ensure_ascii=False)
    else:
        if args.format == "csv":
            write_csv(results, sys.stdout)
        else:
            json.dump(results, sys.stdout, indent=2, ensure_ascii=False)
            sys.stdout.write("\n")

    return 0 if all(r["status_code"] for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
