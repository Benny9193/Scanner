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
    parser.add_argument("urls", nargs="*", help="URLs to scrape.")
    parser.add_argument(
        "-i",
        "--input",
        help="Read URLs from FILE (one per line). Combined with positional args.",
    )
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
        "-w",
        "--workers",
        type=int,
        default=4,
        help="Concurrent worker count for multiple URLs (default: 4).",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=15.0,
        help="Request timeout in seconds (default: 15).",
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=2,
        help="Retry attempts on transient errors (default: 2).",
    )
    parser.add_argument(
        "--respect-robots",
        action="store_true",
        help="Skip URLs disallowed by robots.txt.",
    )
    return parser


def write_csv(results: list[dict], stream) -> None:
    writer = csv.writer(stream)
    writer.writerow(
        [
            "url",
            "status_code",
            "elapsed_ms",
            "title",
            "description",
            "language",
            "word_count",
            "internal_links",
            "external_links",
            "images",
            "error",
        ]
    )
    for r in results:
        writer.writerow(
            [
                r["url"],
                r["status_code"],
                r.get("elapsed_ms", 0),
                r.get("title") or "",
                r.get("description") or "",
                r.get("language") or "",
                r.get("word_count", 0),
                len(r.get("internal_links") or []),
                len(r.get("external_links") or []),
                len(r.get("images") or []),
                r.get("error") or "",
            ]
        )


def collect_urls(args: argparse.Namespace) -> list[str]:
    urls = list(args.urls)
    if args.input:
        for line in Path(args.input).read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                urls.append(line)
    return urls


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    urls = collect_urls(args)
    if not urls:
        print("error: no URLs provided", file=sys.stderr)
        return 2

    scraper = Scraper(
        timeout=args.timeout,
        retries=args.retries,
        respect_robots=args.respect_robots,
    )

    results = [
        r.to_dict()
        for r in scraper.scrape_many(urls, selector=args.selector, max_workers=args.workers)
    ]

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
