
from sources.base.scraper import Scraper
import json
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin, quote, quote_plus
import re
from loguru import logger
from sources.base.utils import DEAULT_MSG_FORMAT
class LikeMangaWebs(Scraper):
  def __init__(self):
    super().__init__()
    self.url = "https://likemanga.in"
    self.sf = "ikin"
    self.headers = {
      "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:97.0) Gecko/20100101 Firefox/97.0"
    }
  async def search(self, query: str = ""):
    params = {"s": query, "post_type": "wp-manga"}
    html = await self.get(self.url, params=params, headers=self.headers)
    if not html:
      return []
    soup = BeautifulSoup(html, "html.parser")
    results = []
    for row in soup.select("div.c-tabs-item__content"):
        title_tag = row.select_one(".post-title a")
        if not title_tag:
            continue
        result_title = title_tag.get_text(strip=True)
        result_url = title_tag['href']
        img_tag = row.select_one(".tab-thumb img")
        thumbnail = img_tag['src'] if img_tag else None
        results.append({
            "title": result_title,
            "url": result_url,
            "poster": thumbnail
        })
    return results
  async def get_chapters(self, data, page: int=1):
    results = data
    content = await self.get(results['url'], headers=self.headers)
    if content:
      soup = BeautifulSoup(content, "html.parser")
      summary_tag = soup.select_one("div.description-summary .summary__content")
      summary = summary_tag.get_text(separator="\n", strip=True) if summary_tag else "N/A"
      genres = [a.get_text(strip=True) for a in soup.select("div.genres-content a")]
      genres = ", ".join(genres) if genres else "N/A"
      try:
        status = next(
          (
            item.select_one('.summary-content').get_text(strip=True)
            if item.select_one('.summary-content') else None
            for item in soup.select("div.post-content_item")
            if 'status' in item.select_one('.summary-heading').get_text(strip=True).lower()
          ),
          "N/A"
        )
      except:
        status = "N/A"
      results['msg'] = DEAULT_MSG_FORMAT.format(
        title=results['title'],
        status=status if status else "N/A",
        genres=genres if genres else "N/A",
        summary=summary[:400] if summary else "N/A",
        url=results['url']
      )
      cover = soup.select_one("div.summary_image img")
      results['poster'] = cover['src'] if cover else None
      if results['url'].endswith("/"):
          ajax_url = results['url'] + "ajax/chapters/"
      else:
          ajax_url = results['url'] + "/ajax/chapters/"
      headers = self.headers.copy()
      headers['X-Requested-With'] = 'XMLHttpRequest'
      chapters_html = await self.post(ajax_url, headers=headers)
      results['chapters'] = []
      chapters_soup = BeautifulSoup(chapters_html, "html.parser")
      for li in chapters_soup.select("li.wp-manga-chapter"):
        a = li.find("a")
        if a:
          results['chapters'].append((a.get_text(strip=True), a["href"]))
    return results
  def iter_chapters(self, data, page: int=1):
    chapters_list = []
    if not data['chapters']:
      return []
    for chapters in data['chapters']:
      try:
        chapters_list.append({
          "title": chapters[0],
          "url": chapters[1],
          "manga_title": data['title'],
          "poster": data['poster'] if 'poster' in data else None,
        })
      except:
        continue
    return chapters_list[(page - 1) * 60:page * 60] if page != 1 else chapters_list
  async def get_pictures(self, url, data=None):
    try:
      logger.info(f"LikeManga: Fetching images from {url}")
      response = await self.get(url, headers=self.headers)
      if not response:
        logger.warning("LikeManga: No response from page")
        return []
      soup = BeautifulSoup(response, "html.parser")
      container = soup.select_one('.reading-content')
      img_urls = []
      if container:
          for img in container.find_all("img", class_="wp-manga-chapter-img"):
              img_url = (img.get("data-src") or img.get("src") or "").strip()
              if img_url and img_url.startswith("http"):
                  img_urls.append(img_url)
      logger.info(f"LikeManga: Found {len(img_urls)} images")
      return img_urls
    except Exception as e:
      logger.error(f"LikeManga Error: {e}")
      return []
