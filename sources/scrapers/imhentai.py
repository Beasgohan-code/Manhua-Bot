# Manhua-Bot - ImHentai-style adult scraper (gallery listing)

from sources.base.scraper import Scraper
from loguru import logger
from bs4 import BeautifulSoup
import re

class ImHentaiWebs(Scraper):
    def __init__(self):
        super().__init__()
        self.url = "https://imhentai.xxx"
        self.sf = "ih"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://imhentai.xxx/",
        }

    async def search(self, query: str = ""):
        try:
            html = await self.get(
                f"{self.url}/search/?key={query}",
                headers=self.headers,
            )
            if not html:
                return []
            soup = BeautifulSoup(html, "lxml")
            results = []
            for card in soup.select(".gallery, .thumb, .caption")[:20]:
                a = card if card.name == "a" else card.select_one("a")
                if not a:
                    continue
                href = a.get("href") or ""
                if "/gallery/" not in href and "/g/" not in href:
                    continue
                title_el = card.select_one(".caption, .title, h2, h3") or a
                title = title_el.get_text(strip=True) if title_el else href
                img = card.select_one("img")
                cover = None
                if img:
                    cover = img.get("data-src") or img.get("src")
                gid = href.rstrip("/").split("/")[-1]
                results.append({
                    "id": gid,
                    "title": title[:120],
                    "url": href if href.startswith("http") else self.url + href,
                    "cover": cover,
                    "src": self.sf,
                })
            return results
        except Exception as e:
            logger.error(f"[imhentai] search: {e}")
            return []

    async def get_manga(self, manga_id: str):
        url = manga_id if str(manga_id).startswith("http") else f"{self.url}/gallery/{manga_id}/"
        try:
            html = await self.get(url, headers=self.headers)
            if not html:
                return None
            soup = BeautifulSoup(html, "lxml")
            title_el = soup.select_one("h1, .gallery_title, .title")
            title = title_el.get_text(strip=True) if title_el else str(manga_id)
            cover_el = soup.select_one(".gallery_thumb img, .cover img, img")
            cover = None
            if cover_el:
                cover = cover_el.get("data-src") or cover_el.get("src")
            return {
                "id": str(manga_id),
                "title": title,
                "url": url,
                "cover": cover,
                "chapters": [{
                    "id": "1",
                    "title": title,
                    "url": url,
                    "num": "1",
                }],
                "src": self.sf,
            }
        except Exception as e:
            logger.error(f"[imhentai] get_manga: {e}")
            return None

    async def get_chapter(self, chapter_url: str):
        try:
            html = await self.get(chapter_url, headers=self.headers)
            if not html:
                return []
            soup = BeautifulSoup(html, "lxml")
            pages = []
            for img in soup.select(".gallery_page img, #image-container img, .page-img, img.lazy"):
                src = img.get("data-src") or img.get("src")
                if src and src.startswith("http") and not src.endswith(".gif"):
                    pages.append(src)
            # dedupe preserve order
            seen = set()
            out = []
            for p in pages:
                if p not in seen:
                    seen.add(p)
                    out.append(p)
            return out
        except Exception as e:
            logger.error(f"[imhentai] get_chapter: {e}")
            return []
