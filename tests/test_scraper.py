from __future__ import annotations

import requests

from scraper import Scraper


SAMPLE_HTML = """
<!doctype html>
<html lang="en">
<head>
  <title>Sample Page</title>
  <meta name="description" content="A test page.">
  <meta property="og:title" content="OG Title">
  <meta property="og:image" content="https://cdn.test/og.png">
  <meta name="twitter:card" content="summary">
  <link rel="canonical" href="https://example.test/canonical">
  <link rel="icon" href="/icon.png">
</head>
<body>
  <h1>Hello</h1>
  <h2>Sub</h2>
  <a href="/internal">Internal</a>
  <a href="https://other.test/x">External</a>
  <a href="javascript:void(0)">Skip</a>
  <img src="/img.png" alt="An image">
  <p>Some body text with several words for counting.</p>
  <script>noisy()</script>
</body>
</html>
"""


class FakeResponse:
    def __init__(self, text: str, status_code: int = 200, url: str = "https://example.test/"):
        self.text = text
        self.status_code = status_code
        self.url = url

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"status {self.status_code}", response=self)


def make_scraper(response: FakeResponse) -> Scraper:
    s = Scraper(retries=0)
    s.session.get = lambda *a, **k: response  # type: ignore[assignment]
    return s


def test_scrape_extracts_metadata():
    s = make_scraper(FakeResponse(SAMPLE_HTML))
    r = s.scrape("https://example.test/")

    assert r.status_code == 200
    assert r.title == "Sample Page"
    assert r.description == "A test page."
    assert r.language == "en"
    assert r.canonical == "https://example.test/canonical"
    assert r.favicon == "https://example.test/icon.png"
    assert r.open_graph["title"] == "OG Title"
    assert r.open_graph["image"] == "https://cdn.test/og.png"
    assert r.twitter["card"] == "summary"
    assert r.headings == {"h1": ["Hello"], "h2": ["Sub"]}
    assert r.word_count > 0
    assert r.error is None


def test_internal_vs_external_links():
    s = make_scraper(FakeResponse(SAMPLE_HTML))
    r = s.scrape("https://example.test/")

    internal_hrefs = [l["href"] for l in r.internal_links]
    external_hrefs = [l["href"] for l in r.external_links]

    assert "https://example.test/internal" in internal_hrefs
    assert "https://other.test/x" in external_hrefs
    assert all("javascript:" not in h for h in internal_hrefs + external_hrefs)


def test_selector_matches():
    s = make_scraper(FakeResponse(SAMPLE_HTML))
    r = s.scrape("https://example.test/", selector="h1, h2")
    assert r.matches == ["Hello", "Sub"]


def test_request_error_returns_result():
    s = Scraper(retries=0)

    def boom(*a, **k):
        raise requests.ConnectionError("dns fail")

    s.session.get = boom  # type: ignore[assignment]
    r = s.scrape("https://nope.test")
    assert r.status_code == 0
    assert r.error and "dns fail" in r.error


def test_scrape_many_concurrent():
    s = make_scraper(FakeResponse(SAMPLE_HTML))
    results = s.scrape_many(
        ["https://example.test/a", "https://example.test/b", "https://example.test/c"],
        max_workers=3,
    )
    assert len(results) == 3
    assert all(r.title == "Sample Page" for r in results)


def test_retries_then_succeeds():
    attempts = {"n": 0}

    def flaky(*a, **k):
        attempts["n"] += 1
        if attempts["n"] < 2:
            raise requests.ConnectionError("transient")
        return FakeResponse(SAMPLE_HTML)

    s = Scraper(retries=2, backoff=0.0)
    s.session.get = flaky  # type: ignore[assignment]
    r = s.scrape("https://example.test/")
    assert r.status_code == 200
    assert attempts["n"] == 2
