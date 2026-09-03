# Manhua-Bot - anime / hentai video commands
#
# UI/engine adapted from the reference bots:
#   * KunalG932/auto-manga-chapter-update-bot — "search ALL sources" flow,
#     paginated result cards, cached session ids
#   * zenin-373/Hstream-TG — live progress cards, subtitle remux
#   * MatrixRobots/Hanime-Downloader — quality picker, rich status panels
#
#   /anime  <name>    search SFW anime sources
#   /hentai <name>    search adult sources (requires /adult on)
#   /vsearch <name>   search everything the user is allowed to see
#   /vdl <src> <id> [ep|a-b]
#   /vsources         video site list
#   /vengine          engine + hanime-plugin diagnostics

from __future__ import annotations

import asyncio
import logging
import re
import time
from pathlib import Path

from pyrogram import Client, filters
from pyrogram.errors import MessageNotModified
from pyrogram.types import InlineKeyboardMarkup as KM, InlineKeyboardButton as KB

from plugins.adult_cmd import user_allows_adult
from plugins.fsub import force_sub
from services.mem import mem
from services.vmgr import vmgr
from services import vengine
from services.hplugin import plugin_status, status_line
from services.video_dl import download_and_send_video, vget

log = logging.getLogger(__name__)

PER_PAGE = 8
EPS_PER_PAGE = 30
SESSION_MIN = 60


def _key(prefix: str, uid: int) -> str:
    return f"{prefix}_{uid}_{int(time.time() * 1000) % 10_000_000}"


async def safe_edit(msg, text, reply_markup=None):
    try:
        await msg.edit(text, reply_markup=reply_markup)
    except MessageNotModified:
        pass
    except Exception as exc:
        log.debug(f"[VUI] edit failed: {exc}")


def split_cb(data: str, prefix: str, tail: int = 1):
    """Split callback data whose session key itself contains underscores.

    Layout is `<prefix>_<skey>_<arg...>`; skey is `name_uid_ts`, so we peel
    the fixed number of trailing args off the end instead of splitting
    left-to-right (which would slice the key apart).
    """
    body = data[len(prefix):]
    parts = body.rsplit("_", tail)
    return parts[0], *parts[1:]


def rule(char: str = "━", n: int = 26) -> str:
    return char * n


def _engine_warn() -> str:
    st = vengine.engine_status()
    bits = []
    if not st["yt_dlp"]:
        bits.append("yt-dlp missing")
    if not st["ffmpeg"]:
        bits.append("ffmpeg missing")
    return f"\n⚠️ <i>{' · '.join(bits)}</i>" if bits else ""


# ------------------------------------------------------------------ search
async def _do_search(c, m, query: str, mode: str):
    uid = m.from_user.id
    allow_adult = await user_allows_adult(uid)

    if mode == "adult" and not allow_adult:
        return await m.reply(
            "🔞 <b>Adult sources locked</b>\n\n"
            "<blockquote>Enable them first with <code>/adult on</code>.</blockquote>"
        )

    use_adult = allow_adult and mode != "sfw"
    total = len(vmgr.names(use_adult))

    status = await m.reply(
        f"<b>⌕ Searching</b>\n{rule()}\n"
        f"Query: <code>{query}</code>\n"
        f"Sources: <code>0/{total}</code>\n"
        f"{vengine.progress_bar(0)}\n"
        f"Found: <code>0</code>"
    )

    last = [0.0]

    async def on_progress(st):
        now = time.time()
        if now - last[0] < 1.5 and st["done"] < st["total"]:
            return
        last[0] = now
        pct = 100.0 * st["done"] / max(1, st["total"])
        await safe_edit(
            status,
            f"<b>⌕ Searching</b>\n{rule()}\n"
            f"Query: <code>{query}</code>\n"
            f"Sources: <code>{st['done']}/{st['total']}</code>\n"
            f"{vengine.progress_bar(pct)} {pct:.0f}%\n"
            f"Found: <code>{st['found']}</code>",
        )

    results = await vmgr.search(query, allow_adult=use_adult, on_progress=on_progress)
    if mode == "sfw":
        results = [r for r in results if not r.get("adult")]
    elif mode == "adult":
        results = [r for r in results if r.get("adult")]

    stats = getattr(vmgr, "last_stats", {}) or {}
    if not results:
        return await safe_edit(
            status,
            f"<b>✗ No results</b>\n{rule()}\n"
            f"Nothing found for <code>{query}</code>.\n"
            f"<blockquote>Searched <code>{stats.get('total', 0)}</code> sources · "
            f"<code>{len(stats.get('failed', []))}</code> unreachable.</blockquote>"
            f"{_engine_warn()}",
        )

    skey = _key("vres", uid)
    mem.set(skey, {"results": results[:80], "query": query, "stats": stats}, minutes=SESSION_MIN)
    await _show_results(status, skey, 0)


