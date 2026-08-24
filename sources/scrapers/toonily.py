# Manhua-Bot - Toonily scraper

from sources.base.scraper import Scraper
from bs4 import BeautifulSoup
from loguru import logger
from urllib.parse import quote_plus
import re

class ToonilyWebs(Scraper):
    def __init__(self):
        super().__init__()
        self.url = "https://toonily.com"
        self.sf = "tn"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://toonily.com/",
        }

    async def search(self, query: str = ""):
        try:
            html = await self.get(
                f"{self.url}/?s={quote_plus(query)}&post_type=wp-manga",
                headers=self.headers,
                cs=True,
            )
            if not html:
                return []
            soup = BeautifulSoup(html, "lxml")
            results = []
            for card in soup.select(".c-tabs-item__content, .tab-content-wrap .row .col-12")[:20]:
                a = card.select_one("a")
                if not a:
                    continue
                href = a.get("href") or ""
                title_el = card.select_one(".post-title h3, .post-title a, h3 a")
                title = title_el.get_text(strip=True) if title_el else a.get("title") or href
                img = card.select_one("img")
                cover = img.get("data-src") or img.get("src") if img else None
                results.append({
                    "id": href.rstrip("/").split("/")[-1],
                    "title": title,
                    "url": href,
                    "cover": cover,
                    "src": self.sf,
                })
            return results
        except Exception as e:
            logger.error(f"[toonily] search: {e}")
            return []

    async def get_manga(self, manga_id: str):
        url = manga_id if str(manga_id).startswith("http") else f"{self.url}/manga/{manga_id}/"
        try:
            html = await self.get(url, headers=self.headers, cs=True)
            if not html:
                return None
            soup = BeautifulSoup(html, "lxml")
            title_el = soup.select_one(".post-title h1, h1")
            title = title_el.get_text(strip=True) if title_el else manga_id
            cover_el = soup.select_one(".summary_image img, .wp-post-image")
            cover = None
            if cover_el:
                cover = cover_el.get("data-src") or cover_el.get("src")
            chapters = []
            for li in soup.select(".wp-manga-chapter, .listing-chapters_wrap li"):
                a = li.select_one("a")
                if not a:
                    continue
                href = a.get("href") or ""
                text = a.get_text(strip=True)
                num = re.search(r"([\d.]+)", text)
                chapters.append({
                    "id": href.rstrip("/").split("/")[-1],
                    "title": text,
                    "url": href,
                    "num": num.group(1) if num else text,
                })
            return {
                "id": str(manga_id),
                "title": title,
                "url": url,
                "cover": cover,
                "chapters": chapters,
                "src": self.sf,
            }
        except Exception as e:
            logger.error(f"[toonily] get_manga: {e}")
            return None

    async def get_chapter(self, chapter_url: str):
        try:
            html = await self.get(chapter_url, headers=self.headers, cs=True)
            if not html:
                return []
            soup = BeautifulSoup(html, "lxml")
            pages = []
            for img in soup.select(".reading-content img, .page-break img, #images img"):
                src = img.get("data-src") or img.get("src")
                if src and src.startswith("http"):
                    pages.append(src)
            return pages
        except Exception as e:
            logger.error(f"[toonily] get_chapter: {e}")
            return []
