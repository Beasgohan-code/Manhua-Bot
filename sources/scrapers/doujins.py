# Manhua-Bot - Doujins.com (adult)
from sources.base.scraper import Scraper
from bs4 import BeautifulSoup
from loguru import logger
from urllib.parse import quote_plus

class DoujinsWebs(Scraper):
    def __init__(self):
        super().__init__()
        self.url = "https://doujins.com"
        self.sf = "douj"
        self.headers = {"User-Agent": "Mozilla/5.0", "Referer": self.url + "/"}

    async def search(self, query: str = ""):
        try:
            html = await self.get(f"{self.url}/searches?words={quote_plus(query)}", headers=self.headers)
            if not html:
                return []
            soup = BeautifulSoup(html, "lxml")
            out = []
            for a in soup.select("a.gallery, .gallery-item a, a[href*='/gallery/'], a[href*='/g/']")[:30]:
                href = a.get("href") or ""
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
            logger.error(f"[douj] search: {e}")
            return []

    async def get_manga(self, manga_id: str):
        url = manga_id if str(manga_id).startswith("http") else f"{self.url}/gallery/{manga_id}"
        try:
            html = await self.get(url, headers=self.headers)
            if not html:
                return None
            soup = BeautifulSoup(html, "lxml")
            title_el = soup.select_one("h1, .gallery-title, .title")
            title = title_el.get_text(strip=True) if title_el else str(manga_id)
            return {
                "id": str(manga_id), "title": title, "url": url, "src": self.sf,
                "chapters": [{"title": title, "url": url, "num": "1"}],
            }
        except Exception as e:
            logger.error(f"[douj] get_manga: {e}")
            return None

    async def get_chapter(self, chapter_url: str):
        try:
            html = await self.get(chapter_url, headers=self.headers)
            if not html:
                return []
            soup = BeautifulSoup(html, "lxml")
            pages = []
            for img in soup.select(".gallery-image img, #gallery img, img.lazy, img"):
                src = img.get("data-src") or img.get("src")
                if src and src.startswith("http"):
                    pages.append(src)
            return list(dict.fromkeys(pages))
        except Exception as e:
            logger.error(f"[douj] get_chapter: {e}")
            return []
