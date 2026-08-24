# Manhua-Bot - custom rate-poll question text

from pyrogram import Client, filters
from database.db import db
from config import Config
from plugins.fsub import force_sub

DEFAULT_Q = "Rate: {title} Ch {chapter}"


@Client.on_message(filters.command(["polltext", "setpoll"]))
@force_sub
async def polltext_cmd(c, m):
    uid = m.from_user.id
    if uid not in (Config.OWNER_ID or []):
        return await m.reply("Owner only.")
    args = m.command[1:]
    if not args:
        cur = await db.get_cfg(uid, "poll_text") or DEFAULT_Q
        return await m.reply(
            f"<b>Poll question template</b>\n<code>{cur}</code>\n\n"
            "Placeholders: <code>{title}</code> <code>{chapter}</code>\n"
            "Usage:\n<code>/polltext Rate this: {title} #{chapter}</code>\n"
            "<code>/polltext reset</code>"
        )
    if args[0].lower() in ("reset", "default", "clear"):
        await db.set_cfg(uid, "poll_text", DEFAULT_Q)
        return await m.reply(f"Reset to:\n<code>{DEFAULT_Q}</code>")
    text = " ".join(args)
    await db.set_cfg(uid, "poll_text", text)
    await m.reply(f"Poll text set:\n<code>{text}</code>")
