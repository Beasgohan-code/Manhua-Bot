
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup as KM, InlineKeyboardButton as KB
from database.db import db
from config import Config
from plugins.settings.shared import has_wmark, has_img
import logging
log = logging.getLogger(__name__)
_editing = {}
_edit_states = {}
def _s(val):
    return "●" if val else "○"
def _set(val):
    return "◆" if val else "◇"
@Client.on_message(filters.command("usettings") & filters.user(Config.OWNER_ID))
async def usettings_cmd(c, m):
    args = m.command[1:]
    if not args:
        users = await db.get_all_users()
        if not users:
            return await m.reply("<b>No users found.</b>")
        txt = "<b>░ User Settings</b>\n\n<blockquote>Recent users:</blockquote>\n\n"
        for u in users[:15]:
            uid = u.get('id')
            txt += f"<code>{uid}</code>\n"
        txt += "\n<i>Usage: <code>/usettings &lt;user_id&gt;</code></i>"
        return await m.reply(txt)
    try:
        target_uid = int(args[0])
    except:
        return await m.reply("<b>✗ Invalid user ID</b>")
    user = await db.get_usr(target_uid)
    if not user:
        return await m.reply(f"<b>✗ User {target_uid} not found</b>")
    _editing[m.from_user.id] = target_uid
    await show_user_settings(m, target_uid)
async def show_user_settings(msg, uid, edit=False):
    update_cid = await db.get_cfg(uid, "update_cid")
    update_msg = await db.get_cfg(uid, "update_msg")
    update_sticker = await db.get_cfg(uid, "update_sticker")
    update_btn = await db.get_cfg(uid, "update_btn", "Read Now")
    chan_listen = await db.get_cfg(uid, "chan_listen", False)
    update_btn_on = await db.get_cfg(uid, "update_btn_on", True)
    caption = await db.get_cfg(uid, "caption")
    fname = await db.get_cfg(uid, "fname", "{title} - {chap_no}")
    monitoring = await db.get_cfg(uid, "mon", True)
    file_type = await db.get_cfg(uid, "ftype", "pdf")
    quality = await db.get_cfg(uid, "quality", 85)
    interval = await db.get_cfg(uid, "interval", 15)
    wmark_enabled = await db.get_cfg(uid, "wmark_on", False)
    w_set = await has_wmark(uid)
    p_first_set = await has_img(uid, "first")
    p_last_set = await has_img(uid, "last")
    dump_cid = await db.get_cfg(uid, "dump_cid")
    subs = await db.get_subs(uid)
    sub_count = len(subs) if subs else 0
    txt = (
        f"<b>░ User Settings</b>\n"
        f"<b>ID:</b> <code>{uid}</code>\n\n"
        "<blockquote>"
        f"<b>▸ General</b>\n"
        f"Monitoring: {_s(monitoring)}\n"
        f"File Type: <code>{file_type}</code>  (pdf/cbz/links)\n"
        f"Quality: <code>{quality}%</code>\n"
        f"Interval: <code>{interval}m</code>\n"
        f"Subs: <code>{sub_count}</code>\n"
        "</blockquote>\n\n"
        "<blockquote>"
        f"<b>▸ Update Channel</b>\n"
        f"Channel: <code>{update_cid or 'Not set'}</code>\n"
        f"Button: <code>{update_btn}</code>\n"
        f"Sticker: {_set(update_sticker)}\n"
        f"Btn Enabled: {_s(update_btn_on)}\n"
        f"Listener: {_s(chan_listen)}\n"
        f"Message: {_set(update_msg)}\n"
        "</blockquote>\n\n"
        "<blockquote>"
        f"<b>▸ Styling</b>\n"
        f"Caption: {_set(caption)}\n"
        f"Filename: <code>{fname}</code>\n"
        "</blockquote>\n\n"
        "<blockquote>"
        f"<b>▸ Watermark</b>\n"
        f"Enabled: {_s(wmark_enabled)}\n"
        f"Image: {_set(w_set)}\n"
        "</blockquote>\n\n"
        "<blockquote>"
        f"<b>▸ Promos</b>\n"
        f"First: {_set(p_first_set)}\n"
        f"Last: {_set(p_last_set)}\n"
        f"Dump: <code>{dump_cid or 'Not set'}</code>\n"
        "</blockquote>"
    )
    btns = KM([
        [
            KB("▸ General", f"ue_gen_{uid}"),
            KB("▸ Update", f"ue_upd_{uid}")
        ],
        [
            KB("▸ Style", f"ue_style_{uid}"),
            KB("▸ Wmark", f"ue_wmark_{uid}")
        ],
        [
            KB("▸ Promos", f"ue_promo_{uid}"),
            KB("▸ Subs", f"ue_subs_{uid}")
        ],
        [
            KB("⊖ Reset All", f"ue_reset_{uid}"),
            KB("✕ Close", "close")
        ]
    ])
    if edit and hasattr(msg, 'edit'):
        await msg.edit(txt, reply_markup=btns)
    elif hasattr(msg, 'message'):
        await msg.message.edit(txt, reply_markup=btns)
    else:
        await msg.reply(txt, reply_markup=btns)
