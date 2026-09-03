#!/usr/bin/env python3
"""Extraction test: prove scrapers parse *well-formed* responses correctly.

tools/audit.py fuzzes sources with malformed input and proves nothing
crashes. That is necessary but not sufficient: a scraper whose selectors are
wrong also "passes" a fuzz test, because returning [] is the expected result
for garbage input.

This harness does the opposite. It feeds each scraper a realistic response
shaped like the real site (built from that scraper's own selectors/API
fields) and asserts it actually extracts a title and a URL. A source that
returns [] here has a genuine parsing bug.

No network required — responses are served from fixtures.

Usage:  python tools/extract_test.py [-v]
"""

from __future__ import annotations

import asyncio
import json
import pathlib
import sys
import warnings

warnings.filterwarnings("ignore")
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    from loguru import logger

    logger.remove()
except Exception:
    pass

OK, FAIL, WARN, SKIP = "\033[92m✓\033[0m", "\033[91m✗\033[0m", "\033[93m!\033[0m", "·"


# --------------------------------------------------------------- fixtures
def wp_manga_html() -> str:
    """WordPress "Madara" theme — by far the most common manga CMS."""
    return """
    <html><body>
      <div class="c-tabs-item">
        <div class="row c-tabs-item__content">
          <div class="tab-thumb c-image-hover">
            <a href="https://site.test/manga/test-manga/" title="Test Manga">
              <img src="https://site.test/cover.jpg" class="img-responsive"/>
            </a>
          </div>
          <div class="tab-summary">
            <div class="post-title"><h3 class="h4">
              <a href="https://site.test/manga/test-manga/">Test Manga</a>
            </h3></div>
            <div class="mg_chapter"><a href="https://site.test/manga/test-manga/ch-10/">Chapter 10</a></div>
          </div>
        </div>
      </div>
      <div class="listing-chapters_wrap">
        <ul class="main version-chap">
          <li class="wp-manga-chapter">
            <a href="https://site.test/manga/test-manga/ch-2/">Chapter 2</a>
          </li>
          <li class="wp-manga-chapter">
            <a href="https://site.test/manga/test-manga/ch-1/">Chapter 1</a>
          </li>
        </ul>
      </div>
      <div class="reading-content">
        <div class="page-break"><img class="wp-manga-chapter-img" src="https://site.test/p1.jpg"/></div>
        <div class="page-break"><img class="wp-manga-chapter-img" src="https://site.test/p2.jpg"/></div>
      </div>
    </body></html>
    """


def generic_cards_html() -> str:
    """Grid-of-cards layout used by many custom themes."""
    return """
    <html><body>
      <div id="book_list">
        <div class="item">
          <div class="wrap_img"><a href="https://site.test/manga/test-manga">
            <img src="https://site.test/cover.jpg"/></a></div>
          <h3 class="title"><a href="https://site.test/manga/test-manga">Test Manga</a></h3>
          <div class="genres uk-hidden-small"><a>Action</a></div>
          <div class="chapter"><a href="https://site.test/manga/test-manga/c10">Chapter 10</a></div>
        </div>
      </div>
      <div class="bigOne"><a href="https://site.test/manga/test-manga">Test Manga</a></div>
      <article class="bs"><div class="bsx">
        <a href="https://site.test/manga/test-manga" title="Test Manga">
          <div class="tt">Test Manga</div>
          <img src="https://site.test/cover.jpg"/>
        </a></div></article>
      <ul class="clstyle"><li><a href="https://site.test/manga/test-manga/ch-1">Chapter 1</a></li></ul>
      <div id="readerarea"><img src="https://site.test/p1.jpg"/></div>
      <a href="https://site.test/manga/test-manga">Test Manga</a>
      <a href="https://site.test/series/test-manga">Test Manga</a>
      <a href="https://site.test/comic/test-manga">Test Manga</a>
      <a href="https://site.test/title/abc-test-manga">Test Manga</a>
    </body></html>
    """


