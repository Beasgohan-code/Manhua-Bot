
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup as KM, InlineKeyboardButton as KB
from database.db import db
from plugins.settings.shared import edit_msg, _set, user_states
@Client.on_callback_query(filters.regex("^menu_update"))
async def update_menu(c, q):
    uid = q.from_user.id
    update_cid = await db.get_cfg(uid, "update_cid")
    update_msg = await db.get_cfg(uid, "update_msg")
    update_sticker = await db.get_cfg(uid, "update_sticker")
    update_btn = await db.get_cfg(uid, "update_btn", "Read Now")
    update_btn_on = await db.get_cfg(uid, "update_btn_on", True)
    chan_listen = await db.get_cfg(uid, "chan_listen", False)
    cl_s = "●" if chan_listen else "○"
    txt = (
        "<b>░ Update Channel</b>\n\n"
        "<blockquote>"
        f"<b>Channel:</b> <code>{update_cid or 'Not set'}</code>\n"
        f"<b>Button:</b> <code>{update_btn}</code>\n"
        f"<b>Btn Enabled:</b> {'●' if update_btn_on else '○'}\n"
        f"<b>Sticker:</b> {_set(update_sticker)}\n"
        f"<b>Listener:</b> {cl_s}\n\n"
        f"<b>Message:</b>\n"
        f"<code>{update_msg or 'Default template'}</code>"
        "</blockquote>\n\n"
        "<i>Listener auto-detects manual uploads</i>"
    )
    btns = KM([
        [KB(f"⊕ Set Channel {_set(update_cid)}", "ask_u_cid")],
        [
            KB(f"⊕ Message {_set(update_msg)}", "ask_u_msg"),
            KB(f"⊕ Sticker {_set(update_sticker)}", "ask_u_sticker")
        ],
        [KB(f"⊕ Button Text", "ask_u_btn")],
        [KB(f"Update Button {'●' if update_btn_on else '○'}", "tog_u_btn_on")],
        [KB(f"Channel Listener {cl_s}", "tog_chan_listen")],
        [KB("⊖ Clear All", "c_u_all")],
        [KB("◂ Back", "open_main")]
    ])
    await edit_msg(c, q, txt, reply_markup=btns)
@Client.on_callback_query(filters.regex("^ask_u_cid"))
async def ask_u_cid(c, q):
    uid = q.from_user.id
    curr = await db.get_cfg(uid, "update_cid")
    user_states[uid] = "await_u_cid"
    txt = (
        "<b>⊕ Set Update Channel</b>\n\n"
        f"<b>Current:</b> <code>{curr or 'Not set'}</code>\n\n"
        "<blockquote>Send channel ID or forward a message from the channel</blockquote>\n\n"
        "<i>Or /cancel</i>"
    )
    await q.message.edit(txt)
@Client.on_callback_query(filters.regex("^ask_u_msg"))
async def ask_u_msg(c, q):
    uid = q.from_user.id
    curr = await db.get_cfg(uid, "update_msg")
    user_states[uid] = "await_u_msg"
    txt = (
        "<b>⊕ Set Notification Message</b>\n\n"
        "<b>Current:</b>\n"
        f"<code>{curr or 'Using default template'}</code>\n\n"
        "<b>Variables:</b>\n"
        "<code>{manga_title}</code> - Manga name\n"
        "<code>{chapter_num}</code> - Chapter number\n"
        "<code>{num}</code> - Chapter number (alias)\n"
        "<code>{chapter_link}</code> - Direct link to chapter\n"
        "<code>{channel_link}</code> - Link to channel\n\n"
        "<b>Examples:</b>\n\n"
        "<code>&lt;b&gt;&lt;blockquote&gt;{manga_title}&lt;/blockquote&gt;&lt;/b&gt;\n"
        "➥ &lt;a href=\"{chapter_link}\"&gt;Chapter {chapter_num}&lt;/a&gt; Uploaded!\n"
        "➥ &lt;a href=\"{channel_link}\"&gt;Read Now&lt;/a&gt;</code>\n\n"
        "<code>&lt;b&gt;[{manga_title}]&lt;/b&gt; Latest Chapter Uploaded - &lt;a href=\"{chapter_link}\"&gt;Download&lt;/a&gt;</code>\n\n"
        "<code>📚 {manga_title}\nChapter {chapter_num} is out!\n▸ {chapter_link}</code>\n\n"
        "<i>Send your format or /cancel</i>"
    )
    await q.message.edit(txt)
@Client.on_callback_query(filters.regex("^ask_u_sticker"))
async def ask_u_sticker(c, q):
    uid = q.from_user.id
    curr = await db.get_cfg(uid, "update_sticker")
    user_states[uid] = "await_u_sticker"
    txt = (
        "<b>⊕ Set Notification Sticker</b>\n\n"
        f"<b>Current:</b> <code>{'Set ◆' if curr else 'Not set ◇'}</code>\n\n"
        "<blockquote>Send a sticker to show after each update notification</blockquote>\n\n"
        "<i>Or /cancel</i>"
    )
    await q.message.edit(txt)
@Client.on_callback_query(filters.regex("^ask_u_btn"))
async def ask_u_btn(c, q):
    uid = q.from_user.id
    curr = await db.get_cfg(uid, "update_btn", "Read Now")
    user_states[uid] = "await_u_btn"
    txt = (
        "<b>⊕ Set Button Text</b>\n\n"
        f"<b>Current:</b> <code>{curr}</code>\n\n"
        "<blockquote>Text for the button on update notification</blockquote>\n\n"
        "<b>Examples:</b>\n"
        "<code>Read Now</code>\n"
        "<code>📖 Read Chapter</code>\n"
        "<code>Click Here</code>\n\n"
        "<i>Send text or /cancel</i>"
    )
    await q.message.edit(txt)
@Client.on_callback_query(filters.regex("^c_u_all"))
async def clear_u_all(c, q):
    uid = q.from_user.id
    await db.set_cfg(uid, "update_cid", None)
    await db.set_cfg(uid, "update_msg", None)
    await db.set_cfg(uid, "update_sticker", None)
    await db.set_cfg(uid, "update_btn", None)
    await db.set_cfg(uid, "chan_listen", False)
    await q.answer("Update settings cleared.")
    await update_menu(c, q)
@Client.on_callback_query(filters.regex("^tog_u_btn_on"))
async def tog_u_btn_on(c, q):
    uid = q.from_user.id
    curr = await db.get_cfg(uid, "update_btn_on", True)
    await db.set_cfg(uid, "update_btn_on", not curr)
    s = "●" if not curr else "○"
    await q.answer(f"Update Button: {s}")
    await update_menu(c, q)
@Client.on_callback_query(filters.regex("^tog_chan_listen"))
async def tog_chan_listen(c, q):
    uid = q.from_user.id
    curr = await db.get_cfg(uid, "chan_listen", False)
    await db.set_cfg(uid, "chan_listen", not curr)
    s = "●" if not curr else "○"
    await q.answer(f"Channel Listener: {s}")
    await update_menu(c, q)
