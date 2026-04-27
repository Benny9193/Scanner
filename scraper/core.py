from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field, asdict
from typing import Iterable, Optional
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (compatible; ScannerBot/1.0; +https://github.com/benny9193/scanner)"
)


@dataclass
class ScrapeResult:
    url: str
    status_code: int
    elapsed_ms: int = 0
    title: Optional[str] = None
    description: Optional[str] = None
    canonical: Optional[str] = None
    language: Optional[str] = None
    favicon: Optional[str] = None
    word_count: int = 0
    open_graph: dict[str, str] = field(default_factory=dict)
    twitter: dict[str, str] = field(default_factory=dict)
    headings: dict[str, list[str]] = field(default_factory=dict)
    internal_links: list[dict[str, str]] = field(default_factory=list)
    external_links: list[dict[str, str]] = field(default_factory=list)
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
        retries: int = 2,
        backoff: float = 0.5,
        respect_robots: bool = False,
    ) -> None:
        self.user_agent = user_agent
        self.timeout = timeout
        self.max_text_chars = max_text_chars
        self.retries = max(0, retries)
        self.backoff = backoff
        self.respect_robots = respect_robots
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": user_agent})
        self._robots_cache: dict[str, RobotFileParser] = {}

    def fetch(self, url: str) -> requests.Response:
        if not urlparse(url).scheme:
            url = "https://" + url

        last_exc: Optional[Exception] = None
        for attempt in range(self.retries + 1):
            try:
                response = self.session.get(
                    url, timeout=self.timeout, allow_redirects=True
                )
                response.raise_for_status()
                return response
            except requests.RequestException as exc:
                last_exc = exc
                if attempt < self.retries:
                    time.sleep(self.backoff * (2 ** attempt))
        assert last_exc is not None
        raise last_exc

    def _robots_allows(self, url: str) -> bool:
        parsed = urlparse(url)
        if not parsed.scheme:
            return True
        root = f"{parsed.scheme}://{parsed.netloc}"
        rp = self._robots_cache.get(root)
        if rp is None:
            rp = RobotFileParser()
            rp.set_url(urljoin(root, "/robots.txt"))
            try:
                rp.read()
            except Exception:
                rp = RobotFileParser()
                rp.parse([])
            self._robots_cache[root] = rp
        try:
            return rp.can_fetch(self.user_agent, url)
        except Exception:
            return True

    def scrape(self, url: str, selector: Optional[str] = None) -> ScrapeResult:
        if not urlparse(url).scheme:
            url = "https://" + url

        if self.respect_robots and not self._robots_allows(url):
            return ScrapeResult(
                url=url, status_code=0, error="Disallowed by robots.txt"
            )

        started = time.perf_counter()
        try:
            response = self.fetch(url)
        except requests.RequestException as exc:
            return ScrapeResult(
                url=url,
                status_code=getattr(exc.response, "status_code", 0) or 0,
                elapsed_ms=int((time.perf_counter() - started) * 1000),
                error=str(exc),
            )

        elapsed_ms = int((time.perf_counter() - started) * 1000)
        soup = BeautifulSoup(response.text, "lxml")
        base_url = str(response.url)

        result = ScrapeResult(
            url=base_url,
            status_code=response.status_code,
            elapsed_ms=elapsed_ms,
        )
        result.title = self._extract_title(soup)
        result.description = self._extract_description(soup)
        result.canonical = self._extract_canonical(soup, base_url)
        result.language = self._extract_language(soup)
        result.favicon = self._extract_favicon(soup, base_url)
        result.open_graph = self._extract_meta_prefix(soup, "og:")
        result.twitter = self._extract_meta_prefix(soup, "twitter:")
        result.headings = self._extract_headings(soup)
        internal, external = self._extract_links(soup, base_url)
        result.internal_links = internal
        result.external_links = external
        result.images = self._extract_images(soup, base_url)
        result.text = self._extract_text(soup)
        result.word_count = len((result.text or "").split())

        if selector:
            try:
                result.matches = [
                    el.get_text(" ", strip=True) for el in soup.select(selector)
                ]
            except Exception as exc:
                result.error = f"Invalid selector: {exc}"

        return result

    def scrape_many(
        self,
        urls: Iterable[str],
        selector: Optional[str] = None,
        max_workers: int = 4,
    ) -> list[ScrapeResult]:
        urls = list(urls)
        if not urls:
            return []
        max_workers = max(1, min(max_workers, len(urls)))
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            return list(pool.map(lambda u: self.scrape(u, selector=selector), urls))

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

    def _extract_canonical(self, soup: BeautifulSoup, base_url: str) -> Optional[str]:
        link = soup.find("link", rel="canonical")
        if link and link.get("href"):
            return urljoin(base_url, link["href"].strip())
        return None

    def _extract_language(self, soup: BeautifulSoup) -> Optional[str]:
        if soup.html and soup.html.get("lang"):
            return soup.html["lang"].strip()
        return None

    def _extract_favicon(self, soup: BeautifulSoup, base_url: str) -> Optional[str]:
        for rel in ("icon", "shortcut icon", "apple-touch-icon"):
            link = soup.find("link", rel=lambda v: v and rel in v.lower())
            if link and link.get("href"):
                return urljoin(base_url, link["href"].strip())
        return urljoin(base_url, "/favicon.ico")

    def _extract_meta_prefix(self, soup: BeautifulSoup, prefix: str) -> dict[str, str]:
        out: dict[str, str] = {}
        for tag in soup.find_all("meta"):
            key = tag.get("property") or tag.get("name") or ""
            if key.startswith(prefix) and tag.get("content"):
                out[key[len(prefix):]] = tag["content"].strip()
        return out

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
    ) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
        base_host = urlparse(base_url).netloc
        internal: list[dict[str, str]] = []
        external: list[dict[str, str]] = []
        seen: set[str] = set()
        for a in soup.find_all("a", href=True):
            href = urljoin(base_url, a["href"].strip())
            if href in seen or href.startswith(("javascript:", "mailto:", "tel:")):
                continue
            seen.add(href)
            entry = {"href": href, "text": a.get_text(strip=True)}
            host = urlparse(href).netloc
            if host == base_host or not host:
                internal.append(entry)
            else:
                external.append(entry)
        return internal, external

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
