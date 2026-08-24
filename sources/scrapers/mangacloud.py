
from sources.base.scraper import Scraper
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin, quote, quote_plus
from loguru import logger
from sources.base.utils import DEAULT_MSG_FORMAT
class MangaCloudWebs(Scraper):
  def __init__(self):
    super().__init__()
    self.url = "https://mangacloud.org/"
    self.api_base = "https://api.mangacloud.org"
    self.sf = "mclo"
    self.headers = {
      "Accept": "application/json",
      "Referer": "https://mangacloud.org",
      "User-Agent": "Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Mobile Safari/537.36",
    }
  async def search(self, query: str = ""):
    url = f"{self.api_base}/search"
    payload = {"terms": query}
    data = await self.post(url, rjson=True, json=payload, headers=self.headers)
    if not data:
      return []
    results = []
    for result in data.get("data", [])[:8]:
      title = result.get("title", "")
      manga_id = result.get("id", "")
      url = f"https://mangacloud.org/comic/{manga_id}"
      cover = result.get("cover", {})
      cover_id = cover.get("id", "")
      cover_fmt = cover.get("f", "jpeg").lower()
      thumbnail = f"https://pika.mangacloud.org/{manga_id}/{cover_id}.{cover_fmt}" if cover_id else ""
      results.append({
          "title": title,
          "url": url,
          "poster": thumbnail
      })
    return results
  async def get_chapters(self, data, page: int=1):
    results = data
    manga_id = results['url'].rstrip('/').split('/')[-1]
    url = f"{self.api_base}/comic/{manga_id}"
    data = await self.get(url, rjson=True, headers=self.headers)
    if data:
      info = data.get("data", {})
      description = info.get("description", "No description available")
      status = info.get("status", "Unknown")
      genres = ", ".join([tag["name"] for tag in info.get("tags", []) if tag.get("type")=="genre"][:4]) or "None"
      results['msg'] = DEAULT_MSG_FORMAT.format(
        title=results['title'],
        status=status if status else "N/A",
        genres=genres if genres else "N/A",
        summary=description[:400] if description else "N/A",
        url=results['url']
      )
      cover = info.get("cover", {})
      cover_id = cover.get("id", "")
      cover_fmt = cover.get("f", "jpeg").lower()
      results['poster'] = f"https://pika.mangacloud.org/{manga_id}/{cover_id}.{cover_fmt}" if cover_id and not results['poster'] else results['poster']
      results['chapters'] = []
      for chap in info.get("chapters", []):
        chap_id = chap.get("id")
        number = chap.get("number")
        name = chap.get("name")
        chapter_title = f"Chapter {number}" + (f" {name}" if name else "")
        chapter_url = f"https://mangacloud.org/comic/{manga_id}/chapter/{chap_id}"
        results['chapters'].append((chapter_title, chapter_url))
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
          "poster": data.get('poster'),
        })
      except Exception as e:
        logger.debug(f"MangaCloud: Error parsing chapter: {e}")
        continue
    return chapters_list[(page - 1) * 60:page * 60] if page != 1 else chapters_list
  async def get_pictures(self, url, data=None):
    parts = url.rstrip("/").split("/")
    try:
        manga_id = parts[-3]
        chapter_id = parts[-1]
    except Exception:
        return []
    api_url = f"{self.api_base}/chapter/{chapter_id}"
    data = await self.get(api_url, rjson=True, headers=self.headers)
    image_urls = []
    if data:
      images = data.get("data", {}).get("images", [])
      for img in images:
        image_id = img.get("id")
        fmt = img.get("f", "jpeg").lower()
        if image_id:
          url = f"https://pika.mangacloud.org/{manga_id}/{chapter_id}/{image_id}.{fmt}"
          image_urls.append(url)
    return image_urls
