
from sources.base.scraper import Scraper
import json
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin, quote, quote_plus
import re
from loguru import logger
from sources.base.utils import DEAULT_MSG_FORMAT
class AsuraScansWebs(Scraper):
  def __init__(self):
    super().__init__()
    self.url = "https://asuracomic.net/"
    self.bg = True
    self.sf = "as"
    self.headers = {
      "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
      "Host": "asuracomic.net",
      "Connection": "keep-alive",
      "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
    }
  async def search(self, query: str = ""):
    url = f"https://asuracomic.net/series?page=1&name={quote(query)}"
    mangas = await self.get(url, headers=self.headers)
    if not mangas:
        return []
    bs = BeautifulSoup(mangas, "html.parser")
    container = bs.find(class_="grid grid-cols-2 sm:grid-cols-2 md:grid-cols-5 gap-3 p-4")
    results = []
    if container:
      cards = container.find_all("a")
      for card in cards:
        data = {}
        data['url'] = urljoin(self.url, card.get('href').strip())
        data['poster'] = card.find_next('img').get('src').strip()
        data['type'] = card.find_next('span').text.strip()
        data['title'] = card.find_next('span', class_="block text-[13.3px] font-bold").text.strip()
        data['id'] = data['url'].split("-")[-1]
        results.append(data)
    return results
  async def get_chapters(self, data, page: int=1):
    results = data
    content = await self.get(results['url'], headers=self.headers)
    if content:
      bs = BeautifulSoup(content, "html.parser")
      des = bs.find(class_="font-medium text-sm text-[#A2A2A2]")
      des = des.text.strip() if des else "N/A"
      gen = " ".join([g.text.strip() for g in bs.find_all("button", class_="text-white hover:text-themecolor text-sm cursor-pointer rounded-[3px] px-3 py-1 bg-[#343434]")])
      results['msg'] = DEAULT_MSG_FORMAT.format(
        title=results['title'],
        status=results.get('type', "N/A"),
        genres=gen,
        summary=des[:400],
        url=results['url']
      )
      container = bs.find(class_="pl-4 pr-2 pb-4 overflow-y-auto scrollbar-thumb-themecolor scrollbar-track-transparent scrollbar-thin mr-3 max-h-[20rem] space-y-2.5")
      chapters_list = []
      if container:
        cards = container.find_all("a")
        for card in cards:
          titles_tag = card.find_next('h3')
          titles = self.chapter_title(titles_tag) if titles_tag else "N/A"
          chapters_list.append({
            "title": titles,
            "url": urljoin(self.url, card.get('href', '').strip()),
            "manga_title": results['title'],
            "poster": results.get('poster')
          })
      results['chapters'] = chapters_list
    return results
  def chapter_title(self, title):
    parts = []
    for content in title.contents:
        if content.name == 'span':
            parts.append(content.text.strip())
        elif isinstance(content, str):
            parts.append(content.strip())
    return ' '.join(parts).replace(" ", " ")
  def iter_chapters(self, data, page: int=1):
    chaps = data.get('chapters', [])
    return chaps[(page - 1) * 60:page * 60] if page != 1 else chaps
  async def get_pictures(self, url, data=None):
    response = await self.get(url, headers=self.headers)
    bs = BeautifulSoup(response, "html.parser")
    script_tags = bs.find_all('script')
    image_links = []
    for script in script_tags:
       if script.string and "self.__next_f.push" in script.string and r'\"pages\"' in script.string:
           script_content = script.string
           pattern = r'\\\"pages\\\":(\[.*?])'
           match = re.search(pattern, script_content)
           if match:
               json_string = f'{{"pages":[{match.group(1)}]}}'
               json_string = json_string.replace(r'\"', '"')
               json_data = json.loads(json_string)
               nested_pages = json_data['pages'][0]
               image_links = [page['url'] for page in nested_pages if isinstance(page, dict)]
               return image_links
  async def get_updates(self, page:int=1):
    output = []
    while page <= 3:
      url = f"https://asuracomic.net/page/{page}"
      results = await self.get(url, headers=self.headers)
      bs = BeautifulSoup(results, "html.parser")
      container = bs.find(class_="text-white mb-1 md:mb-5 mt-5")
      if container:
        cards = container.find_all(class_="grid grid-rows-1 grid-cols-12 m-2")
        if cards:
          for card in cards:
            try:
              data = {}
              a = card.find("span", class_="text-[15px] font-medium hover:text-themecolor hover:cursor-pointer").find_next("a")
              data['url'] = urljoin(self.url, a.get('href').strip())
              data['manga_title'] = a.text.strip()
              chap = card.find(class_="flex-1 inline-block mt-1")
              data['chapter_url'] = urljoin(self.url, chap.find_next("a").get('href').strip())
              data['title'] = data['chapter_url'].split("/")[-1]
              output.append(data)
            except:
              continue
      page += 1
    return output
