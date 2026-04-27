# Scanner

A Python web scraper with a CLI and a Flask web UI. Given one or more URLs it
extracts:

- title, meta description, canonical URL, language, favicon
- Open Graph and Twitter card metadata
- h1–h3 headings
- internal vs external links (with anchor text)
- images (with alt text)
- a text preview and word count
- elements matching an optional CSS selector

Multiple URLs are scraped concurrently. Failed requests are retried with
exponential backoff. `robots.txt` can optionally be respected.

## Install

```bash
python -m pip install -r requirements.txt
```

## Web UI

```bash
python app.py
```

Open http://127.0.0.1:5000. Paste one URL per line, optionally add a CSS
selector, then **Scrape**, **Download JSON**, or **Download CSV**.

JSON endpoints:

```
GET  /api/scrape?url=https://example.com&selector=h1
POST /api/scrape-many   { "urls": [...], "selector": "h1" }
```

## CLI

```bash
# JSON to stdout
python -m scraper.cli https://example.com

# Multiple URLs, concurrent, CSV
python -m scraper.cli https://a.com https://b.com -w 8 -f csv -o out.csv

# Read URLs from a file (one per line, # for comments)
python -m scraper.cli -i urls.txt -f csv -o out.csv

# Polite mode
python -m scraper.cli https://example.com --respect-robots --retries 3
```

Flags: `-s/--selector`, `-w/--workers`, `--timeout`, `--retries`,
`--respect-robots`, `-f/--format json|csv`, `-o/--output`, `-i/--input`.

## Library

```python
from scraper import Scraper

s = Scraper(retries=3, respect_robots=True)
result = s.scrape("https://example.com", selector="h1")
print(result.title, result.word_count, result.matches)

results = s.scrape_many(["https://a.com", "https://b.com"], max_workers=8)
```

## Tests

```bash
python -m pytest -q
```

## Project layout

```
app.py                # Flask UI + JSON API + downloads
scraper/core.py       # Scraper, ScrapeResult
scraper/cli.py        # `python -m scraper.cli`
templates/index.html
tests/test_scraper.py
requirements.txt
```
