from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup as KM, InlineKeyboardButton as KB
from database.db import db
from plugins.fsub import force_sub
from utils.ui import RichMessage, code, bold

@Client.on_message(filters.command(["subs", "subscriptions", "mylist"]))
@force_sub
async def subs_cmd(c, m):
    uid = m.from_user.id
    subs = await db.get_subs(uid)
    if not subs:
        return await m.reply(
            RichMessage("Subscriptions", "📚")
            .tip("No series yet. Use /search to track one.")
            .build()
        )
    msg = RichMessage("Your Subscriptions", "📚").kv([("Count", code(len(subs)))]).line()
    btns = []
    for i, s in enumerate(subs[:30], 1):
        title = s.get("title") or "?"
        sid = s.get("sid") or "?"
        last = s.get("last") or "—"
        msg.line(f"{i}. {bold(title)}")
        msg.line(f"   sid: {code(sid)} · last: {code(last)}")
        if sid and sid != "?":
            btns.append([KB(f"Unsub {title[:18]}", f"unsub_{sid}")])
    btns.append([KB("✗ Close", "close")])
    await m.reply(msg.build(), reply_markup=KM(btns))

@Client.on_message(filters.command(["unsubs", "unsub", "unsubscribe"]))
@force_sub
async def unsubs_cmd(c, m):
    uid = m.from_user.id
    if len(m.command) < 2:
        return await m.reply(
            RichMessage("Unsubscribe", "📚")
            .section("Usage", f"{code('/unsubs SID')}\nGet SIDs from /subs")
            .build()
        )
    sid = m.command[1].strip()
    await db.del_sub(uid, sid)
    await m.reply(RichMessage("Unsubscribe", "📚").success(f"Removed {code(sid)}").build())

@Client.on_callback_query(filters.regex(r"^unsub_"))
async def unsub_cb(c, q):
    sid = q.data.replace("unsub_", "", 1)
    await db.del_sub(q.from_user.id, sid)
    await q.answer("Unsubscribed")
    try:
        await q.message.edit_text(
            RichMessage("Unsubscribe", "📚").success(f"Removed {code(sid)}").build()
        )
    except Exception:
        await q.message.reply(
            RichMessage("Unsubscribe", "📚").success(f"Removed {code(sid)}").build()
        )
