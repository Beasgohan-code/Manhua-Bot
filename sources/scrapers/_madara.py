"""Shared Madara / WP-Manga helpers for thin site wrappers."""
from sources.base.scraper import Scraper
from bs4 import BeautifulSoup
from loguru import logger
from urllib.parse import quote_plus
import re

class MadaraBase(Scraper):
    url = ""
    sf = ""
    search_path = "/?s={q}&post_type=wp-manga"
    use_cs = True

    def __init__(self):
        super().__init__()
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": self.url + "/",
        }

    async def search(self, query: str = ""):
        try:
            path = self.search_path.format(q=quote_plus(query))
            html = await self.get(self.url + path, headers=self.headers, cs=self.use_cs)
            if not html:
                return []
            soup = BeautifulSoup(html, "lxml")
            results = []
            for card in soup.select(
                ".c-tabs-item__content, .tab-thumb, .page-item-detail, .manga, .bsx, .list-item"
            )[:20]:
                a = card.select_one("a")
                if not a:
                    continue
                href = a.get("href") or ""
                if not href:
                    continue
                title_el = card.select_one(
                    ".post-title h3, .post-title a, h3 a, .tt, .manga-title, .title"
                )
                title = (title_el.get_text(strip=True) if title_el else None) or a.get("title") or href
                img = card.select_one("img")
                cover = None
                if img:
                    cover = img.get("data-src") or img.get("src")
                full = href if href.startswith("http") else self.url + href
                results.append({
                    "id": full.rstrip("/").split("/")[-1],
                    "title": title[:120],
                    "url": full,
                    "cover": cover,
                    "src": self.sf,
                })
            # dedupe
            seen, out = set(), []
            for r in results:
                if r["url"] not in seen:
                    seen.add(r["url"])
                    out.append(r)
            return out
        except Exception as e:
            logger.error(f"[{self.sf}] search: {e}")
            return []

    async def get_manga(self, manga_id: str):
        url = manga_id if str(manga_id).startswith("http") else f"{self.url}/manga/{manga_id}/"
        try:
            html = await self.get(url, headers=self.headers, cs=self.use_cs)
            if not html:
                return None
            soup = BeautifulSoup(html, "lxml")
            title_el = soup.select_one(".post-title h1, h1.entry-title, h1")
            title = title_el.get_text(strip=True) if title_el else str(manga_id)
            cover_el = soup.select_one(".summary_image img, .wp-post-image, .thumb img")
            cover = None
            if cover_el:
                cover = cover_el.get("data-src") or cover_el.get("src")
            chapters = []
            for li in soup.select(
                "li.wp-manga-chapter, .listing-chapters_wrap li, .mainversion-chapter, .eplister li, #chapterlist li"
            ):
                a = li.select_one("a")
                if not a:
                    continue
                href = a.get("href") or ""
                text = a.get_text(" ", strip=True)
                num = re.search(r"([\d.]+)", text)
                full = href if href.startswith("http") else self.url + href
                chapters.append({
                    "id": full.rstrip("/").split("/")[-1],
                    "title": text,
                    "url": full,
                    "num": num.group(1) if num else text,
                })
            # status / genres / description
            status = ""
            st = soup.select_one(".post-status .summary-content, .status, .manga-status, .post-content_item")
            # common madara rows
            for row in soup.select(".post-content_item, .summary-heading"):
                label = row.get_text(" ", strip=True).lower()
                if "status" in label:
                    val = row.select_one(".summary-content")
                    status = val.get_text(strip=True) if val else row.get_text(" ", strip=True)
            genres = []
            for a in soup.select(".genres-content a, .genre-item a, .manga-genres a, .genres a"):
                g = a.get_text(strip=True)
                if g:
                    genres.append(g)
            desc = ""
            desc_el = soup.select_one(".description-summary .summary__content, .manga-summary, .summary, .description, .dsct")
            if desc_el:
                desc = desc_el.get_text(" ", strip=True)

            return {
                "id": str(manga_id),
                "title": title,
                "url": url,
                "cover": cover,
                "poster": cover,
                "chapters": chapters,
                "status": status or None,
                "genres": genres or None,
                "description": desc or None,
                "src": self.sf,
            }
        except Exception as e:
            logger.error(f"[{self.sf}] get_manga: {e}")
            return None

    async def get_chapter(self, chapter_url: str):
        try:
            html = await self.get(chapter_url, headers=self.headers, cs=self.use_cs)
            if not html:
                return []
            soup = BeautifulSoup(html, "lxml")
            pages = []
            for img in soup.select(
                ".reading-content img, .page-break img, #images img, .rdminimal img, #readerarea img"
            ):
                src = img.get("data-src") or img.get("data-lazy-src") or img.get("src")
                if src and src.startswith("http") and not src.endswith(".gif"):
                    pages.append(src)
            seen, out = set(), []
            for p in pages:
                if p not in seen:
                    seen.add(p)
                    out.append(p)
            return out
        except Exception as e:
            logger.error(f"[{self.sf}] get_chapter: {e}")
            return []
