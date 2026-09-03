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
from utils.tgui import (
    Btn, Keyboard, Card, table, quote, code as tcode, divider,
    PRIMARY, DANGER, SUCCESS, NOOP_CB,
)
from utils.richmsg import RichDoc, send_rich, rich_available, codespan

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
    try:
        from services.search_util import remember

        remember(uid, query, hits=len(results), kind=mode)
    except Exception:
        pass
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

    kb = Keyboard()
    for i, r in enumerate(chunk):
        idx = page * PER_PAGE + i
        tag = "🔞" if r.get("adult") else "🎬"
        n = 1 + len(r.get("also_on") or [])
        where = f"{n} sources" if n > 1 else (r.get("src_name") or "")[:14]
        kb.row(Btn(f"{tag} {r['title'][:32]} · {where}",
                   f"vpick_{skey}_{idx}", style=PRIMARY))

    kb.row(
        Btn("◂ Prev", f"vpg_{skey}_{page - 1}", disabled=page == 0),
        Btn(f"{page + 1}/{pages}", NOOP_CB, disabled=True, mark_disabled=False),
        Btn("Next ▸", f"vpg_{skey}_{page + 1}", disabled=page >= pages - 1),
    )
    kb.row(Btn("✕ Close", "close", style=DANGER))

    ok = len(stats.get("ok", []))
    failed = len(stats.get("failed", []))
    card = (
        Card("Video Search", "🎬")
        .field("Query", tcode(query))
        .field("Results", f"{tcode(len(results))} unique from {tcode(ok)} sources"
               + (f" · {tcode(failed)} failed" if failed else ""))
        .field("Page", tcode(f"{page + 1}/{pages}"))
        .divider()
        .note("Pick a title to list its episodes.")
    )
    await safe_edit(msg, card.build(), kb.render())


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

    kb = Keyboard()
    kb.grid(
        [Btn(str(ep.get("num") or page * EPS_PER_PAGE + i + 1),
             f"vep_{ekey}_{page * EPS_PER_PAGE + i}")
         for i, ep in enumerate(chunk)],
        per_row=5,
    )
    kb.row(
        Btn("◂", f"vep_pg_{ekey}_{page - 1}", disabled=page == 0),
        Btn(f"{page + 1}/{pages}", NOOP_CB, disabled=True, mark_disabled=False),
        Btn("▸", f"vep_pg_{ekey}_{page + 1}", disabled=page >= pages - 1),
    )
    kb.row(
        Btn("⚙ Quality", f"vq_{ekey}", style=PRIMARY),
        Btn(f"⬇️ Batch ({min(25, len(eps))})", f"vall_{ekey}", style=SUCCESS),
    )
    kb.row(Btn("✕ Close", "close", style=DANGER))

    quality = await vget(uid, "v_quality")
    mode = await vget(uid, "v_upload")
    card = (
        Card(series["title"][:48], "🎬")
        .table(
            ["Setting", "Value"],
            [
                ["Source", series.get("src_name") or series.get("src") or "?"],
                ["Episodes", len(eps)],
                ["Quality", vengine.quality_label(quality)],
                ["Upload as", mode],
            ],
        )
        .note("Tap an episode number to download.")
    )
    warn = _engine_warn()
    if warn:
        card.line(warn)
    await safe_edit(msg, card.build(), kb.render())


@Client.on_callback_query(filters.regex(r"^vep_pg_"))
async def vep_pg(c, q):
    ekey, page = split_cb(q.data, "vep_pg_")
    await q.answer()
    await _show_episodes(q.message, ekey, int(page), q.from_user.id)


