from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Optional
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (compatible; ScannerBot/1.0; +https://github.com/benny9193/scanner)"
)


@dataclass
class ScrapeResult:
    url: str
    status_code: int
    title: Optional[str] = None
    description: Optional[str] = None
    headings: dict[str, list[str]] = field(default_factory=dict)
    links: list[dict[str, str]] = field(default_factory=list)
    images: list[dict[str, str]] = field(default_factory=list)
    text: Optional[str] = None
    matches: list[str] = field(default_factory=list)
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


class Scraper:
    def __init__(
        self,
        user_agent: str = DEFAULT_USER_AGENT,
        timeout: float = 15.0,
        max_text_chars: int = 5000,
    ) -> None:
        self.timeout = timeout
        self.max_text_chars = max_text_chars
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": user_agent})

    def fetch(self, url: str) -> requests.Response:
        if not urlparse(url).scheme:
            url = "https://" + url
        response = self.session.get(url, timeout=self.timeout, allow_redirects=True)
        response.raise_for_status()
        return response

    def scrape(self, url: str, selector: Optional[str] = None) -> ScrapeResult:
        try:
            response = self.fetch(url)
        except requests.RequestException as exc:
            return ScrapeResult(url=url, status_code=0, error=str(exc))

        soup = BeautifulSoup(response.text, "lxml")
        base_url = str(response.url)

        result = ScrapeResult(url=base_url, status_code=response.status_code)
        result.title = self._extract_title(soup)
        result.description = self._extract_description(soup)
        result.headings = self._extract_headings(soup)
        result.links = self._extract_links(soup, base_url)
        result.images = self._extract_images(soup, base_url)
        result.text = self._extract_text(soup)

        if selector:
            result.matches = [
                el.get_text(" ", strip=True) for el in soup.select(selector)
            ]

        return result

    def _extract_title(self, soup: BeautifulSoup) -> Optional[str]:
        if soup.title and soup.title.string:
            return soup.title.string.strip()
        return None

    def _extract_description(self, soup: BeautifulSoup) -> Optional[str]:
        for name in ("description", "og:description", "twitter:description"):
            tag = soup.find("meta", attrs={"name": name}) or soup.find(
                "meta", attrs={"property": name}
            )
            if tag and tag.get("content"):
                return tag["content"].strip()
        return None

    def _extract_headings(self, soup: BeautifulSoup) -> dict[str, list[str]]:
        headings: dict[str, list[str]] = {}
        for level in range(1, 4):
            tag = f"h{level}"
            found = [h.get_text(strip=True) for h in soup.find_all(tag)]
            if found:
                headings[tag] = found
        return headings

    def _extract_links(
        self, soup: BeautifulSoup, base_url: str
    ) -> list[dict[str, str]]:
        links = []
        seen: set[str] = set()
        for a in soup.find_all("a", href=True):
            href = urljoin(base_url, a["href"].strip())
            if href in seen or href.startswith("javascript:"):
                continue
            seen.add(href)
            links.append({"href": href, "text": a.get_text(strip=True)})
        return links

    def _extract_images(
        self, soup: BeautifulSoup, base_url: str
    ) -> list[dict[str, str]]:
        images = []
        for img in soup.find_all("img"):
            src = img.get("src") or img.get("data-src")
            if not src:
                continue
            images.append(
                {
                    "src": urljoin(base_url, src.strip()),
                    "alt": (img.get("alt") or "").strip(),
                }
            )
        return images

    def _extract_text(self, soup: BeautifulSoup) -> str:
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()
        text = soup.get_text(" ", strip=True)
        if len(text) > self.max_text_chars:
            return text[: self.max_text_chars] + "…"
        return text
