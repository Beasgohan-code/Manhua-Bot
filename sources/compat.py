# Manhua-Bot - scraper interface compatibility layer
#
# Two scraper generations live in sources/scrapers/:
#
#   "modern" (34 sources) : search() -> list, get_manga(id) -> dict with
#                           chapters[], get_chapter(url) -> [image urls]
#   "legacy" (35 sources) : search() -> list of dicts, get_chapters(data)
#                           -> enriched dict, iter_chapters(data) -> list,
#                           get_pictures(url, data) -> [image urls]
#
# /search handled both, but /dl only ever called get_manga(), so direct
# download silently failed on every legacy source (Comick, Asura, Batoto,
# FlameComics, WeebCentral, MangaPark, ...). This module normalises both
# into one interface so callers stop caring.

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)


def is_legacy(scraper) -> bool:
    """Legacy scrapers expose get_chapters/get_pictures, not get_manga."""
    return not callable(getattr(scraper, "get_manga", None)) and callable(
        getattr(scraper, "get_chapters", None)
    )


def _norm_chapter(ch: Any, idx: int) -> Optional[Dict[str, Any]]:
    """Coerce a chapter in any of the shapes scrapers emit into a dict."""
    if ch is None:
        return None
    if isinstance(ch, dict):
        url = ch.get("url") or ch.get("link") or ch.get("href") or ""
        title = ch.get("title") or ch.get("name") or ch.get("chapter") or ""
    elif isinstance(ch, (tuple, list)):
        if not ch:
            return None
        title = str(ch[0]) if len(ch) > 0 else ""
        url = str(ch[1]) if len(ch) > 1 else ""
    else:
        return None
    if not url:
        return None

    import re

    num = ""
    m = re.search(r"(\d+(?:\.\d+)?)", str(title))
    if m:
        num = m.group(1)
    else:
        m = re.search(r"(\d+(?:\.\d+)?)", str(url).rstrip("/").split("/")[-1])
        if m:
            num = m.group(1)
    return {
        "id": (ch.get("chapter_id") if isinstance(ch, dict) else None) or str(idx),
        "title": str(title) or f"Chapter {num or idx}",
        "url": url,
        "num": num or str(idx),
    }


async def _maybe_await(value):
    if asyncio.iscoroutine(value):
        return await value
    return value


async def resolve_series(scraper, ident: str, timeout: int = 60) -> Optional[Dict]:
    """Return {title, url, cover, chapters:[{title,url,num,id}]} for any scraper.

    `ident` may be an id, a slug or a full URL.
    """
    # ---- modern interface -------------------------------------------------
    if callable(getattr(scraper, "get_manga", None)):
        try:
            manga = await asyncio.wait_for(scraper.get_manga(ident), timeout=timeout)
        except Exception as exc:
            log.warning(f"[COMPAT] get_manga failed: {exc}")
            manga = None
        if manga:
            chaps = manga.get("chapters") or []
            manga["chapters"] = [
                c for c in (_norm_chapter(c, i + 1) for i, c in enumerate(chaps)) if c
            ]
            return manga
        # fall through and try the legacy path too

    # ---- legacy interface -------------------------------------------------
    if not callable(getattr(scraper, "get_chapters", None)):
        return None

    seed: Dict[str, Any] = {}
    ident_s = str(ident)

    if ident_s.startswith("http"):
        seed = {"url": ident_s, "title": ident_s.rstrip("/").split("/")[-1]}
    else:
        # Legacy get_chapters() needs the dict that search() produced, so
        # look the title back up rather than guessing a URL shape.
        try:
            found = await asyncio.wait_for(scraper.search(ident_s), timeout=timeout)
        except Exception as exc:
            log.warning(f"[COMPAT] search lookup failed: {exc}")
            found = None
        if found:
            low = ident_s.lower()
            seed = next(
                (
                    r for r in found
                    if isinstance(r, dict)
                    and (
                        low in str(r.get("url", "")).lower()
                        or low in str(r.get("title", "")).lower()
                        or low == str(r.get("manga_id", "")).lower()
                        or low == str(r.get("slug", "")).lower()
                    )
                ),
                found[0] if isinstance(found[0], dict) else {},
            )
        if not seed:
            return None

    try:
        enriched = await asyncio.wait_for(scraper.get_chapters(seed), timeout=timeout)
    except Exception as exc:
        log.warning(f"[COMPAT] get_chapters failed: {exc}")
        enriched = None

    data = enriched if isinstance(enriched, dict) else dict(seed)
    if isinstance(enriched, list):
        data["chapters"] = enriched

    raw: List[Any] = []
    if callable(getattr(scraper, "iter_chapters", None)):
        try:
            raw = await _maybe_await(scraper.iter_chapters(data, 1)) or []
        except Exception as exc:
            log.debug(f"[COMPAT] iter_chapters failed: {exc}")
    if not raw:
        raw = data.get("chapters") or []

    chapters = [c for c in (_norm_chapter(c, i + 1) for i, c in enumerate(raw)) if c]
    return {
        "id": data.get("manga_id") or data.get("slug") or ident_s,
        "title": data.get("title") or data.get("manga_title") or ident_s,
        "url": data.get("url") or "",
        "cover": data.get("poster") or data.get("cover") or "",
        "chapters": chapters,
        "_legacy_data": data,
    }


async def resolve_pages(
    scraper, chapter: Dict[str, Any], series: Optional[Dict] = None, timeout: int = 60
) -> List[str]:
    """Return the image URLs for one chapter, whichever interface exists."""
    url = chapter.get("url") or ""

    if callable(getattr(scraper, "get_pictures", None)):
        try:
            data = (series or {}).get("_legacy_data")
            try:
                pics = await asyncio.wait_for(
                    scraper.get_pictures(url, data), timeout=timeout
                )
            except TypeError:
                pics = await asyncio.wait_for(scraper.get_pictures(url), timeout=timeout)
            if pics:
                return [p for p in pics if p]
        except Exception as exc:
            log.warning(f"[COMPAT] get_pictures failed: {exc}")

    if callable(getattr(scraper, "get_chapter", None)):
        try:
            pics = await asyncio.wait_for(scraper.get_chapter(url), timeout=timeout)
            if pics:
                return [p for p in pics if p]
        except Exception as exc:
            log.warning(f"[COMPAT] get_chapter failed: {exc}")

    return []
