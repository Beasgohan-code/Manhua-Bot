# Manhua-Bot - Normal (SFW) anime video sources

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from loguru import logger

from sources.video.base import VideoScraper, soup, clean, slug_of


class AllAnimeWebs(VideoScraper):
    """allanime.to — GraphQL API, returns episode lists reliably."""

    name = "AllAnime"
    sf = "allanime"
    adult = False

    def __init__(self):
        super().__init__()
        self.url = "https://allmanga.to"
        self.api = "https://api.allanime.day/api"

    @property
    def headers(self) -> Dict[str, str]:
        h = super().headers
        h["Referer"] = "https://allmanga.to/"
        return h

    async def _gql(self, query: str, variables: dict):
        import json

        try:
            return await self.get(
                self.api,
                rjson=True,
                headers=self.headers,
                params={"variables": json.dumps(variables), "query": query},
            )
        except Exception as exc:
            logger.debug(f"[allanime] gql: {exc}")
            return None

    async def search(self, query: str = "") -> List[Dict[str, Any]]:
        gql = """
        query($search: SearchInput, $limit: Int, $page: Int) {
          shows(search: $search, limit: $limit, page: $page) {
            edges { _id name thumbnail availableEpisodes }
          }
        }"""
        data = await self._gql(
            gql,
            {
                "search": {"allowAdult": False, "allowUnknown": False, "query": query},
                "limit": 20,
                "page": 1,
            },
        )
        if not data:
            return []
        out = []
        for show in ((data.get("data") or {}).get("shows") or {}).get("edges") or []:
            sid = show.get("_id")
            if not sid:
                continue
            out.append(
                {
                    "id": sid,
                    "title": show.get("name") or sid,
                    "url": f"{self.url}/anime/{sid}",
                    "cover": show.get("thumbnail") or "",
                    "src": self.sf,
                    "adult": False,
                    "kind": "video",
                }
            )
        return out

    async def get_series(self, sid: str) -> Optional[Dict[str, Any]]:
        sid = slug_of(sid) if str(sid).startswith("http") else sid
        gql = """
        query($showId: String!) {
          show(_id: $showId) {
            _id name thumbnail availableEpisodesDetail
          }
        }"""
        data = await self._gql(gql, {"showId": sid})
        show = ((data or {}).get("data") or {}).get("show") or {}
        if not show:
            return None
        detail = show.get("availableEpisodesDetail") or {}
        nums = detail.get("sub") or detail.get("dub") or detail.get("raw") or []

        def sort_key(x):
            try:
                return float(x)
            except Exception:
                return 0.0

        episodes = [
            {
                "id": f"{sid}:{n}",
                "num": str(n),
                "title": f"Episode {n}",
                "url": f"{self.url}/watch/{sid}/{n}",
            }
            for n in sorted(nums, key=sort_key)
        ]
        return {
            "id": sid,
            "title": show.get("name") or sid,
            "url": f"{self.url}/anime/{sid}",
            "cover": show.get("thumbnail") or "",
            "adult": False,
            "src": self.sf,
            "kind": "video",
            "episodes": episodes,
        }


class _WPAnimeSite(VideoScraper):
    """Shared scraper for the common WordPress anime themes."""

    adult = False
    search_path = "/?s={q}"
    card_sel = "article, .bs, .listupd .bsx, .item"
    title_sel = ".tt, .title, h2, h3"
    ep_link_sel = ".eplister li a, .episodios a, .eps a, ul.episodios li a"

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
        page = sid if str(sid).startswith("http") else f"{self.url}/anime/{sid}/"
        html = await self.html(page)
        if not html:
            return None
        s = soup(html)
        h1 = s.select_one("h1")
        title = clean(h1.get_text()) if h1 else slug_of(page)
        og = s.select_one('meta[property="og:image"]')

        episodes = []
        for a in s.select(self.ep_link_sel):
            href = a.get("href")
            if not href:
                continue
            label = clean(a.get_text()) or f"Episode {len(episodes) + 1}"
            m = re.search(r"(\d+(?:\.\d+)?)", label)
            episodes.append(
                {
                    "id": slug_of(href),
                    "num": m.group(1) if m else str(len(episodes) + 1),
                    "title": label,
                    "url": self.abs_url(href),
                }
            )
        episodes.reverse()  # sites list newest first
        if not episodes:
            episodes = [{"id": "1", "num": "1", "title": title, "url": page}]
        return {
            "id": slug_of(page),
            "title": title,
            "url": page,
            "cover": og.get("content") if og else "",
            "adult": False,
            "src": self.sf,
            "kind": "video",
            "episodes": episodes,
        }


class GogoAnimeWebs(_WPAnimeSite):
    name = "GogoAnime"
    sf = "gogo"
    search_path = "/search.html?keyword={q}"
    card_sel = ".items li, .last_episodes li"
    title_sel = ".name, p.name"

    def __init__(self):
        super().__init__()
        self.url = "https://anitaku.io"


class AnimePaheWebs(VideoScraper):
    """animepahe.ru — clean JSON API, good quality releases."""

    name = "AnimePahe"
    sf = "pahe"
    adult = False

    def __init__(self):
        super().__init__()
        self.url = "https://animepahe.ru"

    @property
    def headers(self) -> Dict[str, str]:
        h = super().headers
        h["Cookie"] = "__ddg2_=1"
        return h

    async def search(self, query: str = "") -> List[Dict[str, Any]]:
        try:
            data = await self.get(
                f"{self.url}/api",
                rjson=True,
                cs=True,
                headers=self.headers,
                params={"m": "search", "q": query},
            )
            if not data:
                return []
            out = []
            for item in (data.get("data") or [])[:20]:
                sess = item.get("session")
                if not sess:
                    continue
                out.append(
                    {
                        "id": sess,
                        "title": item.get("title") or sess,
                        "url": f"{self.url}/anime/{sess}",
                        "cover": item.get("poster") or "",
                        "src": self.sf,
                        "adult": False,
                        "kind": "video",
                    }
                )
            return out
        except Exception as exc:
            logger.error(f"[pahe] search: {exc}")
            return []

    async def get_series(self, sid: str) -> Optional[Dict[str, Any]]:
        sid = slug_of(sid) if str(sid).startswith("http") else sid
        episodes: List[Dict[str, Any]] = []
        title = sid
        try:
            page = 1
            while page <= 5:
                data = await self.get(
                    f"{self.url}/api",
                    rjson=True,
                    cs=True,
                    headers=self.headers,
                    params={"m": "release", "id": sid, "sort": "episode_asc", "page": page},
                )
                if not data or not data.get("data"):
                    break
                for ep in data["data"]:
                    num = ep.get("episode")
                    sess = ep.get("session")
                    episodes.append(
                        {
                            "id": str(sess),
                            "num": str(num),
                            "title": f"Episode {num}",
                            "url": f"{self.url}/play/{sid}/{sess}",
                        }
                    )
                if page >= (data.get("last_page") or 1):
                    break
                page += 1
        except Exception as exc:
            logger.error(f"[pahe] get_series: {exc}")
        return {
            "id": sid,
            "title": title,
            "url": f"{self.url}/anime/{sid}",
            "cover": "",
            "adult": False,
            "src": self.sf,
            "kind": "video",
            "episodes": episodes,
        }


class AnimeKaiWebs(_WPAnimeSite):
    name = "AnimeKai"
    sf = "akai"
    search_path = "/browser?keyword={q}"
    card_sel = ".aitem, .film_list-wrap .flw-item"
    title_sel = ".title, .film-name"

    def __init__(self):
        super().__init__()
        self.url = "https://animekai.to"
