# Manhua-Bot - anime / hentai video commands
#
#   /anime  <name>   search SFW anime sources
#   /hentai <name>   search adult sources (requires /adult on)
#   /vsearch <name>  search everything the user is allowed to see
#   /vdl <source> <id|url> [ep|start-end]
#   /vsources        list loaded video sites

from __future__ import annotations

import asyncio
import logging
import re

from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup as KM, InlineKeyboardButton as KB

from plugins.adult_cmd import user_allows_adult
from plugins.fsub import force_sub
from services.vmgr import vmgr
from services.video_dl import HAS_YTDLP, download_and_send_video, vget
from utils.ui import RichMessage, code

log = logging.getLogger(__name__)

# in-memory result cache: token -> payload (search results / series)
_cache: dict = {}
_seq = [0]


def _put(payload) -> str:
    _seq[0] += 1
    token = f"v{_seq[0]}"
    _cache[token] = payload
    if len(_cache) > 400:  # cheap bound
        for old in list(_cache)[:100]:
            _cache.pop(old, None)
    return token


def parse_eps(token: str):
    token = (token or "").strip()
    m = re.match(r"^(\d+)\s*-\s*(\d+)$", token)
    if m:
        a, b = int(m.group(1)), int(m.group(2))
        if a > b:
            a, b = b, a
        return [str(i) for i in range(a, b + 1)]
    return [token] if token else []


def _no_ytdlp_msg() -> str:
    return (
        "<b>⚠️ yt-dlp is missing</b>\n\n"
        "<blockquote>Video download needs yt-dlp (and ffmpeg for merging "
        "and metadata).\n\n"
        "<code>pip install -r requirements.txt</code>\n"
        "<code>apt install ffmpeg</code></blockquote>"
    )


# ------------------------------------------------------------------ search
async def _do_search(c, m, query: str, mode: str):
    uid = m.from_user.id
    allow_adult = await user_allows_adult(uid)

    if mode == "adult" and not allow_adult:
        return await m.reply(
            "🔞 Adult sources are locked. Enable them with <code>/adult on</code> first."
        )

    status = await m.reply(f"<blockquote>⌕ Searching <code>{query}</code>…</blockquote>")
    results = await vmgr.search(query, allow_adult=(mode != "sfw" and allow_adult))

    if mode == "sfw":
        results = [r for r in results if not r.get("adult")]
    elif mode == "adult":
        results = [r for r in results if r.get("adult")]

    if not results:
        return await status.edit(
            f"<blockquote>⚠ No results for <code>{query}</code></blockquote>"
        )

    results = results[:40]
    token = _put(results)

    rows = []
    for i, r in enumerate(results[:20]):
        tag = "🔞 " if r.get("adult") else ""
        label = f"{tag}{r['title'][:32]} · {r.get('src_name', '')[:12]}"
        rows.append([KB(label, f"vpick_{token}_{i}")])
    rows.append([KB("✕ Close", "close")])

    text = (
        RichMessage("Video Search", "🎬")
        .kv([("Query", code(query)), ("Results", code(len(results)))])
        .tip("Pick a title to list its episodes.")
        .build()
    )
    await status.edit(text, reply_markup=KM(rows))


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
            "<b>🎬 Video search</b>\n\n<blockquote>"
            "<code>/vsearch &lt;name&gt;</code> — all allowed sources\n"
            "<code>/anime</code> — SFW only · <code>/hentai</code> — adult only"
            "</blockquote>"
        )
    await _do_search(c, m, " ".join(m.command[1:]), "all")


# ---------------------------------------------------------------- episodes
@Client.on_callback_query(filters.regex(r"^vpick_"))
async def vpick(c, q):
    _, token, idx = q.data.split("_", 2)
    results = _cache.get(token)
    if not results:
        return await q.answer("Results expired — search again.", show_alert=True)
    item = results[int(idx)]

    await q.answer("Loading episodes…")
    try:
        await q.message.edit(
            f"<blockquote>⋯ Loading <b>{item['title'][:60]}</b></blockquote>"
        )
    except Exception:
        pass

    series = await vmgr.get_series(item["src"], item.get("id") or item.get("url"))
    if not series:
        return await q.message.edit("<blockquote>⚠ Could not load that title.</blockquote>")

    series.setdefault("title", item["title"])
    episodes = series.get("episodes") or []
    if not episodes:
        return await q.message.edit("<blockquote>⚠ No episodes found.</blockquote>")

    stoken = _put(series)
    rows, row = [], []
    for i, ep in enumerate(episodes[:60]):
        row.append(KB(ep.get("num") or str(i + 1), f"vep_{stoken}_{i}"))
        if len(row) == 5:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([KB("⬇️ All episodes", f"vall_{stoken}"), KB("✕ Close", "close")])

    text = (
        RichMessage(series["title"][:60], "🎬")
        .kv(
            [
                ("Source", code(series.get("src_name") or series.get("src"))),
                ("Episodes", code(len(episodes))),
                ("Quality", code(await vget(q.from_user.id, "v_quality"))),
            ]
        )
        .tip("Tap an episode number to download. Configure output in /usettings.")
        .build()
    )
    await q.message.edit(text, reply_markup=KM(rows))


