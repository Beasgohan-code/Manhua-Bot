
from sources.base.scraper import Scraper
import json
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin, quote, quote_plus, urlencode
import re
from loguru import logger
from sources.base.utils import DEAULT_MSG_FORMAT, BALL_MSG_FORMAT
LANGUAGE_FLAGS = {
  "ar": {"lang": "Arabic"},
  "bg": {"lang": "Bulgarian"},
  "bn": {"lang": "Bengali"},
  "ca": {"lang": "Catalan"},
  "ca-ad": {"lang": "Catalan (Andorra)"},
  "ca-es": {"lang": "Catalan (Spain)"},
  "ca-fr": {"lang": "Catalan (France)"},
  "ca-it": {"lang": "Catalan (Italy)"},
  "ca-pt": {"lang": "Catalan (Portugal)"},
  "cn": {"lang": "Chinese"},
  "cs": {"lang": "Czech"},
  "da": {"lang": "Danish"},
  "de": {"lang": "German"},
  "el": {"lang": "Greek"},
  "en": {"lang": "English"},
  "es": {"lang": "Spanish"},
  "es-ar": {"lang": "Spanish (Argentina)"},
  "es-mx": {"lang": "Spanish (Mexico)"},
  "es-es": {"lang": "Spanish (Spain)"},
  "es-la": {"lang": "Spanish (Latin America)"},
  "es-419": {"lang": "Spanish (Latin America)"},
  "fa": {"lang": "Persian"},
  "fi": {"lang": "Finnish"},
  "fr": {"lang": "French"},
  "he": {"lang": "Hebrew"},
  "hi": {"lang": "Hindi"},
  "hu": {"lang": "Hungarian"},
  "id": {"lang": "Indonesian"},
  "it": {"lang": "Italian"},
  "it-it": {"lang": "Italian (Italy)"},
  "ja": {"lang": "Japanese"},
  "jp": {"lang": "Japanese (Japan)"},
  "ko": {"lang": "Korean"},
  "kr": {"lang": "Korean"},
  "ml": {"lang": "Malayalam"},
  "ms": {"lang": "Malay"},
  "ne": {"lang": "Nepali"},
  "nl": {"lang": "Dutch"},
  "nl-be": {"lang": "Dutch (Belgium)"},
  "no": {"lang": "Norwegian"},
  "pl": {"lang": "Polish"},
  "pt-br": {"lang": "Portuguese (Brazil)"},
  "pt-pt": {"lang": "Portuguese (Portugal)"},
  "ro": {"lang": "Romanian"},
  "ru": {"lang": "Russian"},
  "sk": {"lang": "Slovak"},
  "sl": {"lang": "Slovenian"},
  "sq": {"lang": "Albanian"},
  "sr": {"lang": "Serbian"},
  "sr-cyrl": {"lang": "Serbian (Cyrillic)"},
  "sv": {"lang": "Swedish"},
  "ta": {"lang": "Tamil"},
  "th": {"lang": "Thai"},
  "th-hk": {"lang": "Thai (Hong Kong)"},
  "th-kh": {"lang": "Thai (Cambodia)"},
  "th-la": {"lang": "Thai (Laos)"},
  "th-my": {"lang": "Thai (Malaysia)"},
  "th-sg": {"lang": "Thai (Singapore)"},
  "tr": {"lang": "Turkish"},
  "uk": {"lang": "Ukrainian"},
  "vi": {"lang": "Vietnamese"},
  "zh": {"lang": "Chinese"},
  "zh-cn": {"lang": "Chinese (Simplified)"},
  "zh-hk": {"lang": "Chinese (Hong Kong)"},
  "zh-mo": {"lang": "Chinese (Macau)"},
  "zh-sg": {"lang": "Chinese (Singapore)"},
  "zh-tw": {"lang": "Chinese (Taiwan)"},
}
def get_language_name(short):
  return LANGUAGE_FLAGS.get(short, {}).get("lang", short)
