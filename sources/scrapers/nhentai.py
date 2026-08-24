# Manhua-Bot - nhentai (adult) scraper

from sources.base.scraper import Scraper
from loguru import logger
import re

class NHentaiWebs(Scraper):
    def __init__(self):
        super().__init__()
        self.url = "https://nhentai.net"
        self.sf = "nh"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://nhentai.net/",
        }

    async def search(self, query: str = ""):
        try:
            data = await self.get(
                f"{self.url}/api/galleries/search",
                params={"query": query, "page": 1},
                rjson=True,
                headers=self.headers,
            )
            if not data:
                return []
            results = []
            for item in data.get("result", [])[:20]:
                mid = str(item.get("id"))
                title = (
                    (item.get("title") or {}).get("english")
                    or (item.get("title") or {}).get("pretty")
                    or f"#{mid}"
                )
                media_id = item.get("media_id")
                cover = f"https://t.nhentai.net/galleries/{media_id}/cover.jpg" if media_id else None
                results.append({
                    "id": mid,
                    "title": title,
                    "url": f"{self.url}/g/{mid}/",
                    "cover": cover,
                    "src": self.sf,
                })
            return results
        except Exception as e:
            logger.error(f"[nhentai] search: {e}")
            return []

    async def get_manga(self, manga_id: str):
        try:
            data = await self.get(
                f"{self.url}/api/gallery/{manga_id}",
                rjson=True,
                headers=self.headers,
            )
            if not data:
                return None
            title = (
                (data.get("title") or {}).get("english")
                or (data.get("title") or {}).get("pretty")
                or f"#{manga_id}"
            )
            media_id = data.get("media_id")
            pages = data.get("num_pages", 0)
            return {
                "id": str(data.get("id")),
                "title": title,
                "url": f"{self.url}/g/{manga_id}/",
                "cover": f"https://t.nhentai.net/galleries/{media_id}/cover.jpg" if media_id else None,
                "chapters": [{
                    "id": "1",
                    "title": title,
                    "url": f"{self.url}/g/{manga_id}/",
                    "num": "1",
                }],
                "pages": pages,
                "src": self.sf,
            }
        except Exception as e:
            logger.error(f"[nhentai] get_manga: {e}")
            return None

    async def get_chapter(self, chapter_url: str):
        # extract id
        m = re.search(r"/g/(\d+)", chapter_url)
        if not m:
            return []
        gid = m.group(1)
        try:
            data = await self.get(
                f"{self.url}/api/gallery/{gid}",
                rjson=True,
                headers=self.headers,
            )
            if not data:
                return []
            media_id = data.get("media_id")
            images = (data.get("images") or {}).get("pages") or []
            ext_map = {"j": "jpg", "p": "png", "g": "gif", "w": "webp"}
            pages = []
            for i, img in enumerate(images, 1):
                t = img.get("t", "j")
                ext = ext_map.get(t, "jpg")
                pages.append(f"https://i.nhentai.net/galleries/{media_id}/{i}.{ext}")
            return pages
        except Exception as e:
            logger.error(f"[nhentai] get_chapter: {e}")
            return []
