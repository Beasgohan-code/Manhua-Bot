# Manhua-Bot - Adult video sources (gated behind /adult on)
#
# Extraction strategy, in order of preference:
#   1. hanime-plugin yt-dlp extractors (HAnime.tv, HStream, Oppai.stream …)
#   2. iframe / <source> / m3u8 discovery on the watch page
#   3. hand the page URL to yt-dlp's generic extractor
#
# Search/listing is still HTML scraping, but each site now declares several
# candidate selectors and search paths so a theme tweak degrades instead of
# breaking outright.

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from loguru import logger

from sources.video.base import VideoScraper, soup, clean, slug_of


# Patterns for locating a playable stream on a watch page.
_IFRAME_RE = re.compile(r'<iframe[^>]+src=["\']([^"\']+)["\']', re.I)
_SOURCE_RE = re.compile(r'<source[^>]+src=["\']([^"\']+\.(?:m3u8|mp4))[^"\']*["\']', re.I)
_M3U8_RE = re.compile(r'["\'](https?://[^"\']+?\.m3u8[^"\']*)["\']', re.I)
_MP4_RE = re.compile(r'["\'](https?://[^"\']+?\.mp4[^"\']*)["\']', re.I)

_BAD_IFRAME = ("disqus", "google", "facebook", "twitter", "ads", "doubleclick")


class AdultVideoSite(VideoScraper):
    """Shared behaviour for the WordPress/WP-Script style hentai tubes."""

    adult = True

    # Several candidates are tried in order until one returns results.
    search_paths: List[str] = ["/?s={q}"]
    card_sels: List[str] = [
        ".video-block", ".item", "article", ".post", ".thumb-block", ".ml-item",
    ]
    title_sels: List[str] = [".title", ".name", "h2", "h3", ".entry-title"]
    episode_sels: List[str] = [
        ".eplister li a", ".episodios a", ".episode-list a", ".ep-item a",
    ]

    async def search(self, query: str = "") -> List[Dict[str, Any]]:
        for path in self.search_paths:
            url = self.url + path.format(q=self.q(query))
            for card in self.card_sels:
                try:
                    res = await self._cards(
                        url, card, title_sel=", ".join(self.title_sels), limit=15
                    )
                except Exception as exc:
                    logger.debug(f"[{self.sf}] search {card}: {exc}")
                    continue
                if res:
                    return res
        return []

    async def get_series(self, sid: str) -> Optional[Dict[str, Any]]:
        page = sid if str(sid).startswith("http") else f"{self.url}/{str(sid).strip('/')}"
        html = await self.html(page)
        if not html:
            return None
        s = soup(html)

        h1 = s.select_one("h1, .entry-title, .video-title")
        title = clean(h1.get_text()) if h1 else slug_of(page).replace("-", " ").title()
        og = s.select_one('meta[property="og:image"]')

        episodes: List[Dict[str, Any]] = []
        seen: set = set()
        for sel in self.episode_sels:
            for a in s.select(sel):
                href = a.get("href")
                if not href:
                    continue
                full = self.abs_url(href)
                if full in seen or full.rstrip("/") == page.rstrip("/"):
                    continue
                seen.add(full)
                label = clean(a.get_text()) or f"Episode {len(episodes) + 1}"
                m = re.search(r"(\d+(?:\.\d+)?)", label) or re.search(r"-(\d+)/?$", full)
                episodes.append(
                    {
                        "id": slug_of(full),
                        "num": m.group(1) if m else str(len(episodes) + 1),
                        "title": label[:80],
                        "url": full,
                    }
                )
            if episodes:
                break

        if not episodes:
            # Single-video page: treat the page itself as episode 1.
            episodes = [{"id": slug_of(page), "num": "1", "title": title, "url": page}]
        else:
            episodes.reverse()  # these themes list newest first

        return {
            "id": slug_of(page),
            "title": title,
            "url": page,
            "cover": (og.get("content") if og else "") or "",
            "adult": True,
            "src": self.sf,
            "kind": "video",
            "episodes": episodes,
        }

    async def get_episode(self, url: str) -> Optional[Dict[str, Any]]:
        """Find a direct stream; fall back to the page for yt-dlp generic."""
        page = url if url.startswith("http") else self.abs_url(url)

        # hanime-plugin may own this URL outright — let yt-dlp handle it.
        try:
            from services.hplugin import supports

            if supports(page):
                return {
                    "title": self.name,
                    "page_url": page,
                    "stream_url": None,
                    "headers": self.headers,
                    "extractor": "hanime-plugin",
                }
        except Exception:
            pass

        html = await self.html(page)
        if html:
            for rx in (_SOURCE_RE, _M3U8_RE, _MP4_RE):
                m = rx.search(html)
                if m:
                    return {
                        "title": self.name,
                        "page_url": page,
                        "stream_url": self.abs_url(m.group(1)),
                        "headers": {**self.headers, "Referer": page},
                    }
            for m in _IFRAME_RE.finditer(html):
                src = m.group(1)
                if any(b in src.lower() for b in _BAD_IFRAME):
                    continue
                return {
                    "title": self.name,
                    "page_url": self.abs_url(src),
                    "stream_url": None,
                    "headers": {**self.headers, "Referer": page},
                }

        return {
            "title": self.name,
            "page_url": page,
            "stream_url": None,
            "headers": self.headers,
        }