@Client.on_callback_query(filters.regex(r"^ue_gen_") & filters.user(Config.OWNER_ID))
async def ue_gen(c, q):
    uid = int(q.data.replace("ue_gen_", ""))
    monitoring = await db.get_cfg(uid, "mon", True)
    file_type = await db.get_cfg(uid, "ftype", "pdf")
    quality = await db.get_cfg(uid, "quality", 85)
    interval = await db.get_cfg(uid, "interval", 15)
    txt = (
        f"<b>▸ General Settings</b>\n"
        f"<b>User:</b> <code>{uid}</code>\n\n"
        "<blockquote>"
        f"Monitoring: {_s(monitoring)}\n"
        f"File Type: <code>{file_type}</code>\n"
        f"Quality: <code>{quality}%</code>\n"
        f"Interval: <code>{interval}m</code>"
        "</blockquote>"
    )
    btns = KM([
        [KB(f"Monitoring {_s(monitoring)}", f"ut_mon_{uid}")],
        [
            KB("PDF", f"ut_ftype_{uid}_pdf"),
            KB("CBZ", f"ut_ftype_{uid}_cbz"),
            KB("Links", f"ut_ftype_{uid}_links"),
        ],
        [
            KB("⊖", f"ut_qual_{uid}_-10"),
            KB(f"Quality: {quality}%", "noop"),
            KB("⊕", f"ut_qual_{uid}_+10")
        ],
        [
            KB("⊖", f"ut_int_{uid}_-5"),
            KB(f"Interval: {interval}m", "noop"),
            KB("⊕", f"ut_int_{uid}_+5")
        ],
        [KB("◂ Back", f"ue_back_{uid}")]
    ])
    await q.message.edit(txt, reply_markup=btns)
@Client.on_callback_query(filters.regex(r"^ut_mon_") & filters.user(Config.OWNER_ID))
async def ut_mon(c, q):
    uid = int(q.data.replace("ut_mon_", ""))
    curr = await db.get_cfg(uid, "mon", True)
    await db.set_cfg(uid, "mon", not curr)
    await q.answer(f"Monitoring: {_s(not curr)}")
    await ue_gen(c, q)
@Client.on_callback_query(filters.regex(r"^ut_ftype_") & filters.user(Config.OWNER_ID))
async def ut_ftype(c, q):
    parts = q.data.split("_")
    uid = int(parts[2])
    ftype = parts[3]
    await db.set_cfg(uid, "ftype", ftype)
    await q.answer(f"File type: {ftype}")
    await ue_gen(c, q)
@Client.on_callback_query(filters.regex(r"^ut_qual_") & filters.user(Config.OWNER_ID))
async def ut_qual(c, q):
    parts = q.data.split("_")
    uid = int(parts[2])
    delta = int(parts[3])
    curr = await db.get_cfg(uid, "quality", 85)
    new_val = max(10, min(100, curr + delta))
    await db.set_cfg(uid, "quality", new_val)
    await q.answer(f"Quality: {new_val}%")
    await ue_gen(c, q)
@Client.on_callback_query(filters.regex(r"^ut_int_") & filters.user(Config.OWNER_ID))
async def ut_int(c, q):
    parts = q.data.split("_")
    uid = int(parts[2])
    delta = int(parts[3])
    curr = await db.get_cfg(uid, "interval", 15)
    new_val = max(5, min(120, curr + delta))
    await db.set_cfg(uid, "interval", new_val)
    await q.answer(f"Interval: {new_val}m")
    await ue_gen(c, q)
