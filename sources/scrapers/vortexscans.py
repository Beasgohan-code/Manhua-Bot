
from sources.base.scraper import Scraper
import json, re
from bs4 import BeautifulSoup
from loguru import logger
from urllib.parse import urlparse, urljoin, quote, quote_plus
from sources.base.utils import DEAULT_MSG_FORMAT, ATSU_MSG_FORMAT
BYPASS_URL = "https://nanobridge.nanobridge-proxy.workers.dev/proxy?url={}"
IMAGES_HEADERS = {
  "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
  "Accept-Language": "en-GB,en-US;q=0.9,en;q=0.8",
  "Connection": "keep-alive",
  "Host": "storage.vexmanga.com",
  "Referer": "https://vortexscans.org/",
  "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36",
}
IMAGES_HEADERS_JSON = json.dumps(IMAGES_HEADERS)
class VortexScansWebs(Scraper):
  def __init__(self):
    super().__init__()
    self.url = "https://vortexscans.org"
    self.sf = "vts"
    self.headers = {
      "Accept": "*/*",
      "Accept-Language": "en-GB,en-US;q=0.9,en;q=0.8",
      "Connection": "keep-alive",
      "Host": "api.vortexscans.org",
      "Origin": "https://vortexscans.org",
      "Referer": "https://vortexscans.org/",
      "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:97.0) Gecko/20100101 Firefox/97.0"
    }
  async def search(self, query: str = ""):
    search_url = f"https://api.vortexscans.org/api/query?searchTerm={quote(query)}&perPage=1000"
    search_url = BYPASS_URL.format(quote_plus(search_url))
    headers_json = json.dumps(self.headers)
    search_url += "&headers=" + quote_plus(headers_json)
    data = await self.get(search_url, rjson=True)
    if not data or "posts" not in data:
      return []
    results = []
    for doc in data.get("posts", []):
      try:
        data = {}
        if doc.get("isNovel", False) is False or doc.get("seriesType", "Manga") != "NOVEL":
          data['title'] = doc['postTitle'].strip()
          data['url'] = f"https://vortexscans.org/series/{doc['slug']}"
          data['poster'] = BYPASS_URL.format(quote(doc['featuredImage']))
          data['poster'] += "&headers=" + quote(IMAGES_HEADERS_JSON)
          _type = doc.get('seriesType', None)
          _summary = doc.get('postContent', None)
          _genres = doc.get("genres", [])
          _genres = ", ".join([g.get("name", "") for g in _genres]) if _genres else None
          _alt_titles = doc.get("alternativeTitles", None)
          _status = doc.get("seriesStatus", None)
          data['msg'] = ATSU_MSG_FORMAT.format(
            title=data['title'],
            alt_title=_alt_titles if _alt_titles else 'N/A',
            genres=_genres if _genres else 'N/A',
            type=_type if _type else 'N/A',
            status=_status if _status else 'N/A',
            summary=_summary[:200] if _summary else 'N/A',
            url=data['url']
          )
          if len(data['msg']) > 1024:
            data['msg'] = DEAULT_MSG_FORMAT.format(
              title=data['title'],
              status=_status if _status else 'N/A',
              genres=_genres if _genres else 'N/A',
              summary=_summary[:200] if _summary else 'N/A',
              url=data['url']
            )
          results.append(data)
      except:
        pass
    return results
  async def get_chapters(self, data, page: int = 1):
    def clean_json(json_data):
      while True:
        if "\\" in json_data:
            json_data = json_data.replace("\\", "")
        else:
          break
      return json_data
    results = data.copy()
    headers = self.headers.copy()
    headers['Host'] = "vortexscans.org"
    url = BYPASS_URL.format(quote_plus(results['url']))
    headers_json = json.dumps(headers)
    url += "&headers=" + quote_plus(headers_json)
    HTML = await self.get(url)
    if not HTML:
      return results
    bs = BeautifulSoup(HTML, "html.parser")
    if "poster" not in results or not results['poster']:
      poster_ = bs.find(class_="relative contents")
      results['poster'] = poster_.find_next("img").get("src") if poster_ else None
    if "msg" not in results:
      tags = bs.find_all(class_="flex sm:justify-between justify-start items-center gap-2")
      status_ = None
      type_ = None
      for tag in tags:
        h1_ = tag.find("h1").text.strip() if tag.find("h1") else None
        if h1_ and h1_ == "Status":
          status_ = tag.find("p").text.strip() if tag.find("p") else None
        elif h1_ and h1_ == "Type":
          type_ = tag.find("span").text.strip() if tag.find("span") else None
      summary_ = bs.find("div", {"itemprop": "description"})
      summary_ = summary_.text.strip() if summary_ else None
      genres_ = bs.find_all("a", {"itemprop": "genre"})
      genres_ = ", ".join([g.text.strip() for g in genres_]) if genres_ else None
      results['msg'] = ATSU_MSG_FORMAT.format(
        title=data['title'],
        alt_title='N/A',
        genres=genres_ if genres_ else 'N/A',
        type=type_ if type_ else 'N/A',
        status=status_ if status_ else 'N/A',
        summary=summary_[:200] if summary_ else 'N/A',
        url=data['url']
      )
      if len(results['msg']) > 1024:
        results['msg'] = DEAULT_MSG_FORMAT.format(
          title=data['title'],
          status=status_ if status_ else 'N/A',
          genres=genres_ if genres_ else 'N/A',
          summary=summary_[:200] if summary_ else 'N/A',
          url=data['url']
        )
    try:
      chapters = bs.find("script", text=lambda x: x and r'\"mangaPost\"' in x)
      match = re.search(r'self\.__next_f\.push\((\[.*\])\)', chapters.text, re.DOTALL)
      if match:
        array_string = match.group(1)
        full_data = str(json.loads(array_string))
        pattern = r'\"chapters\"\s*:\s*(\[.*?\])(?=,\s*\"createdby\")'
        match = re.search(pattern, full_data, re.DOTALL)
        if match:
          results['chapters'] = clean_json(json.loads(json.dumps(match.group(1))))
    except:
      pass
    return results
  def iter_chapters(self, data, page: int = 1):
    chapters_list = []
    if "chapters" in data:
      try:
        for chapter in json.loads(data['chapters']):
          title = chapter.get("slug").replace("-", " ").title()
          chapters_list.append({
            "title": title,
            "url": f"{data['url']}/{chapter.get('slug')}" if not data['url'].endswith("/") else f"{data['url']}{chapter.get('slug')}",
            "manga_title": data['title'],
            "poster": data['poster'] if 'poster' in data else None
          })
      except Exception as err:
        logger.exception(f"vortexscans Error: {err}")
        return []
    return chapters_list[(page - 1)*60:page*60] if page != 1 else chapters_list
  async def get_pictures(self, url, data=None):
    headers = self.headers.copy()
    headers['Host'] = "vortexscans.org"
    url = BYPASS_URL.format(quote_plus(url))
    headers_json = json.dumps(headers)
    url += "&headers=" + quote_plus(headers_json)
    html = await self.get(url)
    if not html:
      return []
    try:
      bs = BeautifulSoup(html, "html.parser")
      images = bs.find("script", text=lambda x: x and r'\"images\":[' in x)
      match = re.search(r'self\.__next_f\.push\((\[.*\])\)', images.text, re.DOTALL)
      if match:
        array_string = match.group(1)
        full_data = str(json.loads(array_string))
        pattern = r'\"images\"\s*:\s*(\[.*?\])(?=,\s*\"nextChapter\":)'
        match = re.search(pattern, full_data, re.DOTALL)
        if match:
          images_json = json.loads(match.group(1))
          return [
            images["url"]
            for images in images_json
          ]
    except:
      return []
