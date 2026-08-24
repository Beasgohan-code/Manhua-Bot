
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup as KM, InlineKeyboardButton as KB
from database.db import db
from plugins.settings.shared import edit_msg, _set, user_states, temp_data
from config import Config
@Client.on_callback_query(filters.regex("^menu_ppromo"))
async def pp_m(c, q):
    uid = q.from_user.id
    dump_cid = await db.get_cfg(uid, "dump_cid")
    promo_list = await db.get_cfg(uid, "promo_msgs", [])
    del_count = await db.get_cfg(uid, "promo_del_count", 0)
    txt = (
        "<b>░ Post Promos</b>\n\n"
        "<blockquote>"
        f"<b>Dump Channel:</b> {_set(dump_cid)}\n"
        f"<b>Promo Msgs:</b> [{len(promo_list)}/3]\n"
        f"<b>Auto-Delete:</b> {del_count} msgs"
        "</blockquote>"
    )
    btns = KM([
        [
            KB(f"⊕ Dump", "ask_d_cid"),
            KB(f"⊕ Msgs", "ask_p_msgs")
        ],
        [
            KB("⊖", "dc_dec"),
            KB(f"Del: {del_count}", "noop"),
            KB("⊕", "dc_inc")
        ],
        [KB("⊖ Clear All", "c_pp_all")],
        [KB("◂ Back", "open_main")]
    ])
    await edit_msg(c, q, txt, reply_markup=btns)
@Client.on_callback_query(filters.regex("^ask_d_cid"))
async def ask_d_cid(c, q):
    user_states[q.from_user.id] = "await_d_cid"
    await q.message.edit(
        "<b>⊕ Set Dump Channel</b>\n\n"
        "<blockquote>Send channel ID or forward a message from the channel</blockquote>\n\n"
        "<i>Or /cancel</i>"
    )
@Client.on_callback_query(filters.regex("^ask_p_msgs"))
async def ask_p_msgs(c, q):
    uid = q.from_user.id
    user_states[uid] = "await_p_msgs"
    temp_data[uid] = []
    await q.message.edit(
        "<b>⊕ Add Promo Messages</b>\n\n"
        "<blockquote>Send up to 3 messages to forward after each chapter</blockquote>\n\n"
        "<i>Click Finish when done</i>",
        reply_markup=KM([[KB("✓ Finish", "f_p_msgs")]])
    )
@Client.on_callback_query(filters.regex("^f_p_msgs"))
async def f_p_msgs(c, q):
    uid = q.from_user.id
    msgs = temp_data.get(uid, [])
    if msgs:
        await db.set_cfg(uid, "promo_msgs", msgs)
        await q.answer("Promos saved!")
    user_states.pop(uid, None)
    temp_data.pop(uid, None)
    await pp_m(c, q)
@Client.on_callback_query(filters.regex("^dc_inc"))
async def dc_inc(c, q):
    curr = await db.get_cfg(q.from_user.id, "promo_del_count", 0)
    await db.set_cfg(q.from_user.id, "promo_del_count", min(10, curr + 1))
    await pp_m(c, q)
@Client.on_callback_query(filters.regex("^dc_dec"))
async def dc_dec(c, q):
    curr = await db.get_cfg(q.from_user.id, "promo_del_count", 0)
    await db.set_cfg(q.from_user.id, "promo_del_count", max(0, curr - 1))
    await pp_m(c, q)
@Client.on_callback_query(filters.regex("^c_pp_all"))
async def c_pp_all(c, q):
    uid = q.from_user.id
    await db.set_cfg(uid, "promo_msgs", [])
    await db.set_cfg(uid, "promo_del_count", 0)
    await q.answer("Cleared.")
    await pp_m(c, q)
