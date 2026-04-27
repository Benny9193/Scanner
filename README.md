# Scanner

A small Python web scraper with a CLI and a Flask web UI. Given a URL, it
extracts the page title, meta description, headings, links, images, a text
preview, and (optionally) elements matching a CSS selector.

## Install

```bash
python -m pip install -r requirements.txt
```

## Web UI

```bash
python app.py
```

Then open http://127.0.0.1:5000. There's also a JSON endpoint:

```
GET /api/scrape?url=https://example.com&selector=h1
```

## CLI

```bash
# JSON to stdout
python -m scraper.cli https://example.com

# Target specific elements via CSS selector
python -m scraper.cli https://example.com -s "article h2"

# CSV summary for multiple URLs
python -m scraper.cli https://a.com https://b.com -f csv -o out.csv
```

## Library

```python
from scraper import Scraper

result = Scraper().scrape("https://example.com", selector="h1")
print(result.title, result.matches)
```

## Project layout

```
app.py              # Flask web UI + JSON API
scraper/core.py     # Scraper, ScrapeResult
scraper/cli.py      # `python -m scraper.cli`
templates/index.html
requirements.txt
```
