
from sources.base.scraper import Scraper
import json, re
from bs4 import BeautifulSoup
from loguru import logger
from urllib.parse import urlparse, urljoin, quote, quote_plus
from sources.base.utils import DEAULT_MSG_FORMAT
class AquaReaderWebs(Scraper):
  def __init__(self):
    super().__init__()
    self.url = "https://aquareader.net"
    self.sf = "aqre"
    self.headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Referer": "https://aquareader.net/",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }
  async def search(self, query: str = ""):
    search_url = f"{self.url}/?s={quote_plus(query)}&post_type=wp-manga"
    html = await self.get(search_url, headers=self.headers, cs=True)
    soup = BeautifulSoup(html, "html.parser")
    results = []
    for row in soup.select(".c-tabs-item__content"):
      title_tag = row.select_one(".post-title a")
      if not title_tag:
        continue
      result_title = title_tag.get_text(strip=True)
      result_url = title_tag['href']
      img_tag = row.select_one(".tab-thumb img")
      thumbnail = img_tag['src'] if img_tag else None
      genres = [
          a.get_text(strip=True) for a in row.select("div.genres-content a")
      ]
      status = None
      for item in row.select("div.post-content_item"):
        heading = item.select_one('.summary-heading')
        if heading and 'status' in heading.get_text(strip=True).lower():
          content = item.select_one('.summary-content')
          status = content.get_text(strip=True) if content else None
          break
      results.append({
          "title": result_title,
          "url": result_url,
          "poster": thumbnail,
          "genres": genres if genres else "N/A",
          "status": status if status else "N/A"
      })
    return results
  async def get_chapters(self, data, page: int = 1):
    results = data
    try:
      html = await self.get(results['url'], headers=self.headers, cs=True)
      soup = BeautifulSoup(html, "html.parser")
      summary_tag = soup.select_one("div.description-summary .summary__content")
      summary = summary_tag.get_text(separator="\n", strip=True) if summary_tag else None
      genres = [a.get_text(strip=True) for a in soup.select("div.genres-content a")]
      genres = ", ".join(genres) if genres else "N/A"
      status = None
      for item in soup.select("div.post-content_item"):
        heading = item.select_one('.summary-heading')
        if heading and 'status' in heading.get_text(strip=True).lower():
            content = item.select_one('.summary-content')
            status = content.get_text(strip=True) if content else None
            break
      results['msg'] = DEAULT_MSG_FORMAT.format(
        title=results['title'],
        status=status if status else results['status'],
        genres=genres if genres else results['genres'],
        summary=summary[:200] if summary else "N/A",
        url=results['url']
      )
      if results['url'].endswith("/"):
        ajax_url = results['url'] + "ajax/chapters/"
      else:
        ajax_url = results['url'] + "/ajax/chapters/"
      results['chapters'] = []
      chapters_html = await self.get(ajax_url, headers=self.headers, cs=True)
      chapters_soup = BeautifulSoup(chapters_html, "html.parser")
      for li in chapters_soup.select("li.wp-manga-chapter"):
        a = li.find("a")
        if a:
          results['chapters'].append((a.get_text(strip=True), a["href"]))
    except Exception as err:
      logger.exception(f"AquaReader: {err}")
    return results
  def iter_chapters(self, data, page: int = 1):
    chapters_list = []
    if "chapters" in data:
      for card in data['chapters']:
        chapters_list.append({
            "title":
            card[0],
            "url":
            card[1],
            "manga_title":
            data['title'],
            "poster":
            data['poster'] if 'poster' in data else None,
        })
    return chapters_list[(page - 1) * 60:page *
                         60] if page != 1 else chapters_list
  async def get_pictures(self, url, data=None):
    html = await self.get(url, headers=self.headers, cs=True)
    soup = BeautifulSoup(html, "html.parser")
    container = soup.select_one('.reading-content')
    img_urls = []
    if container:
        for img in container.find_all("img", class_="wp-manga-chapter-img"):
            url = (img.get("data-src") or img.get("src") or "").strip()
            if url and url.startswith("http"):
                img_urls.append(url)
    return img_urls