@Client.on_callback_query(filters.regex(r"^ue_upd_") & filters.user(Config.OWNER_ID))
async def ue_upd(c, q):
    uid = int(q.data.replace("ue_upd_", ""))
    update_cid = await db.get_cfg(uid, "update_cid")
    update_msg = await db.get_cfg(uid, "update_msg")
    update_btn = await db.get_cfg(uid, "update_btn", "Read Now")
    update_sticker = await db.get_cfg(uid, "update_sticker")
    update_btn_on = await db.get_cfg(uid, "update_btn_on", True)
    chan_listen = await db.get_cfg(uid, "chan_listen", False)
    txt = (
        f"<b>▸ Update Settings</b>\n"
        f"<b>User:</b> <code>{uid}</code>\n\n"
        "<blockquote>"
        f"Channel: <code>{update_cid or 'Not set'}</code>\n"
        f"Button: <code>{update_btn}</code>\n"
        f"Sticker: {_set(update_sticker)}\n"
        f"Btn Enabled: {_s(update_btn_on)}\n"
        f"Listener: {_s(chan_listen)}\n\n"
        f"Message:\n<code>{update_msg or 'Default'}</code>"
        "</blockquote>"
    )
    btns = KM([
        [KB(f"⊕ Channel {_set(update_cid)}", f"ua_ucid_{uid}")],
        [KB(f"⊕ Button Text", f"ua_ubtn_{uid}")],
        [KB(f"⊕ Message {_set(update_msg)}", f"ua_umsg_{uid}")],
        [KB(f"Btn Toggle {_s(update_btn_on)}", f"ut_ubtn_on_{uid}")],
        [KB(f"Listener {_s(chan_listen)}", f"ut_listen_{uid}")],
        [
            KB("⊖ Clear Sticker", f"uc_ustick_{uid}"),
            KB("⊖ Clear Msg", f"uc_umsg_{uid}")
        ],
        [KB("◂ Back", f"ue_back_{uid}")]
    ])
    await q.message.edit(txt, reply_markup=btns)
@Client.on_callback_query(filters.regex(r"^ut_listen_") & filters.user(Config.OWNER_ID))
async def ut_listen(c, q):
    uid = int(q.data.replace("ut_listen_", ""))
    curr = await db.get_cfg(uid, "chan_listen", False)
    await db.set_cfg(uid, "chan_listen", not curr)
    await q.answer(f"Listener: {_s(not curr)}")
    await ue_upd(c, q)
@Client.on_callback_query(filters.regex(r"^ut_ubtn_on_") & filters.user(Config.OWNER_ID))
async def ut_ubtn_on(c, q):
    uid = int(q.data.replace("ut_ubtn_on_", ""))
    curr = await db.get_cfg(uid, "update_btn_on", True)
    await db.set_cfg(uid, "update_btn_on", not curr)
    await q.answer(f"Button: {_s(not curr)}")
    await ue_upd(c, q)
@Client.on_callback_query(filters.regex(r"^uc_ustick_") & filters.user(Config.OWNER_ID))
async def uc_ustick(c, q):
    uid = int(q.data.replace("uc_ustick_", ""))
    await db.set_cfg(uid, "update_sticker", None)
    await q.answer("Sticker cleared")
    await ue_upd(c, q)
@Client.on_callback_query(filters.regex(r"^uc_umsg_") & filters.user(Config.OWNER_ID))
async def uc_umsg(c, q):
    uid = int(q.data.replace("uc_umsg_", ""))
    await db.set_cfg(uid, "update_msg", None)
    await q.answer("Message cleared")
    await ue_upd(c, q)
@Client.on_callback_query(filters.regex(r"^ua_ucid_") & filters.user(Config.OWNER_ID))
async def ua_ucid(c, q):
    uid = int(q.data.replace("ua_ucid_", ""))
    _editing[q.from_user.id] = uid
    _edit_states[q.from_user.id] = "await_ucid"
    await q.message.edit(
        f"<b>⊕ Set Update Channel</b>\n"
        f"<b>User:</b> <code>{uid}</code>\n\n"
        "<blockquote>Send channel ID</blockquote>\n\n"
        "<i>Or /cancel</i>"
    )
