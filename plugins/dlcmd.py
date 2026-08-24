# Manhua-Bot - Direct download with chapter range support
# /dl <source> <id_or_url> [chapter|start-end]

from pyrogram import Client, filters
from database.db import db
from services.mgr import mgr
from plugins.fsub import force_sub
from plugins.adult_cmd import is_adult_source, user_allows_adult
import logging
import asyncio
import re

log = logging.getLogger(__name__)


def parse_range(token: str):
    """Return list of chapter number tokens from '12' or '10-15'."""
    token = token.strip()
    m = re.match(r"^(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)$", token)
    if m:
        a, b = float(m.group(1)), float(m.group(2))
        if a > b:
            a, b = b, a
        # integer range preferred
        if a == int(a) and b == int(b):
            return [str(i) for i in range(int(a), int(b) + 1)]
        return [str(a), str(b)]
    return [token]


def chap_matches(chap: dict, wanted: set) -> bool:
    nums = set()
    for k in ("num", "title", "id"):
        v = str(chap.get(k) or "")
        nums.add(v.lower())
        m = re.search(r"(\d+(?:\.\d+)?)", v)
        if m:
            nums.add(m.group(1))
            try:
                nums.add(str(int(float(m.group(1)))))
            except Exception:
                pass
    return any(w.lower() in nums or w in nums for w in wanted)


@Client.on_message(filters.command(["dl", "download"]))
@force_sub
async def dl_cmd(c, m):
    args = m.command[1:]
    if len(args) < 2:
        return await m.reply(
            "<b>⬇️ Direct Download</b>\n\n"
            "<blockquote>"
            "<b>Usage</b>\n"
            "<code>/dl &lt;source&gt; &lt;id_or_url&gt; [ch|start-end]</code>\n\n"
            "<b>Examples</b>\n"
            "<code>/dl nhentai 123456</code>\n"
            "<code>/dl comick some-slug 12</code>\n"
            "<code>/dl asura my-series 10-15</code>\n"
            "</blockquote>\n"
            "Or use /search → chapter → ⬇️ button."
        )

    src = args[0]
    series = args[1]
    chap_hint = args[2] if len(args) > 2 else None

    scraper = mgr.get(src) or mgr.get(src + "Webs")
    if not scraper:
        keys = list(mgr.srcs.keys()) if hasattr(mgr, "srcs") else []
        match = next((k for k in keys if src.lower() in k.lower()), None)
        scraper = mgr.get(match) if match else None
        src = match or src

    if not scraper:
        return await m.reply(f"<blockquote>⚠ Unknown source: <code>{args[0]}</code></blockquote>")

    # NSFW gate
    if is_adult_source(str(src)) and not await user_allows_adult(m.from_user.id):
        return await m.reply(
            "🔞 This is an adult source. Enable with <code>/adult on</code> first."
        )

    status = await m.reply(f"<blockquote>⋯ Loading <code>{src}</code>…</blockquote>")

    try:
        manga = None
        for meth in ("get_manga", "get", "manga"):
            fn = getattr(scraper, meth, None)
            if callable(fn):
                try:
                    manga = await asyncio.wait_for(fn(series), timeout=40)
                    if manga:
                        break
                except Exception as e:
                    log.warning(f"[DLCMD] {meth}: {e}")

        if not manga:
            return await status.edit("<blockquote>⚠ Series not found</blockquote>")

        manga["src"] = src if isinstance(src, str) else getattr(scraper, "sf", src)

        chapters = manga.get("chapters") or []
        if not chapters and hasattr(scraper, "get_chapters"):
            try:
                raw = await asyncio.wait_for(scraper.get_chapters(manga), timeout=60)
                if isinstance(raw, dict):
                    manga.update(raw)
                    chapters = raw.get("chapters") or []
                elif isinstance(raw, list):
                    chapters = raw
            except Exception as e:
                log.warning(f"[DLCMD] get_chapters: {e}")

        if not chapters:
            chapters = [{"title": manga.get("title"), "url": manga.get("url") or series, "num": "1"}]

        # select targets
        targets = []
        if chap_hint:
            wanted = set(parse_range(chap_hint))
            for citem in chapters:
                if chap_matches(citem, wanted):
                    targets.append(citem)
            if not targets:
                # fallback: single first match contains
                ch = chap_hint.lower()
                for citem in chapters:
                    t = str(citem.get("title") or citem.get("num") or "").lower()
                    if ch in t:
                        targets.append(citem)
                        break
        else:
            targets = [chapters[0]]

        if not targets:
            return await status.edit(
                f"<blockquote>⚠ No matching chapters for <code>{chap_hint}</code></blockquote>"
            )

        # limit range size
        if len(targets) > 20:
            targets = targets[:20]
            await status.edit(f"<blockquote>Downloading first 20 of range…</blockquote>")

        from services.dl import download_and_send
        ok, fail = 0, 0
        for i, target in enumerate(targets, 1):
            try:
                await status.edit(
                    f"<blockquote>⬇️ {i}/{len(targets)} — "
                    f"<code>{target.get('title') or target.get('num')}</code></blockquote>"
                )
                await download_and_send(c, m.chat.id, manga, target, status_msg=None, user_id=m.from_user.id)
                ok += 1
            except Exception as e:
                log.error(f"[DLCMD] ch fail: {e}")
                fail += 1
                await m.reply(f"⚠ Failed: <code>{target.get('title') or target.get('num')}</code> — {str(e)[:80]}")

        try:
            await status.edit(f"<b>Done</b> — ok <code>{ok}</code> · failed <code>{fail}</code>")
        except Exception:
            pass

    except Exception as e:
        log.error(f"[DLCMD] {e}")
        await status.edit(f"<blockquote>⚠ Failed: {str(e)[:100]}</blockquote>")
