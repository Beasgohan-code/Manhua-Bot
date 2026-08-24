# Manhua-Bot - MangaFire
from sources.base.scraper import Scraper
from bs4 import BeautifulSoup
from loguru import logger
from urllib.parse import quote_plus

class MangaFireWebs(Scraper):
    def __init__(self):
        super().__init__()
        self.url = "https://mangafire.to"
        self.sf = "mf"
        self.headers = {"User-Agent": "Mozilla/5.0", "Referer": self.url + "/"}

    async def search(self, query: str = ""):
        try:
            html = await self.get(f"{self.url}/filter?keyword={quote_plus(query)}", headers=self.headers)
            if not html:
                return []
            soup = BeautifulSoup(html, "lxml")
            out = []
            for a in soup.select("a")[:40]:
                href = a.get("href") or ""
                if "/manga/" not in href:
                    continue
                title = a.get_text(strip=True) or a.get("title") or href
                if len(title) < 2:
                    continue
                full = href if href.startswith("http") else self.url + href
                out.append({"id": full.rstrip("/").split("/")[-1], "title": title[:120], "url": full, "src": self.sf})
            seen, res = set(), []
            for r in out:
                if r["url"] not in seen:
                    seen.add(r["url"]); res.append(r)
            return res[:20]
        except Exception as e:
            logger.error(f"[mf] search: {e}")
            return []

    async def get_manga(self, manga_id: str):
        url = manga_id if str(manga_id).startswith("http") else f"{self.url}/manga/{manga_id}"
        try:
            html = await self.get(url, headers=self.headers)
            if not html:
                return None
            soup = BeautifulSoup(html, "lxml")
            title_el = soup.select_one("h1")
            title = title_el.get_text(strip=True) if title_el else str(manga_id)
            chapters = []
            for a in soup.select("a[href*='/read/'], a[href*='/chapter']")[:300]:
                href = a.get("href") or ""
                text = a.get_text(strip=True)
                if not text:
                    continue
                full = href if href.startswith("http") else self.url + href
                chapters.append({"title": text, "url": full, "num": text})
            return {"id": str(manga_id), "title": title, "url": url, "chapters": chapters, "src": self.sf}
        except Exception as e:
            logger.error(f"[mf] get_manga: {e}")
            return None

    async def get_chapter(self, chapter_url: str):
        try:
            html = await self.get(chapter_url, headers=self.headers)
            if not html:
                return []
            soup = BeautifulSoup(html, "lxml")
            pages = []
            for img in soup.select("img"):
                src = img.get("data-src") or img.get("src")
                if src and src.startswith("http") and any(x in src for x in ["manga", "chapter", "cdn", "fire"]):
                    pages.append(src)
            return list(dict.fromkeys(pages))
        except Exception as e:
            logger.error(f"[mf] get_chapter: {e}")
            return []