@Client.on_callback_query(filters.regex(r"^ua_ubtn_") & filters.user(Config.OWNER_ID))
async def ua_ubtn(c, q):
    uid = int(q.data.replace("ua_ubtn_", ""))
    _editing[q.from_user.id] = uid
    _edit_states[q.from_user.id] = "await_ubtn"
    curr = await db.get_cfg(uid, "update_btn", "Read Now")
    await q.message.edit(
        f"<b>⊕ Set Button Text</b>\n"
        f"<b>User:</b> <code>{uid}</code>\n\n"
        f"<b>Current:</b> <code>{curr}</code>\n\n"
        "<blockquote>Send new button text</blockquote>\n\n"
        "<i>Or /cancel</i>"
    )
@Client.on_callback_query(filters.regex(r"^ua_umsg_") & filters.user(Config.OWNER_ID))
async def ua_umsg(c, q):
    uid = int(q.data.replace("ua_umsg_", ""))
    _editing[q.from_user.id] = uid
    _edit_states[q.from_user.id] = "await_umsg"
    await q.message.edit(
        f"<b>⊕ Set Update Message</b>\n"
        f"<b>User:</b> <code>{uid}</code>\n\n"
        "<b>Variables:</b>\n"
        "<code>{manga_title}</code>, <code>{chapter_num}</code>\n"
        "<code>{chapter_link}</code>, <code>{channel_link}</code>\n\n"
        "<blockquote>Send message template</blockquote>\n\n"
        "<i>Or /cancel</i>"
    )
@Client.on_callback_query(filters.regex(r"^ue_style_") & filters.user(Config.OWNER_ID))
async def ue_style(c, q):
    uid = int(q.data.replace("ue_style_", ""))
    caption = await db.get_cfg(uid, "caption")
    fname = await db.get_cfg(uid, "fname", "{title} - {chap_no}")
    txt = (
        f"<b>▸ Style Settings</b>\n"
        f"<b>User:</b> <code>{uid}</code>\n\n"
        "<blockquote>"
        f"Caption:\n<code>{caption or 'Default'}</code>\n\n"
        f"Filename:\n<code>{fname}</code>"
        "</blockquote>"
    )
    btns = KM([
        [KB(f"⊕ Caption {_set(caption)}", f"ua_cap_{uid}")],
        [KB(f"⊕ Filename", f"ua_fname_{uid}")],
        [
            KB("⊖ Reset Caption", f"uc_cap_{uid}"),
            KB("⊖ Reset Fname", f"uc_fname_{uid}")
        ],
        [KB("◂ Back", f"ue_back_{uid}")]
    ])
    await q.message.edit(txt, reply_markup=btns)
@Client.on_callback_query(filters.regex(r"^ua_cap_") & filters.user(Config.OWNER_ID))
async def ua_cap(c, q):
    uid = int(q.data.replace("ua_cap_", ""))
    _editing[q.from_user.id] = uid
    _edit_states[q.from_user.id] = "await_cap"
    await q.message.edit(
        f"<b>⊕ Set Caption</b>\n"
        f"<b>User:</b> <code>{uid}</code>\n\n"
        "<b>Variables:</b> <code>{title}</code>, <code>{chapter}</code>, <code>{link}</code>\n\n"
        "<blockquote>Send caption template</blockquote>\n\n"
        "<i>Or /cancel</i>"
    )
@Client.on_callback_query(filters.regex(r"^ua_fname_") & filters.user(Config.OWNER_ID))
async def ua_fname(c, q):
    uid = int(q.data.replace("ua_fname_", ""))
    _editing[q.from_user.id] = uid
    _edit_states[q.from_user.id] = "await_fname"
    await q.message.edit(
        f"<b>⊕ Set Filename</b>\n"
        f"<b>User:</b> <code>{uid}</code>\n\n"
        "<b>Variables:</b> <code>{title}</code>, <code>{chapter}</code>, <code>{chap_no}</code>\n\n"
        "<blockquote>Send filename format</blockquote>\n\n"
        "<i>Or /cancel</i>"
    )
