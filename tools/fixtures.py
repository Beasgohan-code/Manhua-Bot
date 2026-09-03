# Manhua-Bot - per-source response fixtures
#
# The generic fixture in extract_test.py only matches scrapers whose markup
# resembles the common WordPress/Madara or card-grid shapes. For the rest,
# "returned nothing" was ambiguous: broken selectors and a mismatched fixture
# look identical.
#
# These fixtures are built from each scraper's OWN selectors, so a source that
# still returns nothing here has a genuine parsing fault. Each entry is keyed
# by scraper class name and returns either an HTML string or a JSON-able dict.
#
# Keep the marker title in sync with EXPECT_TITLE — the harness asserts the
# scraper extracted exactly that.

from __future__ import annotations

from typing import Any, Callable, Dict, Optional

EXPECT_TITLE = "One Piece"
EXPECT_URL = "https://site.test/manga/one-piece"
EXPECT_CH = "https://site.test/manga/one-piece/chapter-1"


def _mangapark() -> str:
    # soup.select("div.group.relative.w-full") -> a + img[title]
    return f"""<html><body>
      <div class="group relative w-full">
        <a href="/title/123-one-piece"></a>
        <img title="{EXPECT_TITLE}" src="https://site.test/c.jpg"/>
      </div>
    </body></html>"""


def _mangapark_alt() -> str:
    # MangaParkAlt selects a.link-hover / .ms-item a / .manga-list a and
    # requires "/title/" or "/manga/" in the href.
    return f"""<html><body>
      <a class="link-hover" href="/title/123-one-piece">{EXPECT_TITLE}</a>
      <div class="ms-item"><a href="/title/123-one-piece">{EXPECT_TITLE}</a></div>
      <div class="manga-list"><a href="/manga/one-piece">{EXPECT_TITLE}</a></div>
    </body></html>"""


def _batoto() -> str:
    # "#series-list .col.item" -> a.item-cover + a.item-title
    return f"""<html><body>
      <div id="series-list">
        <div class="col item">
          <a class="item-cover" href="/series/123/one-piece">
            <img src="https://site.test/c.jpg"/>
          </a>
          <a class="item-title" href="/series/123/one-piece">{EXPECT_TITLE}</a>
        </div>
      </div>
    </body></html>"""


def _asura() -> str:
    # find(class_="grid grid-cols-2 sm:grid-cols-2 md:grid-cols-5 gap-3 p-4")
    return f"""<html><body>
      <div class="grid grid-cols-2 sm:grid-cols-2 md:grid-cols-5 gap-3 p-4">
        <a href="series/one-piece-abc">
          <img src="https://site.test/c.jpg"/>
          <span>Manga</span>
          <span class="block text-[13.3px] font-bold">{EXPECT_TITLE}</span>
        </a>
      </div>
    </body></html>"""


def _nhentai() -> Dict[str, Any]:
    return {
        "result": [
            {
                "id": 123456,
                "media_id": "999",
                "title": {"english": EXPECT_TITLE, "pretty": EXPECT_TITLE},
                "images": {
                    "thumbnail": {"t": "j"},
                    "pages": [{"t": "j"}, {"t": "j"}],
                },
                "num_pages": 2,
                "tags": [],
            }
        ],
        "num_pages": 1,
    }


def _generic_json() -> Dict[str, Any]:
    entry = {
        "id": "123", "manga_id": "123", "hash_id": "abc", "comic_id": "123",
        "series_id": "123", "slug": "one-piece", "series_slug": "one-piece",
        "title": EXPECT_TITLE, "name": EXPECT_TITLE, "label": EXPECT_TITLE,
        "url": EXPECT_URL, "link": EXPECT_URL,
        "cover": "https://site.test/c.jpg",
        "thumbnail": "https://site.test/c.jpg",
        "image": "https://site.test/c.jpg",
        "poster": "https://site.test/c.jpg",
    }
    return {
        "result": {"items": [entry], "data": [entry]},
        "data": [entry], "items": [entry], "results": [entry],
        "list": [entry], "comics": [entry], "series": [entry],
        "mangas": [entry], "hits": [entry], "posts": [entry],
        "suggestions": [entry], "success": True,
    }


