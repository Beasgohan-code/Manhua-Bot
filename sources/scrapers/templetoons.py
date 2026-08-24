
from sources.base.scraper import Scraper
import json
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin, quote, quote_plus
import re
from loguru import logger
from sources.base.utils import DEAULT_MSG_FORMAT
class TempleToonsWebs(Scraper):
  def __init__(self):
    super().__init__()
    self.url = "https://templetoons.com/"
    self.api_url = "https://api.templetoons.com/api/allComics"
    self.bg = None
    self.sf = "tt1"
    self.headers = {
      "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36",
    }
  async def search(self, query: str = ""):
    results = []
    mangas = await self.get(self.api_url, cs=True, rjson=True)
    if mangas:
      for card in mangas:
        if query.lower() in card['title'].lower():
          data = {}
          data['title'] = card["title"]
          data['poster'] = card['thumbnail']
          data['url'] = f"https://templetoons.com/comic/{card['series_slug']}"
          results.append(data)
    return results
  async def get_chapters(self, data, page: int=1):
    results = data
    content = await self.get(results['url'], cs=True)
    bs = BeautifulSoup(content, "html.parser") if content else None
    if bs:
      con = bs.find(class_="px-5 py-7 rounded-b-xl text-white/90 shadow-red-400 shadow-md bg-black/50")
      desc = con.find_next("p", class_="text-xs md:text-sm lg:text-normal") if con else None
      desc = desc.text if desc else "N/A"
      pattern = r"Status:\s+([^\n]+)"
      status_container = con.find(class_="grid grid-cols-2 lg:grid-cols-3 gap-2 text-xs md:text-sm lg:text-normal") if con else None
      try:
        status_matches = next((re.findall(pattern, status.text)[0] for status in status_container if re.findall(pattern, status.text)), "N/A")
      except:
        status_matches = "N/A"
      genres = con.find(class_="flex flex-row flex-wrap gap-2 text-xs md:text-sm lg:text-normal mt-2")
      if genres.find_next("p"):
        genres = genres.find_all("p")
        genres = ", ".join([genre.text.strip() for genre in genres]) if genres else "N/A"
      else:
        genres = "N/A"
      results['msg'] = DEAULT_MSG_FORMAT.format(
        title=results['title'],
        status=status_matches if status_matches else "N/A",
        summary=desc[:200],
        genres=genres,
        url=results['url']
      )
      chapter_tags = bs.find_all(
        "a", class_="col-span-full sm:col-span-3 lg:col-span-2 flex flex-row gap-2 bg-[#131212] rounded-lg h-[90px] overflow-hidden"
      )
      chapters_list = []
      for card in chapter_tags:
        try:
          chapter_slug = card["href"].strip("/").split("/")[-1]
          title_tag = card.find("h1", class_="text-sm md:text-normal")
          chapters_list.append({
            "title": title_tag.text.strip() if title_tag else "Unknown",
            "url": chapter_slug,
          })
        except:
          continue
      results['chapters'] = chapters_list
    return results
  def iter_chapters(self, data, page: int=1):
    chapters_list = []
    if not data or 'chapters' not in data or not data['chapters']:
      return []
    url = data.get('url', '').split("/")[-1]
    for card in data['chapters']:
      try:
        if isinstance(card, dict):
          chapter_slug = card.get('url', '')
          title = card.get('title', 'Unknown')
        else:
          chapter_slug = card["href"].strip("/").split("/")[-1] if hasattr(card, '__getitem__') else ''
          title_tag = card.find("h1", class_="text-sm md:text-normal") if hasattr(card, 'find') else None
          title = title_tag.text.strip() if title_tag else "Unknown"
        chapters_list.append({
            "title": title,
            "url": f"{self.url}/comic/{url}/{chapter_slug}",
            "manga_title": data.get('title', 'Unknown'),
            "poster": data.get('poster'),
        })
      except:
        continue
    return chapters_list[(page - 1) * 60:page * 60] if page != 1 else chapters_list
  async def get_pictures(self, url, data=None):
    images_urls = []
    try:
      data = await self.get(url, cs=True)
      bs = BeautifulSoup(data, 'html.parser')
      imgs_tags = bs.find("script", string=lambda text: "images" in text)
      imgs_dump = json.dumps(imgs_tags.text.strip())
      while True:
        imgs_dump = imgs_dump.replace('\n', ' ')
        imgs_dump = imgs_dump.replace('\\', ' ')
        imgs_dump = imgs_dump.replace('"self.__next_f.push(', ' ')
        imgs_dump = imgs_dump.replace(')"', ' ')
        imgs_dump = imgs_dump.replace(' ', '')
        if '\\' not in imgs_dump:
          break
      imgs_dump = json.dumps(imgs_dump)
      pattern = r'https?://[^\s"]+\.jpg'
      image_links = re.findall(pattern, imgs_dump)
      for images_link in image_links:
        img_len = images_link.split('/')
        if len(img_len) > 8:
          images_urls.append(images_link)
    except Exception as e:
      logger.exception(f"Error processing images: {e}")
    return images_urls
  async def get_updates(self, page:int=1):
    output = []
    results = await self.get(self.api_url, cs=True, rjson=True)
    if results:
      for data in results:
        try:
          rdata = {}
          rdata['url'] = f'https://templetoons.com/comic/{data["series_slug"]}'
          rdata['manga_title'] = data['title']
          rdata['chapter_url'] = f'https://templetoons.com/comic/{data["series_slug"]}/{data["Chapter"][0]["chapter_slug"]}'
          rdata['title'] = data['Chapter'][0]['chapter_name']
          rdata['poster'] = data['thumbnail']
          output.append(rdata)
        except:
          continue
    return output