@Client.on_callback_query(filters.regex(r"^uc_cap_") & filters.user(Config.OWNER_ID))
async def uc_cap(c, q):
    uid = int(q.data.replace("uc_cap_", ""))
    await db.set_cfg(uid, "caption", None)
    await q.answer("Caption reset")
    await ue_style(c, q)
@Client.on_callback_query(filters.regex(r"^uc_fname_") & filters.user(Config.OWNER_ID))
async def uc_fname(c, q):
    uid = int(q.data.replace("uc_fname_", ""))
    await db.set_cfg(uid, "fname", "{title} - {chap_no}")
    await q.answer("Filename reset")
    await ue_style(c, q)
@Client.on_callback_query(filters.regex(r"^ue_wmark_") & filters.user(Config.OWNER_ID))
async def ue_wmark(c, q):
    uid = int(q.data.replace("ue_wmark_", ""))
    wmark_on = await db.get_cfg(uid, "wmark_on", False)
    wmark_url = await db.get_cfg(uid, "wmark_url")
    txt = (
        f"<b>▸ Watermark Settings</b>\n"
        f"<b>User:</b> <code>{uid}</code>\n\n"
        "<blockquote>"
        f"Enabled: {_s(wmark_on)}\n"
        f"Image: {_set(wmark_url)}\n"
        f"<code>{wmark_url or 'Not set'}</code>"
        "</blockquote>"
    )
    btns = KM([
        [KB(f"Watermark {_s(wmark_on)}", f"ut_wmark_{uid}")],
        [KB("⊖ Clear Image", f"uc_wmark_{uid}")],
        [KB("◂ Back", f"ue_back_{uid}")]
    ])
    await q.message.edit(txt, reply_markup=btns)
@Client.on_callback_query(filters.regex(r"^ut_wmark_") & filters.user(Config.OWNER_ID))
async def ut_wmark(c, q):
    uid = int(q.data.replace("ut_wmark_", ""))
    curr = await db.get_cfg(uid, "wmark_on", False)
    await db.set_cfg(uid, "wmark_on", not curr)
    await q.answer(f"Watermark: {_s(not curr)}")
    await ue_wmark(c, q)
@Client.on_callback_query(filters.regex(r"^uc_wmark_") & filters.user(Config.OWNER_ID))
async def uc_wmark(c, q):
    uid = int(q.data.replace("uc_wmark_", ""))
    await db.set_cfg(uid, "wmark_url", None)
    await db.set_cfg(uid, "wmark_on", False)
    await q.answer("Watermark cleared")
    await ue_wmark(c, q)
@Client.on_callback_query(filters.regex(r"^ue_promo_") & filters.user(Config.OWNER_ID))
async def ue_promo(c, q):
    uid = int(q.data.replace("ue_promo_", ""))
    promo_first = await db.get_cfg(uid, "promo_first_url")
    promo_last = await db.get_cfg(uid, "promo_last_url")
    dump_cid = await db.get_cfg(uid, "dump_cid")
    promo_msgs = await db.get_cfg(uid, "promo_msgs", [])
    txt = (
        f"<b>▸ Promo Settings</b>\n"
        f"<b>User:</b> <code>{uid}</code>\n\n"
        "<blockquote>"
        f"First Page: {_set(promo_first)}\n"
        f"Last Page: {_set(promo_last)}\n"
        f"Dump Channel: <code>{dump_cid or 'Not set'}</code>\n"
        f"Promo Msgs: <code>{len(promo_msgs)}</code>"
        "</blockquote>"
    )
    btns = KM([
        [
            KB("⊖ First", f"uc_pfirst_{uid}"),
            KB("⊖ Last", f"uc_plast_{uid}")
        ],
        [KB("⊖ Clear Promos", f"uc_promos_{uid}")],
        [KB("◂ Back", f"ue_back_{uid}")]
    ])
    await q.message.edit(txt, reply_markup=btns)
@Client.on_callback_query(filters.regex(r"^uc_pfirst_") & filters.user(Config.OWNER_ID))
async def uc_pfirst(c, q):
    uid = int(q.data.replace("uc_pfirst_", ""))
    await db.set_cfg(uid, "promo_first_url", None)
    await q.answer("First page promo cleared")
    await ue_promo(c, q)