class MangaBallWebs(Scraper):
  def __init__(self):
    super().__init__()
    self.url = "https://mangaball.net/"
    self.sf = "MBL"
    self.session = self.session
  async def fetch_csrf_token(self):
    html = await self.get(self.url, headers={
        "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Mobile Safari/537.36"
    })
    if not html:
        return None
    soup = BeautifulSoup(html, "html.parser")
    tag = soup.find("meta", {"name": "csrf-token"})
    if tag:
        return tag["content"]
    input_ = soup.find("input", {"name": "_token"})
    if input_ and "value" in input_.attrs:
        return input_["value"]
    return None
  async def search(self, query: str = ""):
    results = []
    csrf_token = await self.fetch_csrf_token()
    if not csrf_token:
        return []
    url = urljoin(self.url, "api/v1/smart-search/search/")
    payload = {"search_input": query}
    headers = {
        'Accept': '*/*',
        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'User-Agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Mobile Safari/537.36',
        'Origin': self.url.rstrip("/"),
        'Referer': self.url,
        'X-Csrf-Token': csrf_token,
        'X-Requested-With': 'XMLHttpRequest',
    }
    try:
      data = await self.post(url, data=payload, headers=headers, rjson=True)
      if data and data.get("data"):
        for entry in data.get("data", {}).get("manga", []):
          mtitle = entry.get("title", "").strip()
          murl = entry.get("url", "")
          if murl.startswith("/"):
              murl = urljoin(self.url, murl.lstrip("/"))
          else:
              murl = urljoin(self.url, murl)
          thumb = entry.get("img", "")
          results.append({
              "title": mtitle,
              "url": murl,
              "poster": thumb
          })
    except Exception as e:
      logger.exception(f"MangaBall Error: {e}")
    finally:
      return results
  async def get_chapters(self, data, page: int=1):
    results = data.copy()
    try:
      html = await self.get(results['url'], headers={
        "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Mobile Safari/537.36"
      })
      if not html:
          return results
      soup = BeautifulSoup(html, "html.parser")
      title_tag = soup.find("h4", class_="comic-title")
      results['title'] = title_tag.text.strip() if title_tag else results['title']
      alt_titles = []
      alt_box = soup.find("div", class_="alternate-name-container")
      if alt_box:
        alt_titles = [span.text.strip() for span in alt_box.find_all("span", class_="badge")]
      alt_titles = ", ".join(alt_titles[:3]) if alt_titles else "N/A"
      desc_box = soup.find("div", class_="description-text")
      summary = ""
      if desc_box:
        p = desc_box.find("p")
        if p and p.text.strip():
            summary = p.text.strip()
        else:
            summary = desc_box.get_text(separator="\n", strip=True)
      if not summary:
        meta_desc = soup.find("meta", {"name": "description"})
        summary = meta_desc["content"].strip() if (meta_desc and "content" in meta_desc.attrs) else "N/A"
      if "poster" not in results or not results['poster']:
        meta_img = soup.find("meta", {"property": "og:image"})
        if meta_img and "content" in meta_img.attrs:
          results['poster'] = meta_img["content"]
      status = "N/A"
      for badge in soup.find_all("span", class_="badge"):
        badge_text = badge.get_text(strip=True).lower()
        if badge_text in ("ongoing", "completed", "hiatus"):
            status = badge_text.capitalize()
            break
      year = "N/A"
      badges = soup.find_all("span", class_="badge bg-info bg-opacity-75")
      for badge in badges:
        if "Year:" in badge.get_text():
            year = badge.get_text().split("Year:")[-1].strip()
            break
      genres = []
      raw_genres = []
      for row in soup.find_all("div", class_="d-flex flex-wrap gap-2 mb-3 align-items-center"):
        badges = row.find_all("span", class_="badge")
        if badges and badges[0].get_text(strip=True).lower().startswith("tags"):
            raw_genres = [span.get_text(strip=True) for span in badges[1:]]
            break
      demographic_types = {
        "Manga", "Manhwa", "Manhua", "Webtoon", "Comic",
        "Shounen", "Shoujo", "Seinen", "Josei",
        "Isekai", "Reincarnation", "Transmigration", "Regression",
        "Villainess", "Otome Game",
        "School Life", "Office Life", "Survival",
        "Post-Apocalyptic", "Tragedy",
        "Philosophical", "Supernatural", "Magic", "Martial Arts",
        "Historical", "Military", "Sports", "Music", "Cooking",
        "Medical", "Detective", "Crime", "Dystopian", "Gore",
        "Thriller", "Mature", "Adult",
        "Cyberpunk", "Steampunk", "Vampires", "Zombies",
        "Idol", "Mecha", "Demons", "Angels", "Ghosts",
        "Villain Protagonist", "Anti-Hero", "Revenge",
        "Time Travel", "Parallel World", "Cultivation",
        "Family", "Friendship", "Adventure", "Magic School",
        "Royalty", "Political", "Slice of Life Comedy", "Comedy Drama",
        "Sexual Violence", "Office Workers", "Long Strip", "Full Color",
      }
      genres = [g for g in raw_genres if g not in demographic_types]
      genres = ", ".join(genres) if genres else "Unknown"
      rating = "N/A"
      for item in soup.find_all("div", class_="highlight-item"):
        i_tag = item.find("i", class_="fa-star")
        if i_tag:
            value = item.find("span", class_="text-light")
            if value:
                rating = value.text.strip()
            break
      results['msg'] = BALL_MSG_FORMAT.format(
        title=results['title'],
        alt_title=alt_titles if alt_titles else "N/A",
        status=status if status else "N/A",
        genres=genres if genres else 'N/A',
        rating=rating if rating else 'N/A',
        year=year if year else 'N/A',
        summary=summary[:200] if summary else 'N/A',
        url=results['url'],
      )
      if len(results['msg']) > 1024:
        results['msg'] = DEAULT_MSG_FORMAT.format(
          title=results['title'],
          status=status if status else "N/A",
          genres=genres if genres else 'N/A',
          summary=summary[:200] if summary else 'N/A',
          url=results['url']
        )
      manga_id = None
      parts = results['url'].rstrip("/").split("-")
      if parts and re.match(r"^[0-9a-f]{24}$", parts[-1]):
        manga_id = parts[-1]
      else:
        manga_id = results['url'].rstrip("/").split("/")[-1].split("-")[-1]
      results['chapters'] = await self._get_chapters(manga_id)
    except Exception as e:
      logger.exception(f"MangaBall Chapters Error: {e}")
    finally:
      return results
  def extract_chapter_num(self, chapter_title):
    m = re.match(r"([0-9]+(?:\.[0-9]+)?)", chapter_title)
    if m:
        try:
            return float(m.group(1))
        except Exception:
            return None
    return None
  async def _get_chapters(self, manga_id):
    csrf_token = await self.fetch_csrf_token()
    if not csrf_token:
        return {}
    url = urljoin(self.url, "api/v1/chapter/chapter-listing-by-title-id/")
    payload = {"title_id": manga_id}
    headers = {
        'Accept': '*/*',
        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'User-Agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Mobile Safari/537.36',
        'Origin': self.url.rstrip("/"),
        'Referer': self.url,
        'X-Csrf-Token': csrf_token,
        'X-Requested-With': 'XMLHttpRequest',
    }
    data = await self.post(url, data=payload, headers=headers, rjson=True)
    if not data:
        return {}
    all_chapters = data.get("ALL_CHAPTERS", [])
    results = []
    for chapter in all_chapters:
        chap_num = chapter.get("number") or "Chapter"
        title = chapter.get("title") or ""
        translations = chapter.get("translations", [])
        for t in translations:
            lang_short = t.get("language", "")
            lang_full = get_language_name(lang_short)
            if lang_full == "English":
              url = t.get("url", "")
              chap_title = f"{chap_num}{' - '+title if title else ''}"
              results.append((chap_title, url))
    return results
  def iter_chapters(self, data, page: int=1):
    chapters_list = []
    if 'chapters' in data:
      try:
        for card in data['chapters']:
          chapters_list.append({
            "title": card[0],
            "url": card[1],
            "manga_title": data['title'],
            "poster": data['poster'] if 'poster' in data else None,
          })
      except Exception as err:
        logger.exception(f"MangaBall Error: {err}")
    return chapters_list[(page - 1) * 60:page * 60] if page != 1 else chapters_list
  async def get_pictures(self, url, data=None):
    html = await self.get(url, headers={
      "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Mobile Safari/537.36"
    })
    if not html:
        return []
    m = re.search(r'const chapterImages = JSON\.parse\(`([^`]*)`', html)
    if not m:
      return []
    imglist = json.loads(m.group(1))
    return imglist
