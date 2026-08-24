
from sources.base.scraper import Scraper
import json
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin, quote, quote_plus
import re
from loguru import logger
from sources.base.utils import DEAULT_MSG_FORMAT
class MgekoWebs(Scraper):
  def __init__(self):
    super().__init__()
    self.url = "https://www.mgeko.cc/"
    self.bg = None
    self.sf = "mgeko"
    self.headers = {
      "accept": "*/*",
      "accept-language": "en-GB,en-US;q=0.9,en;q=0.8",
      "connection": "keep-alive",
      "host": "www.mgeko.cc",
      "referer": "https://www.mgeko.cc/",
      "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36",
    }
  async def search(self, query: str = ""):
    url = f"https://www.mgeko.cc/autocomplete?term={quote_plus(query)}"
    mangas = await self.get(url, headers=self.headers)
    bs = BeautifulSoup(mangas, "html.parser") if mangas else None
    cards = bs.find_all("li") if bs else None
    results = []
    if cards:
      for card in cards:
        try:
          data = {}
          data['title'] = card.find_next("a")['title']
          data['poster'] = card.find_next("img")['src']
          data['url'] = urljoin(self.url, card.find_next("a")['href'])
          results.append(data)
        except:
          continue
    return results
  async def get_chapters(self, data, page: int=1):
    results = data
    content = await self.get(results['url'], cs=True)
    bs = BeautifulSoup(content, "html.parser") if content else None
    if bs:
      con = bs.find(class_="categories")
      if con:
        gen = ' '.join([con.text.strip() for con in con.find_all("a")])
        des = bs.find("p", class_="description").text.strip() if bs.find("p", class_="description") else "N/A"
        results['msg'] = DEAULT_MSG_FORMAT.format(
          title=results['title'],
          status="N/A",
          genres=gen,
          summary=des[:200],
          url=results['url']
        )
    chapters_url = f"{results['url']}all-chapters/"
    chapters_html = await self.get(chapters_url, headers=self.headers)
    chapters_list = []
    if chapters_html:
      bs = BeautifulSoup(chapters_html, "html.parser")
      ul = bs.find('div', {'id': 'chpagedlist'}) if bs else None
      lis = ul.find_all('li') if ul else None
      if lis:
        for card in lis:
          a_tag = card.find_next("a")
          if a_tag:
            chapter_slug = a_tag.get('title', '')
            chapter_search = re.search(r"chapter-([\d]+(?:\.[\d]+)?)\-([\w-]+)", chapter_slug)
            chapter_text = f"{chapter_search.group(1)}-{chapter_search.group(2)}" if chapter_search else chapter_slug
            chapters_list.append({
              "title": chapter_text,
              "url": urljoin(self.url, a_tag.get('href', ''))
            })
    results['chapters'] = chapters_list
    return results
  def iter_chapters(self, data, page: int=1):
    chapters_list = []
    if not data or 'chapters' not in data:
      return []
    for card in data['chapters']:
      if isinstance(card, str):
        try:
          bs = BeautifulSoup(data['chapters'], "html.parser")
          ul = bs.find('div', {'id': 'chpagedlist'}) if bs else None
          lis = ul.find_all('li') if ul else None
          if lis:
            for li in lis:
              a_tag = li.find_next("a")
              if a_tag:
                chapter_slug = a_tag.get('title', '')
                chapter_search = re.search(r"chapter-([\d]+(?:\.[\d]+)?)\-([\w-]+)", chapter_slug)
                chapter_text = f"{chapter_search.group(1)}-{chapter_search.group(2)}" if chapter_search else chapter_slug
                chapters_list.append({
                  "title": chapter_text,
                  "url": urljoin(self.url, a_tag.get('href', '')),
                  "manga_title": data['title'],
                  "poster": data.get('poster'),
                })
        except:
          pass
        break
      else:
        chapters_list.append({
          "title": card.get("title", ""),
          "url": card.get("url", ""),
          "manga_title": data['title'],
          "poster": data.get('poster'),
        })
    return chapters_list[(page - 1) * 60:page * 60] if page != 1 else chapters_list
  async def get_pictures(self, url, data=None):
    content = await self.get(url, headers=self.headers)
    bs = BeautifulSoup(content, "html.parser") if content else None
    ul = bs.find("div", {"id": "chapter-reader"}) if bs else None
    images = ul.find_all('img') if ul else None
    images_url = [quote(img.get('src'), safe=':/%') for img in images] if images else []
    return images_url
  async def get_updates(self, page:int=1):
    output = []
    while page < 4:
      url = f"https://www.mgeko.cc/jumbo/manga/?results={page}&filter=All"
      try: content = await self.get(url, cs=True, headers=self.headers)
      except: content = None
      if content:
        bs = BeautifulSoup(content, "html.parser")
        lis = bs.find_all('li', class_='novel-item')
        if lis:
          for card in lis:
            try:
              rdata = card.find_next("a")
              data = {}
              data['url'] = urljoin(self.url, rdata['href'])
              data['manga_title'] = rdata.find_next("h4").text.strip()
              data['poster'] = card.find_next("img")['data-src']
              chapter_title = rdata.find_next("h5").text.strip()
              chapter_search = re.search(r"chapter-([\d]+(?:\.[\d]+)?)\-([\w-]+)", chapter_title)
              chapter_text = f"{chapter_search.group(1)}-{chapter_search.group(2)}" if chapter_search else chapter_title
              chapter_url = f"{data['url']}all-chapters/"
              content = await self.get(chapter_url, headers=self.headers)
              bs = BeautifulSoup(content, "html.parser")
              ul = bs.find('div', {'id': 'chpagedlist'})
              lis = ul.find('li')
              chapter_url = urljoin(self.url, lis.find_next("a")['href'])
              data['chapter_url'] = chapter_url
              data['title'] = chapter_text
              output.append(data)
            except:
              continue
      page += 1
    return output