async def _run_downloads(c, chat_id, uid, series, episodes, status):
    ok = fail = 0
    for i, ep in enumerate(episodes, 1):
        try:
            await status.edit(
                f"<blockquote>⬇️ {i}/{len(episodes)} — "
                f"Episode <code>{ep.get('num')}</code></blockquote>"
            )
            await download_and_send_video(c, chat_id, uid, series, ep, status_msg=status)
            ok += 1
        except Exception as exc:
            log.error(f"[VDL] {series.get('title')} E{ep.get('num')}: {exc}")
            fail += 1
            await c.send_message(
                chat_id,
                f"⚠ Episode <code>{ep.get('num')}</code> failed — {str(exc)[:120]}",
            )
    try:
        await status.edit(
            f"<b>Done</b> — ok <code>{ok}</code> · failed <code>{fail}</code>"
        )
    except Exception:
        pass


@Client.on_callback_query(filters.regex(r"^vep_"))
async def vep(c, q):
    if not HAS_YTDLP:
        return await q.message.reply(_no_ytdlp_msg())
    _, token, idx = q.data.split("_", 2)
    series = _cache.get(token)
    if not series:
        return await q.answer("Expired — search again.", show_alert=True)
    ep = (series.get("episodes") or [])[int(idx)]
    await q.answer("Queued")
    status = await q.message.reply("<blockquote>⋯ Preparing download…</blockquote>")
    asyncio.create_task(
        _run_downloads(c, q.message.chat.id, q.from_user.id, series, [ep], status)
    )


@Client.on_callback_query(filters.regex(r"^vall_"))
async def vall(c, q):
    if not HAS_YTDLP:
        return await q.message.reply(_no_ytdlp_msg())
    series = _cache.get(q.data.split("_", 1)[1])
    if not series:
        return await q.answer("Expired — search again.", show_alert=True)
    episodes = (series.get("episodes") or [])[:25]
    await q.answer(f"Queued {len(episodes)} episodes")
    status = await q.message.reply(
        f"<blockquote>⋯ Queued <code>{len(episodes)}</code> episodes…</blockquote>"
    )
    asyncio.create_task(
        _run_downloads(c, q.message.chat.id, q.from_user.id, series, episodes, status)
    )


# --------------------------------------------------------------------- /vdl
@Client.on_message(filters.command(["vdl", "vdownload"]))
@force_sub
async def vdl_cmd(c, m):
    if not HAS_YTDLP:
        return await m.reply(_no_ytdlp_msg())
    args = m.command[1:]
    if len(args) < 2:
        return await m.reply(
            "<b>⬇️ Video download</b>\n\n<blockquote>"
            "<code>/vdl &lt;source&gt; &lt;id_or_url&gt; [ep|start-end]</code>\n\n"
            "<code>/vdl hanime some-slug</code>\n"
            "<code>/vdl pahe &lt;session&gt; 1-5</code>\n"
            "</blockquote>See <code>/vsources</code> for names."
        )

    uid = m.from_user.id
    src = vmgr.get(args[0])
    if not src:
        return await m.reply(f"<blockquote>⚠ Unknown source: <code>{args[0]}</code></blockquote>")
    if src.adult and not await user_allows_adult(uid):
        return await m.reply("🔞 Adult source — enable with <code>/adult on</code> first.")

    status = await m.reply(f"<blockquote>⋯ Loading <code>{src.name}</code>…</blockquote>")
    series = await vmgr.get_series(vmgr.key_of(src), args[1])
    if not series:
        return await status.edit("<blockquote>⚠ Title not found.</blockquote>")

    episodes = series.get("episodes") or []
    if len(args) > 2:
        wanted = set(parse_eps(args[2]))
        picked = [e for e in episodes if str(e.get("num")) in wanted]
        episodes = picked or episodes[:1]
    else:
        episodes = episodes[:1]

    if not episodes:
        return await status.edit("<blockquote>⚠ No matching episodes.</blockquote>")

    await _run_downloads(c, m.chat.id, uid, series, episodes[:25], status)


# ---------------------------------------------------------------- /vsources
@Client.on_message(filters.command(["vsources", "vsites"]))
@force_sub
async def vsources_cmd(c, m):
    allow = await user_allows_adult(m.from_user.id)
    sfw = [s for s in vmgr.srcs.values() if not s.adult]
    adult = [s for s in vmgr.srcs.values() if s.adult]

    body = "<b>Anime</b>\n" + "\n".join(
        f"• {s.name} — <code>{s.sf}</code>" for s in sfw
    )
    if allow:
        body += "\n\n<b>🔞 Hentai</b>\n" + "\n".join(
            f"• {s.name} — <code>{s.sf}</code>" for s in adult
        )
    else:
        body += f"\n\n🔞 <i>{len(adult)} adult sources hidden — /adult on</i>"

    await m.reply(
        "<b>🎬 Video Sources</b>\n\n<blockquote>" + body + "</blockquote>\n\n"
        "<i>Use /vsearch, /anime, /hentai or /vdl &lt;source&gt; …</i>",
        reply_markup=KM([[KB("✕ Close", "close")]]),
    )