class HAnimeTVWebs(AdultVideoSite):
    """hanime.tv — public search API; playback via hanime-plugin's HanimeTV IE."""

    name = "HAnime.tv"
    sf = "hanime"

    def __init__(self):
        super().__init__()
        self.url = "https://hanime.tv"
        self.api = "https://search.htv-services.com"

    async def search(self, query: str = "") -> List[Dict[str, Any]]:
        import json

        payload = {
            "search_text": query,
            "tags": [],
            "tags_mode": "AND",
            "brands": [],
            "blacklist": [],
            "order_by": "created_at_unix",
            "ordering": "desc",
            "page": 0,
        }
        try:
            raw = await self.post(self.api, rjson=True, json=payload, headers=self.headers)
            if not raw:
                return []
            hits = raw.get("hits")
            hits = json.loads(hits) if isinstance(hits, str) else (hits or [])
            out = []
            for hit in hits[:20]:
                slug = hit.get("slug")
                if not slug:
                    continue
                out.append(
                    {
                        "id": slug,
                        "title": hit.get("name") or slug,
                        "url": f"{self.url}/videos/hentai/{slug}",
                        "cover": hit.get("cover_url") or hit.get("poster_url") or "",
                        "src": self.sf,
                        "adult": True,
                        "kind": "video",
                    }
                )
            return out
        except Exception as exc:
            logger.error(f"[hanime] search: {exc}")
            return []

    async def get_series(self, sid: str) -> Optional[Dict[str, Any]]:
        slug = slug_of(sid) if str(sid).startswith("http") else sid
        page = f"{self.url}/videos/hentai/{slug}"
        title, cover, episodes = slug.replace("-", " ").title(), "", []
        try:
            data = await self.get(
                f"{self.url}/rapi/v7/video?id={slug}", rjson=True, headers=self.headers
            )
            if data:
                hv = data.get("hentai_video") or {}
                title = hv.get("name") or title
                cover = hv.get("cover_url") or ""
                for fr in data.get("hentai_franchise_hentai_videos") or []:
                    fslug = fr.get("slug")
                    if not fslug:
                        continue
                    episodes.append(
                        {
                            "id": fslug,
                            "num": str(len(episodes) + 1),
                            "title": fr.get("name") or fslug,
                            "url": f"{self.url}/videos/hentai/{fslug}",
                        }
                    )
        except Exception as exc:
            logger.debug(f"[hanime] get_series api: {exc}")

        if not episodes:
            episodes = [{"id": slug, "num": "1", "title": title, "url": page}]
        return {
            "id": slug,
            "title": title,
            "url": page,
            "cover": cover,
            "adult": True,
            "src": self.sf,
            "kind": "video",
            "episodes": episodes,
        }

    async def get_episode(self, url: str) -> Optional[Dict[str, Any]]:
        # Always defer to hanime-plugin's HanimeTV extractor (AES token flow).
        return {
            "title": self.name,
            "page_url": url if url.startswith("http") else self.abs_url(url),
            "stream_url": None,
            "headers": self.headers,
            "extractor": "hanime-plugin/HanimeTV",
        }


