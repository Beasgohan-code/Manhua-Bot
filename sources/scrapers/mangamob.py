
from sources.base.scraper import Scraper
import json
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin, quote, quote_plus
import re
from loguru import logger
from sources.base.utils import DEAULT_MSG_FORMAT
class MangaMobWebs(Scraper):
  def __init__(self):
    super().__init__()
    self.url = "https://www.mangamob.com/"
    self.bg = None
    self.sf = "mm"
    self.image_cdn = "https://cdn.mangageko.com/avatar/288x412"
    self.headers = {
      "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
      "accept-language": "en-GB,en-US;q=0.9,en;q=0.8",
      "connection": "keep-alive",
      "host": "www.mangamob.com",
      "sec-fetch-user": "?1",
      "upgrade-insecure-requests": "1",
      "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36"
    }
  def get_manga_id(self, page, data):
    bs = BeautifulSoup(page, "html.parser")
    script_tags = bs.find_all("script")
    for script in script_tags:
        if script.string:
            match = re.search(r"manga_id:\s*(\d+)", script.string)
            if match:
              data['id'] = match.group(1)
    return None
  def get_information(self, page, data):
    bs = BeautifulSoup(page, "html.parser")
    des = bs.find(class_="description").text.strip() if bs.find(class_="description") else "N/A"
    gen = bs.find(class_="genres").find_all("a") if bs.find(class_="genres") else None
    gens = " ".join([g.text.replace("\n", "") for g in gen]) if gen else "N/A"
    status_ = bs.find('span', string='Status:')
    status = status_.find_next_sibling('span').text if status_ else "N/A"
    data['msg'] = DEAULT_MSG_FORMAT.format(
      title=data['title'],
      status=status,
      genres=gens,
      summary=des[:200],
      url=data['url']
    )
  async def search(self, query: str = ""):
    query = quote(query)
    request_url = f'https://www.mangamob.com/browse-comics/?search={query}'
    page = await self.get(request_url, headers=self.headers)
    bs = BeautifulSoup(page, "html.parser")
    cards = bs.find_all('div', class_='item item-spc')
    results = []
    for card in cards:
        a_tag = card.find('a')
        if a_tag is not None:
          name = a_tag.find("img").get('alt').strip()
          url = urljoin(self.url, a_tag.get('href').strip())
          img_tag = card.find("img")
          image =(
            img_tag.get('src').strip()) if img_tag else None
          results.append({"title": name, "url": url, "poster": image})
    return results
  async def get_chapters(self, data, page: int = 1):
    results = data
    content = await self.get(data['url'], headers=self.headers)
    self.get_manga_id(content, results)
    self.get_information(content, results)
    if not "id" in results:
        return []
    data_1 = await self.get(f"https://www.mangamob.com/get/chapters/?manga_id={results['id']}", rjson=True, headers=self.headers)
    results['chapters'] = data_1['chapters']
    return results
  def iter_chapters(self, data, page: int = 1):
    chapters_list = []
    for chapter in data['chapters']:
      text = chapter.get("chapter_number", None)
      slug = chapter.get("chapter_slug", None)
      if text and slug:
        chapters_list.append({
          "title": text.replace("-eng-li", ""),
          "url": f"https://www.mangamob.com/chapter/en/{slug}",
          "slug": slug,
          "manga_title": data['title'],
          "poster": data['poster'] if 'poster' in data else None,
        })
    return chapters_list[(page - 1) * 60:page * 60] if page != 1 else chapters_list
  async def get_pictures(self, url, data=None):
    content = await self.get(url, headers=self.headers)
    bs = BeautifulSoup(content, "html.parser")
    chapter_reader_div = bs.find("div", {"id": "chapter-images"})
    image_items = chapter_reader_div.find_all("img") if chapter_reader_div else []
    images_url = [image_item.get("data-src") for image_item in image_items]
    return images_url[:-1]
  async def get_updates(self, page:int=1):
    urls = []
    while page <= 3:
      url = f"https://www.mangamob.com/browse-comics/?results={page}&filter=Updated"
      content = await self.get(url, headers=self.headers)
      bs = BeautifulSoup(content, "html.parser")
      container = bs.find("div", {"class": "mls-wrap"})
      items = container.find_all("div", {"class": "manga-detail"})
      for item in items:
        data = {}
        manga_url = urljoin(self.url, item.find('a').get('href'))
        chapter = item.find("div", {"class": "chapter"})
        data['chapter_url'] = f'{self.url}{chapter.find("a").get("href")}/'
        data['title'] = (chapter.find("a").text.strip()).replace("\n", "")
        data['manga_title'] = item.find_next("a").get("title", "N/A")
        data['url'] = manga_url
        urls.append(data)
      page += 1
    return urls
