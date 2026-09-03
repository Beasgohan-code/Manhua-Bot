# Manhua-Bot - Video source base classes
#
# A "video source" is any site that exposes searchable episodes with a
# playable page URL. Actual stream extraction is delegated to yt-dlp
# (services/video_dl.py), so individual sources only have to answer:
#
#   search(query)      -> [ {id, title, url, cover, src, adult} ]
#   get_series(sid)    -> {id, title, url, cover, episodes: [...], adult}
#   get_episode(url)   -> {title, page_url, stream_url|None, headers}
#
# Keeping extraction generic means new sites are ~40 lines of HTML parsing
# instead of a bespoke player-decryption routine per site.

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, quote_plus

from bs4 import BeautifulSoup
from loguru import logger

from sources.base.scraper import Scraper


def soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html or "", "lxml")


def clean(text: Optional[str]) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip()


def slug_of(url: str) -> str:
    return (url or "").rstrip("/").split("/")[-1]


class VideoScraper(Scraper):
    """Base class for every video (anime / hentai) source."""

    # Overridden by subclasses
    url: str = ""
    name: str = "Video"
    sf: str = "vid"
    adult: bool = False
    kind: str = "video"  # marker used by the manager to separate from manga

    # ---- helpers -------------------------------------------------------
    def abs_url(self, href: str) -> str:
        if not href:
            return ""
        if href.startswith("//"):
            return "https:" + href
        return urljoin(self.url + "/", href)

    @property
    def headers(self) -> Dict[str, str]:
        return {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            "Referer": self.url + "/",
            "Accept-Language": "en-US,en;q=0.9",
        }

    async def html(self, url: str, cs: bool = True) -> Optional[str]:
        try:
            return await self.get(url, headers=self.headers, cs=cs)
        except Exception as exc:  # network / cloudflare
            logger.debug(f"[{self.sf}] fetch failed {url}: {exc}")
            return None

    def q(self, query: str) -> str:
        return quote_plus(query or "")

    # ---- interface -----------------------------------------------------
    async def search(self, query: str = "") -> List[Dict[str, Any]]:
        raise NotImplementedError

    async def get_series(self, sid: str) -> Optional[Dict[str, Any]]:
        raise NotImplementedError

    async def get_episode(self, url: str) -> Optional[Dict[str, Any]]:
        """Default: hand the watch page straight to yt-dlp."""
        page = url if url.startswith("http") else self.abs_url(url)
        return {
            "title": self.name,
            "page_url": page,
            "stream_url": None,
            "headers": self.headers,
        }

    # ---- generic HTML list scraping ------------------------------------
    async def _cards(
        self,
        url: str,
        card_sel: str,
        link_sel: str = "a",
        title_sel: Optional[str] = None,
        img_sel: str = "img",
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Scrape a grid of result cards using CSS selectors."""
        html = await self.html(url)
        if not html:
            return []
        out: List[Dict[str, Any]] = []
        for card in soup(html).select(card_sel)[:limit]:
            a = card.select_one(link_sel)
            if not a or not a.get("href"):
                continue
            href = self.abs_url(a["href"])
            title = ""
            if title_sel:
                t = card.select_one(title_sel)
                title = clean(t.get_text()) if t else ""
            if not title:
                title = clean(a.get("title") or a.get_text())
            if not title:
                continue
            img = card.select_one(img_sel)
            cover = ""
            if img:
                cover = (
                    img.get("data-src")
                    or img.get("data-lazy-src")
                    or img.get("src")
                    or ""
                )
                cover = self.abs_url(cover) if cover else ""
            out.append(
                {
                    "id": slug_of(href),
                    "title": title,
                    "url": href,
                    "cover": cover,
                    "src": self.sf,
                    "adult": self.adult,
                    "kind": "video",
                }
            )
        return out