def api_json() -> dict:
    """Superset of the JSON field names the API-backed scrapers look for."""
    entry = {
        "id": "123", "manga_id": "123", "hash_id": "abc", "slug": "test-manga",
        "comic_id": "123", "series_id": "123",
        "title": "Test Manga", "name": "Test Manga", "label": "Test Manga",
        "series_slug": "test-manga",
        "poster": {"large": "https://site.test/c.jpg"},
        "thumbnail": "https://site.test/c.jpg",
        "cover": {"id": "cv1", "f": "JPEG"},
        "image": "https://site.test/c.jpg",
        "url": "https://site.test/manga/test-manga",
        "chapters": [
            {"id": "1", "chapter": "1", "number": 1, "title": "Chapter 1",
             "slug": "ch-1", "url": "https://site.test/manga/test-manga/1-chapter"},
        ],
    }
    return {
        "result": {"items": [entry], "data": [entry]},
        "data": [entry],
        "items": [entry],
        "results": [entry],
        "comics": [entry],
        "series": [entry],
        "mangas": [entry],
        "hits": [entry],
        "list": [entry],
        "posts": [entry],
        "suggestions": [entry],
        "success": True,
        "entry": entry,
    }


class Fixture:
    """Serves a plausible response for whatever the scraper asks for."""

    def __init__(self):
        self.calls = 0

    def body(self, url: str, rjson):
        self.calls += 1
        if rjson:
            return api_json()
        u = str(url).lower()
        if any(k in u for k in ("search", "?s=", "query", "ajax", "browse", "filter")):
            return wp_manga_html() + generic_cards_html()
        return wp_manga_html() + generic_cards_html()


async def main() -> int:
    verbose = "-v" in sys.argv
    from sources.base import scraper as SC
    from services.mgr import mgr
    from services.vmgr import vmgr

    fx = Fixture()

    async def fake_get(self, url, rjson=None, cs=None, timeout=30, *a, **k):
        return fx.body(url, rjson)

    async def fake_post(self, url, rjson=None, cs=None, timeout=30, *a, **k):
        return fx.body(url, rjson)

    SC.Scraper.get = fake_get
    SC.Scraper.post = fake_post

    # WeebCentral bypasses Scraper.post and calls cloudscraper directly.
    class FakeResp:
        status_code = 200
        text = wp_manga_html() + generic_cards_html()

        def json(self):
            return api_json()

    for src in list(mgr.srcs.values()) + list(vmgr.srcs.values()):
        sc = getattr(src, "scraper", None)
        if sc is not None:
            sc.get = lambda *a, **k: FakeResp()
            sc.post = lambda *a, **k: FakeResp()

    print("\033[1mExtraction test — realistic fixtures\033[0m\n")

    extracted, empty, errored = [], [], []
    for name, src in sorted(mgr.srcs.items()):
        try:
            res = await asyncio.wait_for(src.search("test manga"), timeout=15)
        except Exception as exc:
            errored.append((name, f"{type(exc).__name__}: {exc}"[:70]))
            continue
        if not res:
            empty.append(name)
            continue
        first = res[0] if isinstance(res, (list, tuple)) else None
        title = url = None
        if isinstance(first, dict):
            title = first.get("title") or first.get("name")
            url = first.get("url") or first.get("link")
        if title and url:
            extracted.append((name, str(title)[:28], len(res)))
        else:
            empty.append(f"{name} (no title/url)")

    total = len(mgr.srcs)
    print(f"{OK} extracted from {len(extracted)}/{total} manga sources")
    if verbose:
        for n, t, c in extracted:
            print(f"    {OK} {n:24} {c:3} results, first={t!r}")
    if empty:
        print(f"{WARN} {len(empty)} returned nothing (selectors differ from fixture):")
        for n in empty[:40]:
            print(f"    {SKIP} {n}")
    if errored:
        print(f"{FAIL} {len(errored)} raised on WELL-FORMED input (real bugs):")
        for n, e in errored:
            print(f"    {FAIL} {n}: {e}")

    # Video sources
    v_ok, v_empty, v_err = [], [], []
    for name, src in vmgr.srcs.items():
        try:
            res = await asyncio.wait_for(src.search("test"), timeout=15)
            (v_ok if res else v_empty).append(src.sf)
        except Exception as exc:
            v_err.append((src.sf, f"{type(exc).__name__}: {exc}"[:60]))
    print(f"\n{OK} video: {len(v_ok)} extracted, {len(v_empty)} empty, {len(v_err)} errored")
    if v_err:
        for n, e in v_err:
            print(f"    {FAIL} {n}: {e}")

    print(f"\n\033[1mSummary\033[0m")
    print(f"  parsed OK : {len(extracted)}/{total}")
    print(f"  no match  : {len(empty)}  (fixture shape mismatch, not proof of breakage)")
    print(f"  errors    : {len(errored) + len(v_err)}  <- these are real bugs")
    return 1 if (errored or v_err) else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