@Client.on_callback_query(filters.regex(r"^uc_plast_") & filters.user(Config.OWNER_ID))
async def uc_plast(c, q):
    uid = int(q.data.replace("uc_plast_", ""))
    await db.set_cfg(uid, "promo_last_url", None)
    await q.answer("Last page promo cleared")
    await ue_promo(c, q)
@Client.on_callback_query(filters.regex(r"^uc_promos_") & filters.user(Config.OWNER_ID))
async def uc_promos(c, q):
    uid = int(q.data.replace("uc_promos_", ""))
    await db.set_cfg(uid, "promo_msgs", [])
    await db.set_cfg(uid, "dump_cid", None)
    await q.answer("All promos cleared")
    await ue_promo(c, q)
@Client.on_callback_query(filters.regex(r"^ue_subs_") & filters.user(Config.OWNER_ID))
async def ue_subs(c, q):
    uid = int(q.data.replace("ue_subs_", ""))
    subs = await db.get_subs(uid)
    if not subs:
        txt = f"<b>▸ Subscriptions</b>\n<b>User:</b> <code>{uid}</code>\n\n<blockquote>No subscriptions</blockquote>"
    else:
        txt = f"<b>▸ Subscriptions</b>\n<b>User:</b> <code>{uid}</code>\n\n<blockquote>"
        for s in subs[:10]:
            sid = s.get('sid', '?')
            title = s.get('title', 'Unknown')[:25]
            last = s.get('last', '-')
            txt += f"<code>{sid}</code> │ {title} │ Ch.{last}\n"
        if len(subs) > 10:
            txt += f"\n<i>...and {len(subs) - 10} more</i>"
        txt += "</blockquote>"
    btns = KM([
        [KB("⊖ Clear All Subs", f"uc_subs_{uid}")],
        [KB("◂ Back", f"ue_back_{uid}")]
    ])
    await q.message.edit(txt, reply_markup=btns)
@Client.on_callback_query(filters.regex(r"^uc_subs_") & filters.user(Config.OWNER_ID))
async def uc_subs(c, q):
    uid = int(q.data.replace("uc_subs_", ""))
    await db.delete_all_for_user(uid)
    await q.answer("All subscriptions deleted")
    await ue_subs(c, q)
@Client.on_callback_query(filters.regex(r"^ue_reset_") & filters.user(Config.OWNER_ID))
async def ue_reset(c, q):
    uid = int(q.data.replace("ue_reset_", ""))
    await db.delete_all_conf_for_user(uid)
    await q.answer("All settings reset to default")
    await show_user_settings(q, uid, edit=True)
@Client.on_callback_query(filters.regex(r"^ue_back_") & filters.user(Config.OWNER_ID))
async def ue_back(c, q):
    uid = int(q.data.replace("ue_back_", ""))
    await show_user_settings(q, uid, edit=True)
@Client.on_message(filters.private & filters.user(Config.OWNER_ID) & filters.create(lambda _, __, m: m.from_user.id in _edit_states))
async def usettings_listener(c, m):
    oid = m.from_user.id
    state = _edit_states.get(oid)
    uid = _editing.get(oid)
    if not state or not uid:
        return
    if m.text == "/cancel":
        _edit_states.pop(oid, None)
        _editing.pop(oid, None)
        return await m.reply("Cancelled.")
    if state == "await_ucid":
        try:
            cid = int(m.text)
            await db.set_cfg(uid, "update_cid", cid)
            await m.reply(f"<blockquote>✓ Update channel set to <code>{cid}</code> for user {uid}</blockquote>")
        except:
            await m.reply("Invalid channel ID")
    elif state == "await_ubtn":
        await db.set_cfg(uid, "update_btn", m.text)
        await m.reply(f"<blockquote>✓ Button text set for user {uid}</blockquote>")
    elif state == "await_umsg":
        await db.set_cfg(uid, "update_msg", m.text)
        await m.reply(f"<blockquote>✓ Update message set for user {uid}</blockquote>")
    elif state == "await_cap":
        await db.set_cfg(uid, "caption", m.text)
        await m.reply(f"<blockquote>✓ Caption set for user {uid}</blockquote>")
    elif state == "await_fname":
        await db.set_cfg(uid, "fname", m.text)
        await m.reply(f"<blockquote>✓ Filename set for user {uid}</blockquote>")
    _edit_states.pop(oid, None)
