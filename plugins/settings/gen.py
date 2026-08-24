
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup as KM, InlineKeyboardButton as KB
from database.db import db
from plugins.settings.shared import edit_msg
@Client.on_callback_query(filters.regex("^menu_gen"))
async def gen_menu(c, m):
    uid = m.from_user.id
    mon = await db.get_cfg(uid, "monitor", True)
    ft = await db.get_cfg(uid, "ftype", "pdf")
    q = await db.get_cfg(uid, "qual", 85)
    interval = await db.get_cfg(uid, "check_interval", 30)
    mon_txt = "●" if mon else "○"
    txt = (
        "<b>░ General Settings</b>\n\n"
        "<blockquote>"
        f"<b>Monitor:</b> {mon_txt} Auto-check chapters\n"
        f"<b>Interval:</b> Every {interval} minutes\n"
        f"<b>Format:</b> {ft.upper()} (PDF/CBZ)\n"
        f"<b>Quality:</b> {q}% JPEG compression"
        "</blockquote>"
    )
    int_btns = []
    for i in [15, 30, 60, 120]:
        mark = "● " if interval == i else ""
        int_btns.append(KB(f"{mark}{i}m", f"t_interval_{i}"))
    btns = KM([
        [
            KB(f"↻ Monitor {mon_txt}", "t_mon"),
            KB(f"↻ {ft.upper()}", "t_ft")
        ],
        int_btns,
        [
            KB("60%", "t_qual_60"),
            KB("80%", "t_qual_80"),
            KB("100%", "t_qual_100")
        ],
        [KB("◂ Back", "open_main")]
    ])
    await edit_msg(c, m, txt, reply_markup=btns)
@Client.on_callback_query(filters.regex("^t_mon"))
async def t_mon(c, q):
    uid = q.from_user.id
    await db.set_cfg(uid, "monitor", not await db.get_cfg(uid, "monitor", True))
    await gen_menu(c, q)
@Client.on_callback_query(filters.regex("^t_ft"))
async def t_ft(c, q):
    uid = q.from_user.id
    curr = await db.get_cfg(uid, "ftype", "pdf")
    await db.set_cfg(uid, "ftype", "cbz" if curr == "pdf" else "pdf")
    await gen_menu(c, q)
@Client.on_callback_query(filters.regex(r"^t_interval_(\d+)"))
async def t_interval(c, q):
    uid = q.from_user.id
    val = int(q.data.split("_")[2])
    await db.set_cfg(uid, "check_interval", val)
    await q.answer(f"Check interval set to {val} minutes")
    await gen_menu(c, q)
@Client.on_callback_query(filters.regex(r"^t_qual_(\d+)"))
async def t_qual(c, q):
    uid = q.from_user.id
    val = int(q.data.split("_")[2])
    await db.set_cfg(uid, "qual", val)
    await q.answer(f"Quality set to {val}%")
    await gen_menu(c, q)