async def _show_results(msg, skey: str, page: int):
    data = mem.get(skey)
    if not data:
        return await safe_edit(msg, "<blockquote>Session expired — search again.</blockquote>")

    results = data["results"]
    query, stats = data["query"], data.get("stats", {})
    pages = max(1, (len(results) + PER_PAGE - 1) // PER_PAGE)
    page = max(0, min(page, pages - 1))
    chunk = results[page * PER_PAGE : (page + 1) * PER_PAGE]

    rows = []
    for i, r in enumerate(chunk):
        idx = page * PER_PAGE + i
        tag = "🔞" if r.get("adult") else "🎬"
        rows.append(
            [KB(f"{tag} {r['title'][:34]} · {r.get('src_name', '')[:14]}", f"vpick_{skey}_{idx}")]
        )

    nav = []
    if page > 0:
        nav.append(KB("◂ Prev", f"vpg_{skey}_{page - 1}"))
    nav.append(KB(f"{page + 1}/{pages}", "noop"))
    if page < pages - 1:
        nav.append(KB("Next ▸", f"vpg_{skey}_{page + 1}"))
    rows.append(nav)
    rows.append([KB("✕ Close", "close")])

    ok = len(stats.get("ok", []))
    failed = len(stats.get("failed", []))
    await safe_edit(
        msg,
        f"<b>🎬 Video Search</b>\n{rule()}\n"
        f"Query: <code>{query}</code>\n"
        f"Results: <code>{len(results)}</code> from <code>{ok}</code> sources"
        + (f" · <code>{failed}</code> failed" if failed else "")
        + f"\n{rule()}\n<i>Pick a title to list episodes.</i>",
        KM(rows),
    )


@Client.on_callback_query(filters.regex(r"^vpg_"))
async def vpg(c, q):
    skey, page = split_cb(q.data, "vpg_")
    await q.answer()
    await _show_results(q.message, skey, int(page))


@Client.on_message(filters.command(["anime", "asearch"]))
@force_sub
async def anime_cmd(c, m):
    if len(m.command) < 2:
        return await m.reply(
            "<b>🎬 Anime search</b>\n\n<blockquote>"
            "<code>/anime &lt;name&gt;</code>\n"
            "Example: <code>/anime frieren</code></blockquote>"
        )
    await _do_search(c, m, " ".join(m.command[1:]), "sfw")


@Client.on_message(filters.command(["hentai", "hsearch"]))
@force_sub
async def hentai_cmd(c, m):
    if len(m.command) < 2:
        return await m.reply(
            "<b>🔞 Hentai search</b>\n\n<blockquote>"
            "<code>/hentai &lt;name&gt;</code>\n"
            "Requires <code>/adult on</code>.</blockquote>"
        )
    await _do_search(c, m, " ".join(m.command[1:]), "adult")


@Client.on_message(filters.command(["vsearch", "video"]))
@force_sub
async def vsearch_cmd(c, m):
    if len(m.command) < 2:
        return await m.reply(
            "<b>🎬 Video search — all sources</b>\n\n<blockquote>"
            "<code>/vsearch &lt;name&gt;</code>\n"
            "<code>/anime</code> SFW only · <code>/hentai</code> adult only"
            "</blockquote>"
        )
    await _do_search(c, m, " ".join(m.command[1:]), "all")


# ---------------------------------------------------------------- episodes
@Client.on_callback_query(filters.regex(r"^vpick_"))
async def vpick(c, q):
    skey, idx = split_cb(q.data, "vpick_")
    data = mem.get(skey)
    if not data:
        return await q.answer("Session expired — search again.", show_alert=True)
    item = data["results"][int(idx)]

    await q.answer("Loading…")
    await safe_edit(q.message, f"<blockquote>⋯ Loading <b>{item['title'][:60]}</b></blockquote>")

    series = await vmgr.get_series(item["src"], item.get("id") or item.get("url"))
    if not series:
        return await safe_edit(
            q.message,
            "<b>⚠ Could not load</b>\n<blockquote>The source did not return "
            "episode data. Try another result.</blockquote>",
        )
    series.setdefault("title", item["title"])
    if not series.get("episodes"):
        return await safe_edit(q.message, "<blockquote>⚠ No episodes found.</blockquote>")

    ekey = _key("vser", q.from_user.id)
    mem.set(ekey, series, minutes=SESSION_MIN)
    await _show_episodes(q.message, ekey, 0, q.from_user.id)


async def _show_episodes(msg, ekey: str, page: int, uid: int):
    series = mem.get(ekey)
    if not series:
        return await safe_edit(msg, "<blockquote>Session expired — search again.</blockquote>")

    eps = series.get("episodes") or []
    pages = max(1, (len(eps) + EPS_PER_PAGE - 1) // EPS_PER_PAGE)
    page = max(0, min(page, pages - 1))
    chunk = eps[page * EPS_PER_PAGE : (page + 1) * EPS_PER_PAGE]

    rows, row = [], []
    for i, ep in enumerate(chunk):
        idx = page * EPS_PER_PAGE + i
        row.append(KB(str(ep.get("num") or idx + 1), f"vep_{ekey}_{idx}"))
        if len(row) == 5:
            rows.append(row)
            row = []
    if row:
        rows.append(row)

    nav = []
    if page > 0:
        nav.append(KB("◂", f"vep_pg_{ekey}_{page - 1}"))
    nav.append(KB(f"{page + 1}/{pages}", "noop"))
    if page < pages - 1:
        nav.append(KB("▸", f"vep_pg_{ekey}_{page + 1}"))
    if len(nav) > 1:
        rows.append(nav)

    rows.append(
        [KB("⚙ Quality", f"vq_{ekey}"), KB("⬇️ Batch (25)", f"vall_{ekey}")]
    )
    rows.append([KB("✕ Close", "close")])

    quality = await vget(uid, "v_quality")
    mode = await vget(uid, "v_upload")
    await safe_edit(
        msg,
        f"<b>🎬 {series['title'][:60]}</b>\n{rule()}\n"
        f"Source: <code>{series.get('src_name') or series.get('src')}</code>\n"
        f"Episodes: <code>{len(eps)}</code>\n"
        f"Quality: <code>{vengine.quality_label(quality)}</code>\n"
        f"Upload as: <code>{mode}</code>\n{rule()}\n"
        f"<i>Tap an episode number to download.</i>{_engine_warn()}",
        KM(rows),
    )


@Client.on_callback_query(filters.regex(r"^vep_pg_"))
async def vep_pg(c, q):
    ekey, page = split_cb(q.data, "vep_pg_")
    await q.answer()
    await _show_episodes(q.message, ekey, int(page), q.from_user.id)


@Client.on_callback_query(filters.regex(r"^vq_"))
async def vq_menu(c, q):
    ekey = q.data[len("vq_"):]
    curr = await vget(q.from_user.id, "v_quality")
    rows = [
        [
            KB(f"{'● ' if curr == x else ''}{vengine.quality_label(x)}", f"vqs_{ekey}_{x}")
            for x in ("480", "720")
        ],
        [
            KB(f"{'● ' if curr == x else ''}{vengine.quality_label(x)}", f"vqs_{ekey}_{x}")
            for x in ("1080", "best")
        ],
        [KB("◂ Back", f"vep_pg_{ekey}_0")],
    ]
    await safe_edit(
        q.message,
        f"<b>⚙ Download quality</b>\n{rule()}\n"
        "<blockquote>Applies to all your downloads. The engine falls back "
        "to the next best stream when a height is unavailable.</blockquote>",
        KM(rows),
    )


@Client.on_callback_query(filters.regex(r"^vqs_"))
async def vq_set(c, q):
    ekey, val = split_cb(q.data, "vqs_")
    from services.video_dl import vset

    await vset(q.from_user.id, "v_quality", val)
    await q.answer(f"Quality: {val}")
    await _show_episodes(q.message, ekey, 0, q.from_user.id)


# --------------------------------------------------------------- downloads
async def _run_downloads(c, chat_id, uid, series, episodes, status):
    ok = fail = 0
    total = len(episodes)
    for i, ep in enumerate(episodes, 1):
        head = (
            f"<b>⬇️ {series['title'][:40]}</b>\n{rule()}\n"
            f"Episode <code>{ep.get('num')}</code> · <code>{i}/{total}</code>\n"
        )
        try:
            await safe_edit(status, head + "<i>resolving stream…</i>")
            await download_and_send_video(
                c, chat_id, uid, series, ep, status_msg=status, head=head
            )
            ok += 1
        except Exception as exc:
            log.error(f"[VDL] {series.get('title')} E{ep.get('num')}: {exc}")
            fail += 1
            await c.send_message(
                chat_id,
                f"⚠ Episode <code>{ep.get('num')}</code> failed\n"
                f"<blockquote>{str(exc)[:200]}</blockquote>",
            )
    await safe_edit(
        status,
        f"<b>✅ Finished</b>\n{rule()}\n"
        f"{series['title'][:50]}\n"
        f"Done: <code>{ok}</code> · Failed: <code>{fail}</code>",
    )


@Client.on_callback_query(filters.regex(r"^vep_(?!pg_)"))
async def vep(c, q):
    if not vengine.HAS_YTDLP:
        return await q.message.reply(_no_engine_msg())
    ekey, idx = split_cb(q.data, "vep_")
    series = mem.get(ekey)
    if not series:
        return await q.answer("Session expired — search again.", show_alert=True)
    ep = (series.get("episodes") or [])[int(idx)]
    await q.answer("Queued")
    status = await q.message.reply("<blockquote>⋯ Preparing…</blockquote>")
    asyncio.create_task(
        _run_downloads(c, q.message.chat.id, q.from_user.id, series, [ep], status)
    )


@Client.on_callback_query(filters.regex(r"^vall_"))
async def vall(c, q):
    if not vengine.HAS_YTDLP:
        return await q.message.reply(_no_engine_msg())
    ekey = q.data[len("vall_"):]
    series = mem.get(ekey)
    if not series:
        return await q.answer("Session expired — search again.", show_alert=True)
    eps = (series.get("episodes") or [])[:25]
    await q.answer(f"Queued {len(eps)}")
    status = await q.message.reply(
        f"<blockquote>⋯ Queued <code>{len(eps)}</code> episodes…</blockquote>"
    )
    asyncio.create_task(
        _run_downloads(c, q.message.chat.id, q.from_user.id, series, eps, status)
    )


def _no_engine_msg() -> str:
    return (
        "<b>⚠️ Download engine unavailable</b>\n\n"
        "<blockquote>yt-dlp is required.\n\n"
        "<code>pip install -r requirements.txt</code>\n"
        "<code>apt install ffmpeg aria2</code></blockquote>"
    )


def parse_eps(token: str):
    token = (token or "").strip()
    m = re.match(r"^(\d+)\s*-\s*(\d+)$", token)
    if m:
        a, b = sorted((int(m.group(1)), int(m.group(2))))
        return [str(i) for i in range(a, b + 1)]
    return [token] if token else []


@Client.on_message(filters.command(["vdl", "vdownload"]))
@force_sub
async def vdl_cmd(c, m):
    if not vengine.HAS_YTDLP:
        return await m.reply(_no_engine_msg())
    args = m.command[1:]
    if len(args) < 2:
        return await m.reply(
            "<b>⬇️ Direct video download</b>\n\n<blockquote>"
            "<code>/vdl &lt;source&gt; &lt;id_or_url&gt; [ep|a-b]</code>\n\n"
            "<code>/vdl hanime some-slug</code>\n"
            "<code>/vdl pahe &lt;session&gt; 1-5</code>"
            "</blockquote>See <code>/vsources</code>."
        )

    uid = m.from_user.id
    src = vmgr.get(args[0])
    if not src:
        return await m.reply(f"<blockquote>⚠ Unknown source <code>{args[0]}</code></blockquote>")
    if src.adult and not await user_allows_adult(uid):
        return await m.reply("🔞 Adult source — enable with <code>/adult on</code>.")

    status = await m.reply(f"<blockquote>⋯ Loading <code>{src.name}</code>…</blockquote>")
    series = await vmgr.get_series(vmgr.key_of(src), args[1])
    if not series:
        return await safe_edit(status, "<blockquote>⚠ Title not found.</blockquote>")

    eps = series.get("episodes") or []
    if len(args) > 2:
        wanted = set(parse_eps(args[2]))
        eps = [e for e in eps if str(e.get("num")) in wanted] or eps[:1]
    else:
        eps = eps[:1]
    if not eps:
        return await safe_edit(status, "<blockquote>⚠ No matching episodes.</blockquote>")
    await _run_downloads(c, m.chat.id, uid, series, eps[:25], status)


# ------------------------------------------------------------- diagnostics
@Client.on_message(filters.command(["vsources", "vsites"]))
@force_sub
async def vsources_cmd(c, m):
    allow = await user_allows_adult(m.from_user.id)
    sfw = [s for s in vmgr.srcs.values() if not s.adult]
    adult = [s for s in vmgr.srcs.values() if s.adult]

    body = f"<b>🎬 Anime ({len(sfw)})</b>\n" + "\n".join(
        f"• {s.name} — <code>{s.sf}</code>" for s in sfw
    )
    if allow:
        body += f"\n\n<b>🔞 Hentai ({len(adult)})</b>\n" + "\n".join(
            f"• {s.name} — <code>{s.sf}</code>" for s in adult
        )
    else:
        body += f"\n\n🔞 <i>{len(adult)} adult sources hidden — /adult on</i>"

    await m.reply(
        f"<b>Video Sources</b>\n{rule()}\n<blockquote>{body}</blockquote>\n"
        f"<i>/vsearch · /anime · /hentai · /vdl</i>",
        reply_markup=KM([[KB("⚙ Engine", "vengine_cb"), KB("✕ Close", "close")]]),
    )


def _engine_text() -> str:
    st = vengine.engine_status()

    def mark(v):
        return "✅" if v else "❌"

    return (
        f"<b>⚙ Download Engine</b>\n{rule()}\n"
        "<blockquote>"
        f"{mark(st['yt_dlp'])} yt-dlp — extraction\n"
        f"{mark(st['ffmpeg'])} ffmpeg — merge / metadata / remux\n"
        f"{mark(st['aria2c'])} aria2c — accelerated segments"
        "</blockquote>\n"
        f"<b>hanime-plugin</b>\n<blockquote>{status_line()}</blockquote>\n"
        + ("" if st["ffmpeg"] else
           "\n<i>Without ffmpeg: no 1080p merge, no MKV subtitles.</i>\n"
           "<code>apt install ffmpeg aria2</code>")
    )


@Client.on_message(filters.command(["vengine", "vstatus"]))
@force_sub
async def vengine_cmd(c, m):
    await m.reply(_engine_text(), reply_markup=KM([[KB("✕ Close", "close")]]))


@Client.on_callback_query(filters.regex(r"^vengine_cb$"))
async def vengine_cb(c, q):
    await q.answer()
    await safe_edit(q.message, _engine_text(), KM([[KB("✕ Close", "close")]]))
