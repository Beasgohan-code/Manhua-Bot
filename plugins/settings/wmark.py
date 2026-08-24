
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup as KM, InlineKeyboardButton as KB
from database.db import db
from plugins.settings.shared import edit_msg, user_states, _set, has_wmark, clear_wmark_url
@Client.on_callback_query(filters.regex("^menu_wm"))
async def wm_menu(c, q):
    uid = q.from_user.id
    enabled = await db.get_cfg(uid, "wmark_on", False)
    has_wm = await has_wmark(uid)
    status = "●" if enabled else "○"
    txt = (
        "<b>░ Watermark Settings</b>\n\n"
        f"<blockquote>"
        f"<b>Status:</b> {status}\n"
        f"<b>File:</b> {_set(has_wm)}"
        f"</blockquote>\n\n"
        "<i>Upload a transparent PNG to watermark your pages</i>"
    )
    btns = KM([
        [KB(f"↻ Toggle {status}", "t_wm")],
        [
            KB("⊕ Upload PNG", "ask_wm"),
            KB("⊖ Remove", "rem_wm")
        ],
        [KB("◂ Back", "open_main")]
    ])
    await edit_msg(c, q, txt, reply_markup=btns)
@Client.on_callback_query(filters.regex("^t_wm"))
async def t_wm(c, q):
    uid = q.from_user.id
    if not await has_wmark(uid):
        return await q.answer("⚠ Upload a watermark first!", show_alert=True)
    curr = await db.get_cfg(uid, "wmark_on", False)
    await db.set_cfg(uid, "wmark_on", not curr)
    await wm_menu(c, q)
@Client.on_callback_query(filters.regex("^ask_wm"))
async def ask_wm(c, q):
    uid = q.from_user.id
    user_states[uid] = "await_wm"
    await q.message.edit(
        "<b>⊕ Upload Watermark</b>\n\n"
        "<blockquote>"
        "Send a <b>transparent PNG</b> file\n"
        "Best: Bottom-right corner placement"
        "</blockquote>\n\n"
        "<i>Send image/file or /cancel</i>"
    )
@Client.on_callback_query(filters.regex("^rem_wm"))
async def rem_wm(c, q):
    uid = q.from_user.id
    await clear_wmark_url(uid)
    await db.set_cfg(uid, "wmark_enabled", False)
    await q.answer("Watermark removed.")
    await wm_menu(c, q)