@Client.on_callback_query(filters.regex(r"^vq_"))
async def vq_menu(c, q):
    ekey = q.data[len("vq_"):]
    curr = await vget(q.from_user.id, "v_quality")
    kb = Keyboard()
    kb.grid(
        [Btn(vengine.quality_label(x), f"vqs_{ekey}_{x}",
             style=SUCCESS if curr == x else None, disabled=curr == x)
         for x in ("480", "720", "1080", "best")],
        per_row=2,
    )
    kb.row(Btn("◂ Back", f"vep_pg_{ekey}_0", style=PRIMARY))
    card = (
        Card("Download Quality", "⚙")
        .field("Current", tcode(vengine.quality_label(curr)))
        .section("How it works",
                 "The engine picks the best stream at or below the selected "
                 "height, falling back automatically when unavailable.")
    )
    await safe_edit(q.message, card.build(), kb.render())


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

    card = Card("Video Sources", "🎬")
    card.table(["Anime Source", "Code"], [[s.name, s.sf] for s in sfw])
    if allow:
        card.table(["Hentai Source", "Code"], [[s.name, s.sf] for s in adult])
    else:
        card.line(f"🔞 <i>{len(adult)} adult sources hidden — /adult on</i>")
    card.note("/vsearch · /anime · /hentai · /vdl")

    kb = Keyboard().row(
        Btn("⚙ Engine", "vengine_cb", style=PRIMARY),
        Btn("🔞 Adult" if not allow else "🔞 Enabled", "noop_adult",
            disabled=allow, style=None if allow else DANGER),
        Btn("✕ Close", "close", style=DANGER),
    )
    await m.reply(card.build(), reply_markup=kb.render())


def _engine_doc() -> RichDoc:
    """Native rich version of the engine panel (falls back automatically)."""
    from utils.tgui import backend_report

    st = vengine.engine_status()
    ui = backend_report()
    ps = plugin_status()

    def mk(v):
        return "✅" if v else "❌"

    doc = RichDoc().heading("Download Engine", 1, "⚙")
    doc.table(
        ["Component", "St", "Purpose"],
        [
            ["yt-dlp", mk(st["yt_dlp"]), "extraction"],
            ["ffmpeg", mk(st["ffmpeg"]), "merge / metadata / subtitles"],
            ["aria2c", mk(st["aria2c"]), "accelerated segments"],
        ],
        align=["l", "c", "l"],
        caption="Media pipeline",
    )
    doc.heading("hanime-plugin", 2)
    if ps["installed"]:
        from services.hplugin import PLUGIN_SITES

        doc.bullets([PLUGIN_SITES[n] for n in ps["extractors"]])
    else:
        doc.paragraph(f"⚠️ inactive — {ps.get('error')}")
    doc.table(
        ["UI Backend", "St", "Detail"],
        [
            ["Kurigram", mk(ui["kurigram"]), "MTProto runtime"],
            ["Button styles", mk(ui["kurigram_styles"]), "primary/danger/success"],
            ["aiogram", mk(ui["aiogram"]), f"Bot API {ui['aiogram_bot_api']}"],
            ["Disabled buttons", mk(ui["native_disabled"]), "native"],
            ["Rich messages", mk(rich_available()["ok"]), rich_available()["reason"]],
        ],
        align=["l", "c", "l"],
    )
    if not st["ffmpeg"]:
        doc.details(
            "⚠️ ffmpeg missing — what breaks",
            "<p>No 1080p merge, no metadata, no MKV subtitles.</p>"
            "<pre>apt install ffmpeg aria2</pre>",
        )
    return doc


def _engine_text() -> str:
    from utils.tgui import backend_report

    st = vengine.engine_status()
    ui = backend_report()

    def mark(v):
        return "✅" if v else "❌"

    card = Card("Download Engine", "⚙")
    card.table(
        ["Component", "St", "Purpose"],
        [
            ["yt-dlp", mark(st["yt_dlp"]), "extraction"],
            ["ffmpeg", mark(st["ffmpeg"]), "merge/meta/subs"],
            ["aria2c", mark(st["aria2c"]), "fast segments"],
        ],
    )
    card.section("hanime-plugin", status_line())
    card.table(
        ["UI Backend", "St", "Detail"],
        [
            ["Kurigram", mark(ui["kurigram"]), "MTProto"],
            ["Styles", mark(ui["kurigram_styles"]), "primary/danger"],
            ["aiogram", mark(ui["aiogram"]), f"Bot API {ui['aiogram_bot_api']}"],
            ["Disabled", mark(ui["native_disabled"]), "native btn"],
        ],
    )
    if not st["ffmpeg"]:
        card.line("<i>Without ffmpeg: no 1080p merge, no MKV subtitles.</i>")
        card.line("<code>apt install ffmpeg aria2</code>")
    return card.build()


