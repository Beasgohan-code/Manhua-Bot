from pyrogram import Client, filters
from database.db import db
from config import Config
from plugins.fsub import force_sub
from utils.ui import RichMessage, code

def _owner(uid):
    return uid in (Config.OWNER_ID or [])

@Client.on_message(filters.command(["add", "addpremium"]))
@force_sub
async def add_premium(c, m):
    if not _owner(m.from_user.id):
        return await m.reply(RichMessage("Premium", "⭐").error("Owner only.").build())
    if len(m.command) < 2:
        return await m.reply(RichMessage("Premium", "⭐").section("Usage", code("/add USER_ID [days]")).build())
    try:
        uid = int(m.command[1])
    except ValueError:
        return await m.reply(RichMessage("Premium", "⭐").warn("Invalid user id.").build())
    days = int(m.command[2]) if len(m.command) > 2 else 30
    await db.set_premium(uid, True, days)
    await m.reply(RichMessage("Premium", "⭐").success(f"Added {code(uid)} · {days} days").build())

# NOTE: plain "/del" is claimed by plugins/list.py (subscription delete),
# which registers first and would shadow this handler entirely.
@Client.on_message(filters.command(["delpremium", "delprem"]))
@force_sub
async def del_premium(c, m):
    if not _owner(m.from_user.id):
        return await m.reply(RichMessage("Premium", "⭐").error("Owner only.").build())
    if len(m.command) < 2:
        return await m.reply(RichMessage("Premium", "⭐").section("Usage", code("/del USER_ID")).build())
    uid = int(m.command[1])
    await db.set_premium(uid, False, 0)
    await m.reply(RichMessage("Premium", "⭐").success(f"Removed {code(uid)}").build())

@Client.on_message(filters.command(["premium_users", "premiums"]))
@force_sub
async def list_premium(c, m):
    if not _owner(m.from_user.id):
        return await m.reply(RichMessage("Premium", "⭐").error("Owner only.").build())
    users = await db.list_premium()
    if not users:
        return await m.reply(RichMessage("Premium", "⭐").tip("No premium users.").build())
    msg = RichMessage("Premium Users", "⭐").line()
    for u in users:
        msg.line(f"• {code(u.get('id'))} until {code(u.get('premium_until') or '∞')}")
    await m.reply(msg.build())

@Client.on_message(filters.command(["del_expired"]))
@force_sub
async def del_expired(c, m):
    if not _owner(m.from_user.id):
        return await m.reply(RichMessage("Premium", "⭐").error("Owner only.").build())
    n = await db.del_expired_premium()
    await m.reply(RichMessage("Premium", "⭐").success(f"Removed {code(n)} expired.").build())
