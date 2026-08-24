from pyrogram import Client, filters
from database.db import db
from config import Config
from plugins.fsub import force_sub
from utils.ui import RichMessage, code

def _is_owner(uid: int) -> bool:
    return uid in (Config.OWNER_ID or [])

@Client.on_message(filters.command(["webhook", "setwebhook"]))
@force_sub
async def set_webhook(c, m):
    uid = m.from_user.id
    if not _is_owner(uid):
        return await m.reply(RichMessage("Webhook", "🔗").error("Owner only.").build())
    args = m.command[1:]
    if not args:
        cur = await db.get_cfg(uid, "webhook") or Config.WEBHOOK_URL or "(none)"
        return await m.reply(
            RichMessage("Webhook", "🔗")
            .kv([("Current", code(cur))])
            .section("Usage", f"{code('/webhook https://discord.com/api/webhooks/...')}\n{code('/webhook clear')}")
            .build()
        )
    if args[0].lower() in ("clear", "off", "none", "null"):
        await db.set_cfg(uid, "webhook", "")
        return await m.reply(RichMessage("Webhook", "🔗").success("Cleared.").build())
    await db.set_cfg(uid, "webhook", args[0])
    await m.reply(RichMessage("Webhook", "🔗").success(f"Set:\n{code(args[0])}").build())

@Client.on_message(filters.command(["album"]))
@force_sub
async def set_album(c, m):
    uid = m.from_user.id
    if not _is_owner(uid):
        return await m.reply(RichMessage("Album", "🖼️").error("Owner only.").build())
    args = m.command[1:]
    if not args:
        cur = await db.get_cfg(uid, "album")
        if cur is None:
            cur = getattr(Config, "ALBUM_MAX_PAGES", 10)
        return await m.reply(
            RichMessage("Album mode", "🖼️")
            .kv([("Max pages", code(cur))])
            .section("Usage", f"{code('/album 10')} or {code('/album 0')} to disable")
            .build()
        )
    try:
        n = max(0, min(int(args[0]), 10))
        await db.set_cfg(uid, "album", n)
        await m.reply(RichMessage("Album", "🖼️").success(f"Max pages = {code(n)}").build())
    except ValueError:
        await m.reply(RichMessage("Album", "🖼️").warn("Need a number 0–10.").build())

@Client.on_message(filters.command(["poll", "ratepoll"]))
@force_sub
async def set_poll(c, m):
    uid = m.from_user.id
    if not _is_owner(uid):
        return await m.reply(RichMessage("Rate poll", "⭐").error("Owner only.").build())
    args = m.command[1:]
    if not args:
        cur = await db.get_cfg(uid, "rate_poll", False)
        return await m.reply(
            RichMessage("Rate poll", "⭐")
            .kv([("Status", code("ON" if cur else "OFF"))])
            .section("Usage", f"{code('/poll on')} | {code('/poll off')}")
            .build()
        )
    on = args[0].lower() in ("on", "1", "true", "yes")
    await db.set_cfg(uid, "rate_poll", on)
    await m.reply(RichMessage("Rate poll", "⭐").success(f"{'ON' if on else 'OFF'}").build())
