
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup as KM, InlineKeyboardButton as KB
from services.mem import mem
from services.mgr import mgr
from services.util import clean_title
from database.db import db
import asyncio
import logging
log = logging.getLogger(__name__)
MS_PER_PAGE = 10
@Client.on_callback_query(filters.regex(r"^ms_start_"))
async def start_msearch(c, q):
    sid = q.data.replace("ms_start_", "")
    data = await db.get_cache(sid)
    if not data:
        return await q.answer("Session expired.", show_alert=True)
    query = data.get('q')
    if not query:
        return await q.answer("Invalid query.", show_alert=True)
    await q.message.edit(f"<blockquote>⋯ Searching ALL sources for: <b>{query}</b>...</blockquote>")
    try:
        res = await asyncio.wait_for(mgr.search(query), timeout=60)
        if not res:
            return await q.message.edit(
                f"<b>✗ No Results</b>\n\nNo manga found for <code>{query}</code>.",
                reply_markup=KM([[KB("◂ Sources", f"pg_{sid}_0")]])
            )
        res_key = f"ms_res_{sid}"
        mem.set(res_key, res)
        await show_ms_res(q.message, res_key, sid, 0)
    except asyncio.TimeoutError:
        await q.message.edit(
            "<b>⚠ Timeout</b>\n\nSearch took too long.",
            reply_markup=KM([[KB("◂ Back", f"pg_{sid}_0")]])
        )
    except Exception as e:
        log.error(f"Multi-search error: {e}")
        await q.message.edit(f"Error: {e}", reply_markup=KM([[KB("◂ Back", f"pg_{sid}_0")]]))
async def show_ms_res(msg, res_key, sid, page):
    res = mem.get(res_key)
    if not res:
        return await msg.edit("Results expired.", reply_markup=KM([[KB("◂ Back", f"pg_{sid}_0")]]))
    total = len(res)
    start = page * MS_PER_PAGE
    end = start + MS_PER_PAGE
    curr = res[start:end]
    btns = []
    for i, r in enumerate(curr):
        idx = start + i
        r_k = f"m_{sid}_ms_{idx}"
        r['sid'] = sid
        r['from_multi'] = True
        r['ms_page'] = page
        await db.set_cache(r_k, r)
        src = r.get('src', '?').replace('Webs', '')
        t = clean_title(r['title'], 25)
        btns.append([KB(f"{t} ({src})", f"sel_{r_k}")])
    nav = []
    if page > 0:
        nav.append(KB("[<] Prev", f"msp_{res_key}_{sid}_{page-1}"))
    if end < total:
        nav.append(KB(f"Next ({page+1}) ▸", f"msp_{res_key}_{sid}_{page+1}"))
    if nav: btns.append(nav)
    btns.append([KB("◂ Sources", f"pg_{sid}_0")])
    await msg.edit(
        f"<b>┌─ ALL SOURCES ─┐</b>\n"
        f"<i>Found {total} results</i>\n"
        f"└─────────────────",
        reply_markup=KM(btns)
    )
@Client.on_callback_query(filters.regex(r"^msp_"))
async def ms_page(c, q):
    try:
        p = q.data.split("_")
        page = int(p[-1])
        uid = q.from_user.id
        sid = f"sch_{uid}"
        k = f"ms_res_{sid}"
        await show_ms_res(q.message, k, sid, page)
    except Exception as e:
        log.error(f"MS Page err: {e}")
        await q.answer("Nav Error")
