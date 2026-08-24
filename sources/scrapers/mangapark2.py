# Manhua-Bot - MangaPark alternate endpoint helper (lightweight search)

from sources.base.scraper import Scraper
from loguru import logger
from urllib.parse import quote_plus
from bs4 import BeautifulSoup

class MangaParkAltWebs(Scraper):
    def __init__(self):
        super().__init__()
        self.url = "https://mangapark.net"
        self.sf = "mpk"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://mangapark.net/",
        }

    async def search(self, query: str = ""):
        try:
            html = await self.get(
                f"{self.url}/search?word={quote_plus(query)}",
                headers=self.headers,
            )
            if not html:
                return []
            soup = BeautifulSoup(html, "lxml")
            results = []
            for a in soup.select("a.link-hover, .ms-item a, .manga-list a")[:20]:
                href = a.get("href") or ""
                if "/title/" not in href and "/manga/" not in href:
                    continue
                title = a.get_text(strip=True) or a.get("title") or href
                if len(title) < 2:
                    continue
                full = href if href.startswith("http") else self.url + href
                results.append({
                    "id": href.rstrip("/").split("/")[-1],
                    "title": title[:120],
                    "url": full,
                    "src": self.sf,
                })
            # dedupe by url
            seen, out = set(), []
            for r in results:
                if r["url"] not in seen:
                    seen.add(r["url"])
                    out.append(r)
            return out
        except Exception as e:
            logger.error(f"[mangaparkalt] search: {e}")
            return []

    async def get_manga(self, manga_id: str):
        url = manga_id if str(manga_id).startswith("http") else f"{self.url}/title/{manga_id}"
        try:
            html = await self.get(url, headers=self.headers)
            if not html:
                return None
            soup = BeautifulSoup(html, "lxml")
            title_el = soup.select_one("h1, .item-title, .manga-title")
            title = title_el.get_text(strip=True) if title_el else str(manga_id)
            chapters = []
            for a in soup.select("a[href*='/comic/'], a[href*='/chapter'], .chapter-list a")[:200]:
                href = a.get("href") or ""
                text = a.get_text(strip=True)
                if not text:
                    continue
                full = href if href.startswith("http") else self.url + href
                chapters.append({"title": text, "url": full, "num": text})
            return {
                "id": str(manga_id),
                "title": title,
                "url": url,
                "chapters": chapters,
                "src": self.sf,
            }
        except Exception as e:
            logger.error(f"[mangaparkalt] get_manga: {e}")
            return None

    async def get_chapter(self, chapter_url: str):
        try:
            html = await self.get(chapter_url, headers=self.headers)
            if not html:
                return []
            soup = BeautifulSoup(html, "lxml")
            pages = []
            for img in soup.select("img[src*='mpf'], .page-img, #viewer img, img.lazy"):
                src = img.get("data-src") or img.get("src")
                if src and src.startswith("http"):
                    pages.append(src)
            return pages
        except Exception as e:
            logger.error(f"[mangaparkalt] get_chapter: {e}")
            return []
