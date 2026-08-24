
from sources.base.scraper import Scraper
import json
import re
from bs4 import BeautifulSoup
from loguru import logger
from sources.base.utils import DEAULT_MSG_FORMAT
class ComickWebs(Scraper):
  PREFERRED_SCANLATOR_SLUGS = [
      "official",
      "utoon",
      "templescan",
      "lunatoon",
      "magusmanga",
      "asura",
      "asurascan",
      "violetscan",
      "luacomic"
  ]
  def __init__(self):
    super().__init__()
    self.url = "https://comix.to"
    self.bg = None
    self.sf = "ck"
    self.headers = {
        "Accept": "application/json",
        "Referer": "https://comix.to",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    }
  async def search(self, query: str = ""):
    url = "https://comix.to/api/v2/manga"
    params = {
        "keyword": query,
        "order[relevance]": "desc",
        "limit": 24
    }
    data = await self.get(url, params=params, rjson=True, headers=self.headers)
    if not data:
      return []
    items = data.get("result", {}).get("items", [])
    results = []
    for item in items:
      manga_id = item.get("manga_id") or item.get("hash_id")
      manga_url = f"https://comix.to/title/{item.get('hash_id', manga_id)}-{item.get('slug', '')}"
      thumbnail = item.get("poster", {}).get("large", "")
      results.append({
          "title": item.get("title", ""),
          "url": manga_url,
          "poster": thumbnail,
          "manga_id": manga_id,
          "slug": item.get("slug", "")
      })
    return results
  def select_preferred_chapters(self, chapters_raw):
    chapters_by_number = {}
    for chap in chapters_raw:
      chap_num = chap.get("number")
      if chap_num is None:
        continue
      try:
        num_float = float(chap_num)
        if num_float <= 0:
          logger.debug(f"Skipping invalid chapter {num_float} from Comix (zero or negative)")
          continue
        if num_float > 100000:
          logger.warning(f"Skipping unrealistic chapter number {num_float} from Comix (likely corrupted data)")
          continue
      except (ValueError, TypeError):
        logger.debug(f"Skipping non-numeric chapter {chap_num} from Comix")
        continue
      chapters_by_number.setdefault(chap_num, []).append(chap)
    selected = []
    for chap_num, group in chapters_by_number.items():
      found = None
      best_priority = len(self.PREFERRED_SCANLATOR_SLUGS)
      for chap in group:
        scan_group = chap.get("scanlation_group") or {}
        slug = (scan_group.get("slug") or "").lower()
        if slug in self.PREFERRED_SCANLATOR_SLUGS:
          priority = self.PREFERRED_SCANLATOR_SLUGS.index(slug)
          if (found is None) or (priority < best_priority):
            found = chap
            best_priority = priority
      if found:
        selected.append(found)
      else:
        selected.append(group[0])
    try:
      sorted_chapters = sorted(selected, key=lambda c: float(c.get("number", 0)), reverse=True)
      seen_nums = set()
      deduped = []
      for chap in sorted_chapters:
        chap_num = float(chap.get("number", 0))
        if chap_num not in seen_nums:
          seen_nums.add(chap_num)
          deduped.append(chap)
      return deduped
    except Exception:
      return selected
  async def get_chapters(self, data, page: int = 1):
    results = data.copy()
    manga_url = results.get('url', '')
    m = re.search(r'/title/([a-z0-9]+)-([a-z0-9\-]+)', manga_url, re.IGNORECASE)
    manga_id = m.group(1) if m else None
    slug = m.group(2) if m else None
    if not manga_id:
      logger.error(f"Cannot extract manga_id from url: {manga_url}")
      return results
    results['manga_id'] = manga_id
    results['slug'] = slug
    try:
      html = await self.get(manga_url, headers=self.headers)
      if html:
        soup = BeautifulSoup(html, "html.parser")
        title_tag = soup.select_one("h1.title")
        if title_tag:
          results['title'] = title_tag.text.strip()
        cover_tag = soup.select_one(".poster img")
        if cover_tag and cover_tag.has_attr("src"):
          results['poster'] = cover_tag["src"]
        desc_div = soup.select_one(".description .content")
        summary = desc_div.get_text(separator="\n", strip=True) if desc_div else "N/A"
        author = "Unknown"
        genres = []
        status = "Unknown"
        year = "?"
        original_language = "Unknown"
        raw = soup.select("#metadata li")
        for li in raw:
          txt = li.get_text(" ").lower()
          if "authors" in txt:
            a = li.select_one("a")
            if a:
              author = a.text.strip()
          if "genres" in txt:
            genres_a = li.select("a")
            genres = [a.text.strip() for a in genres_a if a.text.strip()]
          if "original language" in txt:
            span = li.select_one("span")
            if span:
              original_language = span.text.strip()
        year_tag = soup.select_one("span.status")
        if year_tag:
          bits = year_tag.text.strip().split()
          if len(bits) > 1:
            year = bits[0]
            status = bits[1].capitalize()
        type_map = {"ko": "Manhwa", "jp": "Manga", "cn": "Manhua"}
        mtype = type_map.get(original_language.lower(), "Comic")
        genres_str = ", ".join(genres) if genres else "N/A"
        results['msg'] = DEAULT_MSG_FORMAT.format(
          title=results.get('title', 'Unknown'),
          status=status,
          genres=genres_str,
          summary=summary[:200] if summary else "N/A",
          url=manga_url
        )
    except Exception as e:
      logger.error(f"Comix get_info error: {e}")
    all_chapters_raw = []
    api_page = 1
    while True:
      chapter_api = f"https://comix.to/api/v2/manga/{manga_id}/chapters?order[number]=desc&limit=100&page={api_page}"
      try:
        chapter_json = await self.get(chapter_api, rjson=True, headers=self.headers)
        if not chapter_json:
          break
        items = chapter_json.get("result", {}).get("items", [])
        if not items:
          break
        all_chapters_raw.extend(items)
        pag = chapter_json.get("result", {}).get("pagination", {})
        if pag and pag.get("current_page", 1) < pag.get("last_page", 1):
          api_page += 1
        else:
          break
      except Exception as e:
        logger.error(f"Comix chapters API error: {e}")
        break
    preferred_chapters = self.select_preferred_chapters(all_chapters_raw)
    chapters = []
    for chap in preferred_chapters:
      chap_num = chap.get("number")
      chap_id = chap.get("chapter_id")
      scan_group = chap.get("scanlation_group") or {}
      scanlator = scan_group.get("name") or "No Group"
      chap_title = f"Chapter {chap_num}"
      chapter_url = f"https://comix.to/title/{manga_id}-{slug}/{chap_id}-chapter-{chap_num}"
      chapters.append((chap_title, chapter_url, chap_id, scanlator))
    results['chapters'] = chapters
    return results
  def iter_chapters(self, data, page=1):
    if isinstance(data, list):
      data = {'chapters': data, 'title': 'Unknown', 'poster': None}
    if not data or 'chapters' not in data:
      return []
    if not data.get('chapters'):
      return []
    manga_title = data.get('title', 'Unknown') if isinstance(data, dict) else 'Unknown'
    poster = data.get('poster') if isinstance(data, dict) else None
    chapters_list = []
    for chapter in data['chapters']:
      try:
        if isinstance(chapter, list):
          if len(chapter) > 0:
            chapter = chapter[0] if isinstance(chapter[0], dict) else {'title': str(chapter[0]), 'url': str(chapter[1]) if len(chapter) > 1 else ''}
          else:
            continue
        if isinstance(chapter, tuple):
          chap_title, chapter_url = chapter[0], chapter[1]
          chap_id = chapter[2] if len(chapter) > 2 else None
          scanlator = chapter[3] if len(chapter) > 3 else None
        elif isinstance(chapter, dict):
          chap_title = chapter.get("title", "Unknown")
          chapter_url = chapter.get("url", "")
          chap_id = chapter.get("chapter_id")
          scanlator = chapter.get("scanlator")
        else:
          continue
        title = f"{chap_title} ({scanlator})" if scanlator else chap_title
        chapters_list.append({
            "title": title,
            "url": chapter_url,
            "chapter_id": chap_id,
            "manga_title": manga_title,
            "poster": poster,
        })
      except Exception as e:
        logger.error(f"Comix iter_chapters error: {e}")
        continue
    return chapters_list
  async def get_pictures(self, url, data=None):
    try:
      m = re.search(r'/(\d+)-chapter', url)
      chap_id = m.group(1) if m else None
      if not chap_id:
        logger.error(f"Cannot extract chapter_id from url: {url}")
        return []
      api_url = f"https://comix.to/api/v2/chapters/{chap_id}"
      response = await self.get(api_url, rjson=True, headers=self.headers)
      if not response:
        return []
      images = response.get("result", {}).get("images", [])
      urls = [img.get("url") for img in images if img.get("url")]
      return urls
    except Exception as e:
      logger.error(f"Comix get_pictures error: {e}")
      return []
  async def get_updates(self, page: int = 1):
    return []
