
from sources.base.scraper import Scraper
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin, quote, quote_plus
from loguru import logger
from sources.base.utils import ALL_MSG_FORMAT, DEAULT_MSG_FORMAT
import re, json
class AllMangaWebs(Scraper):
  def __init__(self):
    super().__init__()
    self.url = "https://allmanga.to/"
    self.api_url = "https://api.allanime.day/api"
    self.sf = "alm"
    self.headers = {
        'authority': 'api.allanime.day',
        'scheme': 'https',
        'Accept': 'application/json',
        'Accept-Language': 'en-US,en;q=0.9',
        'access-control-allow-origin': '*',
        'Origin': 'https://allanime.to',
        'Referer': 'https://allanime.to/',
        'sec-ch-ua': '"Not_A Brand";v="99", "Google Chrome";v="109", "Chromium";v="109"',
        'sec-ch-ua-mobile': '?1',
        'sec-ch-ua-platform': '"Android"',
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'cross-site',
        'User-Agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Mobile Safari/537.36'
    }
    self.SEARCH_HASH = "a27e57ef5de5bae714db701fb7b5cf57e13d57938fc6256f7d5c70a975d11f3d"
    self.INFO_HASH = "529b0770601c7e04c98566c7b7bb3f75178930ae18b3084592d8af2b591a009f"
    self.CHAPTER_HASH = "121996b57011b69386b65ca8fc9e202046fc20bf68b8c8128de0d0e92a681195"
  def determine_type(self, country):
    if country == 'JP':
        return 'Manga'
    if country == 'KR':
        return 'Manhwa'
    if country == 'CN':
        return 'Manhua'
    return 'Comic'
  async def search(self, query: str = ""):
    payload = {
      "search": {
          "query": query,
          "isManga": True
      },
      "limit": 24,
      "page": 1,
      "translationType": "sub",
      "countryOrigin": "ALL"
    }
    extensions = {
      "persistedQuery": {
          "version": 1,
          "sha256Hash": self.SEARCH_HASH
      }
    }
    params = {
      "variables": json.dumps(payload),
      "extensions": json.dumps(extensions)
    }
    results = []
    try:
      data = await self.get(self.api_url, rjson=True, headers=self.headers, params=params)
      if not data:
        return []
      edges = data.get("data", {}).get("mangas", {}).get("edges", [])
      for result in edges:
        title = result.get("englishName") or result.get("name") or ""
        manga_id = result.get("_id")
        url = f"https://allmanga.to/manga/{manga_id}"
        thumbnail = result.get("thumbnail", "")
        if thumbnail and not thumbnail.startswith("http"):
            thumbnail = "https://wp.youtube-anime.com/aln.youtube-anime.com/" + thumbnail
        results.append({
            "title": title,
            "url": url,
            "poster": thumbnail
        })
    except Exception as e:
      logger.exception(f"AllManga Error: {e}")
    finally:
      return results
  async def get_chapters(self, data, page: int = 1):
    results = data.copy()
    manga_id = results['url'].rstrip('/').split('/')[-1]
    variables = {
        "_id": manga_id,
        "search": {
            "allowAdult": False,
            "allowUnknown": False
        }
    }
    extensions = {
        "persistedQuery": {
            "version": 1,
            "sha256Hash": self.INFO_HASH
        }
    }
    params = {
        "variables": json.dumps(variables),
        "extensions": json.dumps(extensions)
    }
    try:
      data = await self.get(self.api_url, rjson=True, headers=self.headers, params=params)
      data = data.get("data", {}).get("manga", {})
      title = data.get("englishName") or data.get("name") or "Title not found"
      description = data.get("description") or "No Description Available."
      description = re.sub(r'<.*?>', '', description)
      status = data.get("status") or "N/A"
      raw_genres = data.get("genres", [])
      demographic_types = all_tags_except_genres = {
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
        "Royalty", "Political", "Slice of Life Comedy", "Comedy Drama"
      }
      genres = [g for g in raw_genres if g not in demographic_types]
      genres = ", ".join(genres)
      alt_titles = []
      alt_raw = data.get("altNames", [])
      for t in alt_raw:
        if re.match(r'^[\w\s.,!?\'"()\-:;]+$', t) and re.search(r'[a-zA-Z]', t):
            alt_titles.append(t)
        elif re.search(r'[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff]', t):
            alt_titles.append(t)
        elif re.search(r'[\uac00-\ud7af]', t):
            alt_titles.append(t)
        elif re.search(r'[\u4e00-\u9fff]', t):
            alt_titles.append(t)
      alt_titles = ", ".join(alt_titles[:3]) if alt_titles else "N/A"
      year = data.get("airedStart", {}).get("year", "N/A")
      country = data.get("countryOfOrigin", "")
      mtype = self.determine_type(country)
      thumbnails = data.get("thumbnails", [])
      cover = None
      thumb_cover = None
      max_num = -1
      for thumb in thumbnails:
        if thumb.startswith("mcovers/m_tbs/"):
            match = re.search(r'/(\d+)(?:\.\d+)?\.(jpg|png)$', thumb)
            if match:
                num = int(match.group(1))
                if num > max_num:
                    max_num = num
                    thumb_cover = thumb
      if thumb_cover:
        cover = "https://wp.youtube-anime.com/aln.youtube-anime.com/" + thumb_cover
      else:
        cover = data.get("thumbnail", "")
        if cover and not cover.startswith("http"):
            cover = "https://wp.youtube-anime.com/aln.youtube-anime.com/" + cover
      thumbnails = data.get("thumbnails", [])
      al_url = None
      mal_url = None
      for thumb in thumbnails:
        if "myanimelist.net" in thumb:
            try:
                mal_id = thumb.split("/")[-1].split(".")[0]
                mal_url = f"https://myanimelist.net/manga/{mal_id}"
            except Exception:
                pass
        elif "anilist.co" in thumb:
            try:
                bx_id = thumb.split("/")[-1].split("-")[0]
                if bx_id.startswith("bx"):
                    ani_id = bx_id.replace("bx", "")
                    al_url = f"https://anilist.co/manga/{ani_id}"
            except Exception:
                pass
      results['msg'] = ALL_MSG_FORMAT.format(
        title=title,
        status=status,
        genres=genres,
        summary=description[:100],
        url=results['url'],
        anilist=al_url,
        myanime=mal_url,
        alt_title=alt_titles,
        type=mtype,
        year=year
      )
      if len(results['msg'])> 1024:
        results['msg'] = DEAULT_MSG_FORMAT.format(
          title=title,
          status=status,
          genres=genres,
          summary=description[:200],
          url=results['url']
        )
      chapters_detail = data.get("availableChaptersDetail", {}).get("sub", [])
      results['chapters'] = []
      for number in chapters_detail:
        results['chapters'].append((
            f"Chapter {number}",
            f"https://allmanga.to/read/{manga_id}/chapter-{number}-sub"
        ))
    except Exception as e:
      logger.exception(f"AllManga Error: {e}")
    finally:
      return results
  def iter_chapters(self, data, page: int = 1):
    chapters_list = []
    if not data['chapters']:
      return []
    for chapters in data['chapters']:
      try:
        chapters_list.append({
            "title":
            chapters[0],
            "url":
            chapters[1],
            "manga_title":
            data['title'],
            "poster":
            data['poster'] if 'poster' in data else None,
        })
      except:
        continue
    return chapters_list[(page - 1) * 60:page *
                         60] if page != 1 else chapters_list
  async def get_pictures(self, url, data=None):
    try:
      try:
        parts = url.rstrip("/").split("/")
        manga_id = parts[4]
        chapter_str = parts[5].split("-")[1]
      except:
        return []
      variables = {
        "mangaId": manga_id,
        "translationType": "sub",
        "chapterString": chapter_str,
        "limit": 999999,
        "offset": 0
      }
      extensions = {
        "persistedQuery": {
            "version": 1,
            "sha256Hash": self.CHAPTER_HASH
        }
      }
      params = {
        "variables": json.dumps(variables),
        "extensions": json.dumps(extensions)
      }
      resp = await self.get(self.api_url, rjson=True, headers=self.headers, params=params)
      edges = resp.get("data", {}).get("chapterPages", {}).get("edges", [])
      if not edges:
        return []
      source = edges[0]
      pic_head = source.get("pictureUrlHead")
      pic_urls = source.get("pictureUrls", [])
      images = []
      for img in pic_urls:
        image1 = f"{pic_head}{img['url']}"
        poster = "https://nanobridge.nanobridge-proxy.workers.dev/proxy?url=" + quote(image1, safe="")
        images.append(poster)
      return images
    except Exception as e:
      logger.exception(f"Error KaliScans Images: {e}")
      return []