@Client.on_callback_query(filters.regex(r"^vsrc_open$"))
async def vsrc_open_cb(c, q):
    await q.answer()
    allow = await user_allows_adult(q.from_user.id)
    sfw = [s for s in vmgr.srcs.values() if not s.adult]
    adult = [s for s in vmgr.srcs.values() if s.adult]
    card = Card("Video Sources", "🎬")
    card.table(["Anime Source", "Code"], [[s.name, s.sf] for s in sfw])
    if allow:
        card.table(["Hentai Source", "Code"], [[s.name, s.sf] for s in adult])
    else:
        card.line(f"🔞 <i>{len(adult)} adult sources hidden — /adult on</i>")
    kb = Keyboard().row(
        Btn("⚙ Engine", "vengine_cb", style=PRIMARY),
        Btn("✕ Close", "close", style=DANGER),
    )
    await safe_edit(q.message, card.build(), kb.render())


@Client.on_callback_query(filters.regex(r"^audit_open$"))
async def audit_open_cb(c, q):
    await q.answer()
    from services.mgr import mgr as _mgr
    from sources.compat import is_legacy
    from utils.tgui import backend_report

    modern = sum(1 for s in _mgr.srcs.values() if callable(getattr(s, "get_manga", None)))
    legacy = sum(1 for s in _mgr.srcs.values() if is_legacy(s))
    st = vengine.engine_status()
    ui = backend_report()

    def mk(v):
        return "✅" if v else "❌"

    card = (
        Card("Health Check", "🩺")
        .table(
            ["Component", "Count", "St"],
            [
                ["Manga src", len(_mgr.srcs), mk(modern + legacy == len(_mgr.srcs))],
                ["  standard", modern, "—"],
                ["  legacy", legacy, "—"],
                ["Video src", len(vmgr.srcs), mk(bool(vmgr.srcs))],
            ],
        )
        .table(
            ["Engine", "St"],
            [
                ["yt-dlp", mk(st["yt_dlp"])],
                ["ffmpeg", mk(st["ffmpeg"])],
                ["aria2c", mk(st["aria2c"])],
                ["hanime-plugin", mk(plugin_status()["installed"])],
                ["aiogram UI", mk(ui["aiogram"])],
            ],
        )
    )
    kb = Keyboard().row(
        Btn("⚙ Engine", "vengine_cb", style=PRIMARY),
        Btn("✕ Close", "close", style=DANGER),
    )
    await safe_edit(q.message, card.build(), kb.render())


@Client.on_callback_query(filters.regex(r"^(ui_noop|noop_adult)$"))
async def ui_noop_cb(c, q):
    """Inert target for disabled buttons (MTProto has no `disabled` flag)."""
    await q.answer("Unavailable here", cache_time=1)


@Client.on_message(filters.command(["vengine", "vstatus"]))
@force_sub
async def vengine_cmd(c, m):
    kb = Keyboard().row(
        Btn("↻ Refresh", "vengine_cb", style=PRIMARY),
        Btn("✕ Close", "close", style=DANGER),
    )
    doc = _engine_doc()
    sent = await send_rich(m.chat.id, doc, reply_markup=kb, fallback_client=None)
    if sent is None:
        await m.reply(doc.fallback(), reply_markup=kb.render())


@Client.on_callback_query(filters.regex(r"^vengine_cb$"))
async def vengine_cb(c, q):
    await q.answer()
    kb = Keyboard().row(
        Btn("↻ Refresh", "vengine_cb", style=PRIMARY),
        Btn("✕ Close", "close", style=DANGER),
    )
    await safe_edit(q.message, _engine_text(), kb.render())


