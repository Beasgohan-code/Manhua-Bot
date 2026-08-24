
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup as KM, InlineKeyboardButton as KB
from database.db import db
from plugins.settings.shared import edit_msg, _set, user_states
@Client.on_callback_query(filters.regex("^menu_style"))
async def style_menu(c, q):
    uid = q.from_user.id
    curr_cap = await db.get_cfg(uid, "caption")
    curr_fname = await db.get_cfg(uid, "fname", "{title} - {chap_no}")
    cap_set = bool(curr_cap)
    fname_set = curr_fname != "{title} - {chap_no}"
    txt = (
        "<b>░ Post Styling</b>\n\n"
        "<blockquote>"
        f"<b>Caption:</b> {_set(cap_set)}\n"
        f"<code>{curr_cap or 'Default'}</code>\n\n"
        f"<b>Filename:</b>\n"
        f"<code>{curr_fname}</code>"
        "</blockquote>"
    )
    btns = KM([
        [
            KB(f"⊕ Caption {_set(cap_set)}", "ask_cap"),
            KB(f"⊕ Filename {_set(fname_set)}", "ask_fname")
        ],
        [
            KB("▸ Preview", "v_style_cap"),
            KB("⊖ Reset", "r_style")
        ],
        [KB("◂ Back", "open_main")]
    ])
    await edit_msg(c, q, txt, reply_markup=btns)
@Client.on_callback_query(filters.regex("^ask_cap"))
async def ask_cap(c, q):
    uid = q.from_user.id
    curr = await db.get_cfg(uid, "caption")
    user_states[uid] = "await_cap"
    txt = (
        "<b>⊕ Set Caption</b>\n\n"
        "<b>Current:</b>\n"
        f"<code>{curr or 'Default template'}</code>\n\n"
        "<b>Variables:</b>\n"
        "<code>{title}</code> - Manga name\n"
        "<code>{chapter}</code> - Chapter title\n"
        "<code>{num}</code> - Chapter number\n"
        "<code>{link}</code> - Direct link\n\n"
        "<b>Examples:</b>\n\n"
        "<code>&lt;b&gt;&lt;blockquote&gt;{title}&lt;/blockquote&gt;&lt;/b&gt;\n"
        "➥ {chapter}\n"
        "➥ &lt;a href=\"{link}\"&gt;Read Now&lt;/a&gt;</code>\n\n"
        "<code>&lt;b&gt;[{title}]&lt;/b&gt; {chapter} - &lt;a href=\"{link}\"&gt;Download&lt;/a&gt;</code>\n\n"
        "<code>📚 {title}\n📖 {chapter}\n▸ {link}</code>\n\n"
        "<i>Send your format or /cancel</i>"
    )
    await q.message.edit(txt)
@Client.on_callback_query(filters.regex("^ask_fname"))
async def ask_fname(c, q):
    uid = q.from_user.id
    curr = await db.get_cfg(uid, "fname", "{title} - {chap_no}")
    user_states[uid] = "await_fname"
    txt = (
        "<b>⊕ Set Filename</b>\n\n"
        "<b>Current:</b>\n"
        f"<code>{curr}</code>\n\n"
        "<b>Variables:</b>\n"
        "<code>{title}</code> - Manga name\n"
        "<code>{chapter}</code> - Full chapter title\n"
        "<code>{chap_no}</code> - Chapter number only\n"
        "<code>{num}</code> - Chapter number only (alias)\n\n"
        "<b>Examples:</b>\n"
        "<code>{title} - {chap_no}</code>\n"
        "<code>[MC] [{chap_no}] {title}</code>\n"
        "<code>{title} Chapter {chap_no}</code>\n"
        "<code>{chap_no} - {title}</code>\n\n"
        "<i>Send format or /cancel</i>"
    )
    await q.message.edit(txt)
@Client.on_callback_query(filters.regex("^r_style"))
async def reset_style(c, q):
    uid = q.from_user.id
    await db.set_cfg(uid, "caption", None)
    await db.set_cfg(uid, "fname", "{title} - {chap_no}")
    await q.answer("Reset to defaults.")
    await style_menu(c, q)
@Client.on_callback_query(filters.regex("^v_style_cap"))
async def view_style(c, q):
    uid = q.from_user.id
    cap = await db.get_cfg(uid, "caption", "{title} - {chapter}")
    sample = cap.format(title="Manga Title", chapter="Chapter One", link="https://t.me/...", num="001")
    await q.message.reply(f"<b>[PREVIEW] Caption:</b>\n\n{sample}")
    await q.answer()
