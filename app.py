from __future__ import annotations

from flask import Flask, render_template, request

from scraper import Scraper

app = Flask(__name__)
scraper = Scraper()


@app.route("/", methods=["GET", "POST"])
def index():
    result = None
    url = ""
    selector = ""
    if request.method == "POST":
        url = (request.form.get("url") or "").strip()
        selector = (request.form.get("selector") or "").strip() or None
        if url:
            result = scraper.scrape(url, selector=selector).to_dict()
    return render_template("index.html", result=result, url=url, selector=selector or "")


@app.route("/api/scrape")
def api_scrape():
    url = (request.args.get("url") or "").strip()
    selector = (request.args.get("selector") or "").strip() or None
    if not url:
        return {"error": "missing 'url' query parameter"}, 400
    return scraper.scrape(url, selector=selector).to_dict()


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
