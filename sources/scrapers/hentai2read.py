# Manhua-Bot - Hentai2Read (adult)
from sources.base.scraper import Scraper
from bs4 import BeautifulSoup
from loguru import logger
from urllib.parse import quote_plus

class Hentai2ReadWebs(Scraper):
    def __init__(self):
        super().__init__()
        self.url = "https://hentai2read.com"
        self.sf = "h2r"
        self.headers = {"User-Agent": "Mozilla/5.0", "Referer": self.url + "/"}

    async def search(self, query: str = ""):
        try:
            html = await self.get(f"{self.url}/hentai-list/search/{quote_plus(query)}", headers=self.headers)
            if not html:
                return []
            soup = BeautifulSoup(html, "lxml")
            out = []
            for a in soup.select(".book-grid a, .overlay a, a.book-title, .title a")[:25]:
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
            return res
        except Exception as e:
            logger.error(f"[h2r] search: {e}")
            return []

    async def get_manga(self, manga_id: str):
        url = manga_id if str(manga_id).startswith("http") else f"{self.url}/{manga_id}/"
        try:
            html = await self.get(url, headers=self.headers)
            if not html:
                return None
            soup = BeautifulSoup(html, "lxml")
            title_el = soup.select_one("h3.block-title, h1")
            title = title_el.get_text(strip=True) if title_el else str(manga_id)
            chapters = []
            for a in soup.select(".nav-chapters a, ul.nav-chapters li a, .chapter-list a")[:200]:
                href = a.get("href") or ""
                text = a.get_text(strip=True)
                full = href if href.startswith("http") else self.url + href
                chapters.append({"title": text, "url": full, "num": text})
            if not chapters:
                chapters = [{"title": title, "url": url, "num": "1"}]
            return {"id": str(manga_id), "title": title, "url": url, "chapters": chapters, "src": self.sf}
        except Exception as e:
            logger.error(f"[h2r] get_manga: {e}")
            return None

    async def get_chapter(self, chapter_url: str):
        try:
            html = await self.get(chapter_url, headers=self.headers)
            if not html:
                return []
            soup = BeautifulSoup(html, "lxml")
            pages = []
            for img in soup.select("#js-reader img, .img-responsive, .reader-images img, img"):
                src = img.get("data-src") or img.get("src")
                if src and src.startswith("http"):
                    pages.append(src)
            return list(dict.fromkeys(pages))
        except Exception as e:
            logger.error(f"[h2r] get_chapter: {e}")
            return []
