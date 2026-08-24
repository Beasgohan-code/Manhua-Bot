
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup as KM, InlineKeyboardButton as KB
from database.db import db
from plugins.settings.shared import edit_msg, SETTINGS_BANNER, _set, has_img, has_wmark, clear_img_url, clear_wmark_url
from services.backup import create_user_backup
from plugins.fsub import force_sub
@Client.on_message(filters.command("settings") & filters.private)
@force_sub
async def settings_cmd(c, m):
    await db.add_usr(m.from_user.id)
    await main_menu(c, m)
@Client.on_callback_query(filters.regex("^open_main"))
async def cb_main(c, q):
    await main_menu(c, q)
async def main_menu(c, m):
    uid = m.from_user.id if hasattr(m, 'from_user') and m.from_user else m.message.from_user.id if hasattr(m, 'message') else None
    if not uid: return
    mon = await db.get_cfg(uid, "monitor", True)
    ft = await db.get_cfg(uid, "ftype", "pdf")
    qual = await db.get_cfg(uid, "qual", 80)
    interval = await db.get_cfg(uid, "check_interval", 30)
    has_first = await has_img(uid, "first")
    has_last = await has_img(uid, "last")
    has_thumb = await has_img(uid, "thumb")
    imgs_count = sum([has_first, has_last, has_thumb])
    has_cap = await db.get_cfg(uid, "caption")
    has_fname = await db.get_cfg(uid, "fname")
    style_count = sum([bool(has_cap), bool(has_fname)])
    update_cid = await db.get_cfg(uid, "update_cid")
    chan_listen = await db.get_cfg(uid, "chan_listen", False)
    upd_count = 1 if update_cid else 0
    promo_msgs = await db.get_cfg(uid, "promo_msgs", [])
    promo_count = len(promo_msgs)
    wmark_on = await db.get_cfg(uid, "wmark_on", False)
    has_wm = await has_wmark(uid)
    mon_s = "●" if mon else "○"
    wm_s = "●" if wmark_on else "○"
    cl_s = "●" if chan_listen else "○"
    txt = (
        "<b>░ Settings Menu</b>\n\n"
        "<blockquote>"
        f"<b>General:</b> Monitor {mon_s} │ {interval}m │ {ft.upper()} │ {qual}%\n"
        f"<b>Watermark:</b> {wm_s} {_set(has_wm)}\n"
        f"<b>Images:</b> [{imgs_count}/3] │ <b>Style:</b> [{style_count}/2]\n"
        f"<b>Updates:</b> {_set(update_cid)} │ Listener {cl_s} │ <b>Promos:</b> [{promo_count}/3]"
        "</blockquote>\n\n"
        "<i>Select a category below</i>"
    )
    btns = KM([
        [
            KB(f"General {mon_s}", "menu_gen"),
            KB(f"Watermark {wm_s}", "menu_wm")
        ],
        [
            KB(f"Images [{imgs_count}]", "menu_imgs"),
            KB(f"Styling [{style_count}]", "menu_style")
        ],
        [
            KB("Update Channel", "menu_update"),
            KB("Post Promos", "menu_ppromo")
        ],
        [
            KB("📦 Backup", "get_backup"),
            KB("↻ Reset All", "reset_all_cfg")
        ],
        [KB("✕ Close", "close")]
    ])
    if hasattr(m, 'message'):
        await edit_msg(c, m, txt, reply_markup=btns)
    else:
        await c.send_photo(m.chat.id, SETTINGS_BANNER, caption=txt, reply_markup=btns)
@Client.on_callback_query(filters.regex("^reset_all_cfg"))
async def reset_all_cfg(c, q):
    uid = q.from_user.id
    await db.set_cfg(uid, "caption", None)
    await db.set_cfg(uid, "fname", "{title} - {chap_no}")
    await db.set_cfg(uid, "monitor", True)
    await db.set_cfg(uid, "ftype", "pdf")
    await db.set_cfg(uid, "qual", 80)
    await db.set_cfg(uid, "check_interval", 30)
    await db.set_cfg(uid, "update_cid", None)
    await db.set_cfg(uid, "update_msg", None)
    await db.set_cfg(uid, "update_sticker", None)
    await db.set_cfg(uid, "update_btn", None)
    await db.set_cfg(uid, "chan_listen", False)
    await db.set_cfg(uid, "dump_cid", None)
    await db.set_cfg(uid, "promo_msgs", [])
    await db.set_cfg(uid, "promo_del_count", 0)
    await db.set_cfg(uid, "wmark_on", False)
    for t in ["first", "last", "thumb"]:
        await clear_img_url(uid, t)
    await clear_wmark_url(uid)
    await q.answer("All settings reset!", show_alert=True)
    await main_menu(c, q)
@Client.on_callback_query(filters.regex("^get_backup"))
async def get_backup_cb(c, q):
    uid = q.from_user.id
    await q.answer("Creating backup...", show_alert=False)
    success = await create_user_backup(c, uid, q.message.chat.id)
    if not success:
        await q.message.reply("<b>❌ Failed to create backup.</b>\n<i>Please try again later.</i>")