class HentaiCityWebs(AdultVideoSite):
    name = "Hentai City"
    sf = "hcity"
    search_paths = ["/search/{q}/", "/?q={q}", "/?s={q}"]
    card_sels = [".video-block", ".thumb-block", ".item", "article"]

    def __init__(self):
        super().__init__()
        self.url = "https://hentaicity.com"


class HentaiOceanWebs(AdultVideoSite):
    name = "Hentai Ocean"
    sf = "hocean"
    search_paths = ["/?s={q}", "/search/{q}/"]

    def __init__(self):
        super().__init__()
        self.url = "https://hentaiocean.com"


class HentaiShWebs(AdultVideoSite):
    name = "Hentai.sh"
    sf = "hsh"
    search_paths = ["/?s={q}", "/search?q={q}"]

    def __init__(self):
        super().__init__()
        self.url = "https://hentai.sh"


class HentaverseWebs(AdultVideoSite):
    name = "Hentaverse"
    sf = "hverse"
    search_paths = ["/?s={q}", "/search/{q}/"]

    def __init__(self):
        super().__init__()
        self.url = "https://hentaverse.com"


class MyHentaiMovieWebs(AdultVideoSite):
    name = "My Hentai Movie"
    sf = "mhmovie"
    search_paths = ["/?s={q}", "/search/{q}/"]

    def __init__(self):
        super().__init__()
        self.url = "https://myhentaimovie.com"


class OnlyHentaiStuffWebs(AdultVideoSite):
    name = "OnlyHentaiStuff"
    sf = "ohstuff"
    search_paths = ["/?s={q}"]

    def __init__(self):
        super().__init__()
        self.url = "https://onlyhentaistuff.com"


class WatchHentaiWebs(AdultVideoSite):
    name = "WatchHentai"
    sf = "whentai"
    search_paths = ["/?s={q}", "/search/{q}/"]

    def __init__(self):
        super().__init__()
        self.url = "https://watchhentai.net"


class HStreamWebs(AdultVideoSite):
    """hstream.moe — subtitle-rich source; engine remuxes eng.ass into MKV."""

    name = "HStream.moe"
    sf = "hstream"
    search_paths = ["/search?s={q}"]
    card_sels = [".items .item", "article", ".card"]
    has_subs = True

    def __init__(self):
        super().__init__()
        self.url = "https://hstream.moe"

    async def get_episode(self, url: str) -> Optional[Dict[str, Any]]:
        return {
            "title": self.name,
            "page_url": url if url.startswith("http") else self.abs_url(url),
            "stream_url": None,
            "headers": self.headers,
            "extractor": "hanime-plugin/Hstream",
            "subtitles": True,
        }


class OppaiStreamWebs(AdultVideoSite):
    """oppai.stream — handled by hanime-plugin's OppaiStream extractor."""

    name = "Oppai.stream"
    sf = "oppai"
    search_paths = ["/actions/search.php?text={q}", "/?s={q}"]
    card_sels = ["article", ".episode-shown", ".item"]

    def __init__(self):
        super().__init__()
        self.url = "https://oppai.stream"

    async def get_episode(self, url: str) -> Optional[Dict[str, Any]]:
        return {
            "title": self.name,
            "page_url": url if url.startswith("http") else self.abs_url(url),
            "stream_url": None,
            "headers": self.headers,
            "extractor": "hanime-plugin/OppaiStream",
        }
