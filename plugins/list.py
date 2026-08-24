
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup as KM, InlineKeyboardButton as KB
from database.db import db
from services.util import clean_title
from config import Config
import logging
log = logging.getLogger(__name__)
PER_PAGE = 10
from plugins.fsub import force_sub
@Client.on_message(filters.command("list") & filters.private)
@force_sub
async def list_subs(c, m):
    uid = m.from_user.id
    await db.add_usr(uid)
    await show_list(m, uid, 0)
async def show_list(m, uid, page):
    subs = await db.get_subs(uid)
    if not subs:
        txt = "<blockquote>⚠ No subscriptions yet\nUse /search to find manga!</blockquote>"
        if hasattr(m, 'message'): await m.message.edit(txt)
        else: await m.reply(txt)
        return
    total = len(subs)
    start = page * PER_PAGE
    end = start + PER_PAGE
    curr = subs[start:end]
    txt = f"<b>▸ Subscriptions ({total})</b>\n"
    txt += f"<i>Page {page+1} │ {start+1}-{min(end, total)}</i>\n\n"
    txt += "<blockquote>"
    for i, s in enumerate(curr, start=start+1):
        sid = s.get('sid', '---')
        title = clean_title(s.get('title', 'Unknown'), 25)
        last_val = s.get('last', 'None')
        if isinstance(last_val, (int, float)):
            last = f"Ch {last_val}"
        else:
            last = str(last_val)[:15] if last_val else 'None'
        srcs = len(s.get('sources', []))
        if srcs == 0 and s.get('mid'): srcs = 1
        txt += f"<b>{i}. {title}</b>\n"
        txt += f"ID: <code>{sid}</code> │ Src: {srcs}\n\n"
    txt += "</blockquote>"
    btns = []
    nav = []
    if page > 0: nav.append(KB("◂ Prev", f"lst_{page-1}"))
    if end < total: nav.append(KB("Next ▸", f"lst_{page+1}"))
    if nav: btns.append(nav)
    btns.append([KB("✕ Close", "close")])
    if hasattr(m, 'message'): await m.message.edit(txt, reply_markup=KM(btns))
    else: await m.reply(txt, reply_markup=KM(btns))
@Client.on_callback_query(filters.regex(r"^lst_"))
async def lst_page(c, q):
    uid = q.from_user.id
    page = int(q.data.split("_")[1])
    await show_list(q, uid, page)
@Client.on_message(filters.command("del") & filters.private)
@force_sub
async def del_sub_cmd(c, m):
    uid = m.from_user.id
    if len(m.command) < 2:
        return await m.reply("<b>⚠ Missing ID</b>\n<blockquote>Usage: <code>/del ID</code>\nExample: <code>/del MAGA123456</code></blockquote>")
    sid = m.command[1].strip().upper()
    sub = await db.get_sub(uid, sid)
    if not sub:
        return await m.reply(f"<b>✗ Not Found</b>\n<blockquote>No subscription found with ID: <code>{sid}</code></blockquote>")
    await db.del_sub(uid, sid)
    await m.reply(
        f"<b>✓ Subscription Deleted</b>\n"
        f"<blockquote>ID: <code>{sid}</code>\n"
        f"Manga: {sub.get('title')}\n"
        f"Status: Tracking Stopped.</blockquote>"
    )
