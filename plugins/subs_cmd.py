from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup as KM, InlineKeyboardButton as KB
from database.db import db
from plugins.fsub import force_sub
from utils.ui import RichMessage, code, bold
from utils.tgui import Btn, Keyboard, PRIMARY, DANGER, NOOP_CB

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
    shown = subs[:30]
    msg = RichMessage("Your Subscriptions", "📚")
    msg.table(
        ["#", "Series", "Last", "SID"],
        [
            [
                i,
                s.get("title") or "?",
                s.get("last") or "—",
                s.get("sid") or "?",
            ]
            for i, s in enumerate(shown, 1)
        ],
        align=["r", "l", "r", "l"],
        max_col=20,
    )
    if len(subs) > len(shown):
        msg.tip(f"Showing {len(shown)} of {len(subs)}")
    msg.tip("Tap a button to unsubscribe · /unsubs SID")

    kbd = Keyboard()
    for s in shown:
        sid = s.get("sid")
        if sid and sid != "?":
            kbd.row(Btn(f"✕ {(s.get('title') or '?')[:24]}", f"unsub_{sid}", style=DANGER))
    kbd.row(Btn("✗ Close", "close", style=DANGER))
    await m.reply(msg.build(), reply_markup=kbd.render())

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