def _madara() -> str:
    return f"""<html><body>
      <div class="c-tabs-item">
        <div class="row c-tabs-item__content">
          <div class="tab-thumb c-image-hover">
            <a href="{EXPECT_URL}" title="{EXPECT_TITLE}">
              <img src="https://site.test/c.jpg"/></a>
          </div>
          <div class="tab-summary">
            <div class="post-title"><h3 class="h4">
              <a href="{EXPECT_URL}">{EXPECT_TITLE}</a></h3></div>
          </div>
        </div>
      </div>
      <div class="listing-chapters_wrap"><ul class="main version-chap">
        <li class="wp-manga-chapter"><a href="{EXPECT_CH}">Chapter 1</a></li>
      </ul></div>
      <div class="reading-content">
        <div class="page-break"><img class="wp-manga-chapter-img"
             src="https://site.test/p1.jpg"/></div>
      </div>
    </body></html>"""


def _cards() -> str:
    """Broad card-grid markup covering several bespoke themes at once."""
    return f"""<html><body>
      <div id="book_list">
        <div class="item">
          <div class="wrap_img"><a href="{EXPECT_URL}">
            <img src="https://site.test/c.jpg"/></a></div>
          <h3 class="title"><a href="{EXPECT_URL}">{EXPECT_TITLE}</a></h3>
          <div class="genres uk-hidden-small"><a>Action</a></div>
          <div class="chapter"><a href="{EXPECT_CH}">Chapter 1</a></div>
        </div>
      </div>
      <div class="listupd">
        <div class="bs"><div class="bsx">
          <a href="{EXPECT_URL}" title="{EXPECT_TITLE}">
            <div class="tt">{EXPECT_TITLE}</div>
            <img src="https://site.test/c.jpg"/>
          </a></div></div>
      </div>
      <div class="list-truyen-item-wrap">
        <a href="{EXPECT_URL}" title="{EXPECT_TITLE}">
          <img src="https://site.test/c.jpg"/></a>
        <h3><a href="{EXPECT_URL}">{EXPECT_TITLE}</a></h3>
      </div>
      <div class="manga-item">
        <a href="{EXPECT_URL}">{EXPECT_TITLE}</a>
        <img src="https://site.test/c.jpg"/>
      </div>
      <ul class="clstyle"><li><a href="{EXPECT_CH}">Chapter 1</a></li></ul>
      <div id="readerarea"><img src="https://site.test/p1.jpg"/></div>
      <a class="item-cover" href="{EXPECT_URL}">{EXPECT_TITLE}</a>
      <a href="{EXPECT_URL}">{EXPECT_TITLE}</a>
      <a href="https://site.test/series/one-piece">{EXPECT_TITLE}</a>
      <a href="https://site.test/comic/one-piece">{EXPECT_TITLE}</a>
      <a href="https://site.test/title/abc-one-piece">{EXPECT_TITLE}</a>
    </body></html>"""


# scraper class name -> callable returning HTML str or JSON dict
FIXTURES: Dict[str, Callable[[], Any]] = {
    "MangaParkWebs": _mangapark,
    "MangaParkAltWebs": _mangapark_alt,
    "BatotoWebs": _batoto,
    "AsuraScansWebs": _asura,
    "NHentaiWebs": _nhentai,
}


def html_for(name: str) -> str:
    """Best HTML fixture for a scraper: specific if known, else combined."""
    fn = FIXTURES.get(name)
    if fn is not None:
        out = fn()
        if isinstance(out, str):
            return out
    return _madara() + _cards()


def json_for(name: str) -> Any:
    fn = FIXTURES.get(name)
    if fn is not None:
        out = fn()
        if not isinstance(out, str):
            return out
    return _generic_json()
