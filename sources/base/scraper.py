
import requests
from cloudscraper import create_scraper
from asyncio import to_thread
class Scraper:
  _shared_scraper = None
  _shared_session = None
  def __init__(self):
    if Scraper._shared_scraper is None:
      Scraper._shared_scraper = create_scraper()
    if Scraper._shared_session is None:
      Scraper._shared_session = requests.Session()
      Scraper._shared_session.headers.update({
          'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
      })
    self.scraper = Scraper._shared_scraper
    self.session = Scraper._shared_session
  def close(self):
    pass
  async def get(self, url, rjson=None, cs=None, timeout=30, *args, **kwargs):
      if 'timeout' not in kwargs:
          kwargs['timeout'] = timeout
      if cs:
        response = await to_thread(self.scraper.get, url, *args, **kwargs)
      else:
        headers = kwargs.get('headers', {})
        kwargs['headers'] = headers
        response = await to_thread(self.session.get, url, *args, **kwargs)
      if response.status_code == 200:
        return response.json() if rjson else response.text
      else:
        return None
  async def post(self, url, rjson=None, cs=None, timeout=30, *args, **kwargs):
    if 'timeout' not in kwargs:
        kwargs['timeout'] = timeout
    if cs:
      response = await to_thread(self.scraper.post, url, *args, **kwargs)
    else:
      headers = kwargs.get('headers', {})
      kwargs['headers'] = headers
      response = await to_thread(self.session.post, url, *args, **kwargs)
    if response.status_code == 200:
      return response.json() if rjson else response.text
    else:
      return None