@Client.on_message(filters.command(["vhistory", "recent"]))
@force_sub
async def vhistory_cmd(c, m):
    """Recent searches, one tap to run again."""
    from services.search_util import history

    entries = history(m.from_user.id)
    if not entries:
        return await m.reply(
            "<b>🕘 Recent searches</b>\n\n"
            "<blockquote>Nothing yet — try <code>/vsearch frieren</code>.</blockquote>"
        )
    import time as _t

    def ago(ts):
        d = int(_t.time() - ts)
        if d < 60:
            return f"{d}s"
        if d < 3600:
            return f"{d // 60}m"
        if d < 86400:
            return f"{d // 3600}h"
        return f"{d // 86400}d"

    card = Card("Recent Searches", "🕘").table(
        ["Query", "Hits", "When"],
        [[e["query"], e["hits"], ago(e["ts"])] for e in entries],
        align=["l", "r", "r"],
    )
    kb = Keyboard()
    for e in entries[:6]:
        kb.row(Btn(f"⌕ {e['query'][:30]}", f"vre_{e['query'][:40]}", style=PRIMARY))
    kb.row(Btn("🧹 Clear", "vhist_clear", style=DANGER),
           Btn("✕ Close", "close", style=DANGER))
    await m.reply(card.build(), reply_markup=kb.render())


@Client.on_callback_query(filters.regex(r"^vre_"))
async def vhistory_repeat(c, q):
    query = q.data[len("vre_"):]
    await q.answer(f"Searching {query}…")

    class _M:
        from_user = q.from_user
        chat = q.message.chat

        async def reply(self, text, reply_markup=None):
            return await c.send_message(q.message.chat.id, text,
                                        reply_markup=reply_markup)

    await _do_search(c, _M(), query, "all")


@Client.on_callback_query(filters.regex(r"^vhist_clear$"))
async def vhistory_clear(c, q):
    from services.search_util import clear_history

    n = clear_history(q.from_user.id)
    await q.answer(f"Cleared {n}", show_alert=True)
    try:
        await q.message.edit("<blockquote>🕘 Search history cleared.</blockquote>")
    except Exception:
        pass


# ------------------------------------------------------------------ /audit
@Client.on_message(filters.command(["audit", "healthcheck"]))
@force_sub
async def audit_cmd(c, m):
    """Live self-check: sources, interfaces, engine and UI backends."""
    from services.mgr import mgr
    from sources.compat import is_legacy
    from utils.tgui import backend_report

    modern = sum(1 for s in mgr.srcs.values() if callable(getattr(s, "get_manga", None)))
    legacy = sum(1 for s in mgr.srcs.values() if is_legacy(s))
    broken = len(mgr.srcs) - modern - legacy
    sfw = sum(1 for s in vmgr.srcs.values() if not s.adult)
    st = vengine.engine_status()
    ui = backend_report()

    def mk(v):
        return "✅" if v else "❌"

    card = (
        Card("Health Check", "🩺")
        .table(
            ["Component", "Count", "St"],
            [
                ["Manga src", len(mgr.srcs), mk(broken == 0)],
                ["  modern", modern, "—"],
                ["  legacy", legacy, "—"],
                ["Video src", len(vmgr.srcs), mk(len(vmgr.srcs) > 0)],
                ["  sfw/adult", f"{sfw}/{len(vmgr.srcs) - sfw}", "—"],
            ],
        )
        .table(
            ["Engine", "St"],
            [
                ["yt-dlp", mk(st["yt_dlp"])],
                ["ffmpeg", mk(st["ffmpeg"])],
                ["aria2c", mk(st["aria2c"])],
                ["hanime-plugin", mk(plugin_status()["installed"])],
                ["aiogram UI", mk(ui["aiogram"])],
            ],
        )
        .note("Run <code>python tools/audit.py</code> for the full report.")
    )
    kb = Keyboard().row(
        Btn("⚙ Engine", "vengine_cb", style=PRIMARY),
        Btn("✕ Close", "close", style=DANGER),
    )
    await m.reply(card.build(), reply_markup=kb.render())
