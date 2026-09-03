# Manhua-Bot - Adult video sources (gated behind /adult on)
#
# Every source here is marked adult=True, so it is invisible in /vsearch
# and /vsources until the user opts in with /adult on.

from __future__ import annotations

from typing import Any, Dict, List, Optional

from loguru import logger

from sources.video.base import VideoScraper, soup, clean, slug_of


class _SimpleHentaiSite(VideoScraper):
    """Most of these sites are WordPress/WP-Script video themes.

    They share the same shape: /?s=query for search, a grid of <article>
    cards, and a watch page whose <iframe> is handed to yt-dlp. Subclasses
    only override the URL and the selectors that differ.
    """

    adult = True
    search_path = "/?s={q}"
    card_sel = "article, .video-block, .item"
    title_sel = ".title, h2, h3"
    ep_sel = "a"

    async def search(self, query: str = "") -> List[Dict[str, Any]]:
        try:
            url = self.url + self.search_path.format(q=self.q(query))
            return await self._cards(
                url, self.card_sel, title_sel=self.title_sel, limit=15
            )
        except Exception as exc:
            logger.error(f"[{self.sf}] search: {exc}")
            return []

    async def get_series(self, sid: str) -> Optional[Dict[str, Any]]:
        """Single videos are treated as a one-episode series."""
        page = sid if str(sid).startswith("http") else f"{self.url}/{sid}"
        html = await self.html(page)
        if not html:
            return None
        s = soup(html)
        h1 = s.select_one("h1")
        title = clean(h1.get_text()) if h1 else slug_of(page)
        og = s.select_one('meta[property="og:image"]')
        return {
            "id": slug_of(page),
            "title": title,
            "url": page,
            "cover": og.get("content") if og else "",
            "adult": True,
            "src": self.sf,
            "kind": "video",
            "episodes": [
                {"id": "1", "num": "1", "title": title, "url": page}
            ],
        }


class HAnimeTVWebs(_SimpleHentaiSite):
    """hanime.tv — public JSON search API."""

    name = "HAnime.tv"
    sf = "hanime"

    def __init__(self):
        super().__init__()
        self.url = "https://hanime.tv"
        self.api = "https://search.htv-services.com"

    async def search(self, query: str = "") -> List[Dict[str, Any]]:
        try:
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
            raw = await self.post(
                self.api, rjson=True, json=payload, headers=self.headers
            )
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
        try:
            data = await self.get(
                f"https://hanime.tv/rapi/v7/video?id={slug}",
                rjson=True,
                headers=self.headers,
            )
        except Exception:
            data = None
        title, cover, episodes = slug, "", []
        if data:
            hv = data.get("hentai_video") or {}
            title = hv.get("name") or slug
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


class HentaiCityWebs(_SimpleHentaiSite):
    name = "Hentai City"
    sf = "hcity"
    search_path = "/search/{q}/"
    card_sel = ".video-block, .item, article"

    def __init__(self):
        super().__init__()
        self.url = "https://hentaicity.com"


class HentaiOceanWebs(_SimpleHentaiSite):
    name = "Hentai Ocean"
    sf = "hocean"
    search_path = "/?s={q}"

    def __init__(self):
        super().__init__()
        self.url = "https://hentaiocean.com"


class HentaiShWebs(_SimpleHentaiSite):
    name = "Hentai.sh"
    sf = "hsh"
    search_path = "/?s={q}"

    def __init__(self):
        super().__init__()
        self.url = "https://hentai.sh"


class HentaverseWebs(_SimpleHentaiSite):
    name = "Hentaverse"
    sf = "hverse"
    search_path = "/?s={q}"

    def __init__(self):
        super().__init__()
        self.url = "https://hentaverse.com"


class MyHentaiMovieWebs(_SimpleHentaiSite):
    name = "My Hentai Movie"
    sf = "mhmovie"
    search_path = "/?s={q}"

    def __init__(self):
        super().__init__()
        self.url = "https://myhentaimovie.com"


class OnlyHentaiStuffWebs(_SimpleHentaiSite):
    name = "OnlyHentaiStuff"
    sf = "ohstuff"
    search_path = "/?s={q}"

    def __init__(self):
        super().__init__()
        self.url = "https://onlyhentaistuff.com"


class WatchHentaiWebs(_SimpleHentaiSite):
    name = "WatchHentai"
    sf = "whentai"
    search_path = "/?s={q}"

    def __init__(self):
        super().__init__()
        self.url = "https://watchhentai.net"
