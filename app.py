from __future__ import annotations

import csv
import io
import json

from flask import Flask, Response, render_template, request

from scraper import Scraper

app = Flask(__name__)
scraper = Scraper(retries=2)


def parse_urls(raw: str) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for line in (raw or "").splitlines():
        url = line.strip()
        if url and not url.startswith("#") and url not in seen:
            seen.add(url)
            ordered.append(url)
    return ordered


@app.route("/", methods=["GET", "POST"])
def index():
    results: list[dict] = []
    urls_text = ""
    selector = ""
    respect_robots = False

    if request.method == "POST":
        urls_text = request.form.get("urls") or ""
        selector = (request.form.get("selector") or "").strip()
        respect_robots = bool(request.form.get("respect_robots"))
        urls = parse_urls(urls_text)

        if urls:
            run_scraper = Scraper(retries=2, respect_robots=respect_robots)
            results = [
                r.to_dict()
                for r in run_scraper.scrape_many(
                    urls, selector=selector or None, max_workers=min(8, len(urls))
                )
            ]

    return render_template(
        "index.html",
        results=results,
        urls_text=urls_text,
        selector=selector,
        respect_robots=respect_robots,
    )


@app.route("/api/scrape")
def api_scrape():
    url = (request.args.get("url") or "").strip()
    selector = (request.args.get("selector") or "").strip() or None
    if not url:
        return {"error": "missing 'url' query parameter"}, 400
    return scraper.scrape(url, selector=selector).to_dict()


@app.route("/api/scrape-many", methods=["POST"])
def api_scrape_many():
    payload = request.get_json(silent=True) or {}
    urls = payload.get("urls") or []
    selector = payload.get("selector") or None
    if not isinstance(urls, list) or not urls:
        return {"error": "'urls' must be a non-empty list"}, 400
    results = scraper.scrape_many(urls, selector=selector, max_workers=8)
    return {"results": [r.to_dict() for r in results]}


@app.route("/download/<fmt>", methods=["POST"])
def download(fmt: str):
    if fmt not in ("json", "csv"):
        return {"error": "format must be json or csv"}, 400

    urls = parse_urls(request.form.get("urls") or "")
    selector = (request.form.get("selector") or "").strip() or None
    respect_robots = bool(request.form.get("respect_robots"))
    if not urls:
        return {"error": "no URLs provided"}, 400

    run_scraper = Scraper(retries=2, respect_robots=respect_robots)
    results = [
        r.to_dict()
        for r in run_scraper.scrape_many(urls, selector=selector, max_workers=8)
    ]

    if fmt == "json":
        body = json.dumps(results, indent=2, ensure_ascii=False)
        return Response(
            body,
            mimetype="application/json",
            headers={"Content-Disposition": "attachment; filename=scan.json"},
        )

    buf = io.StringIO()
    writer = csv.writer(buf)
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
    return Response(
        buf.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=scan.csv"},
    )


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
