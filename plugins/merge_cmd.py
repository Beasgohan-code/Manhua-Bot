from pyrogram import Client, filters
from database.db import db
from plugins.fsub import force_sub
from utils.ui import RichMessage, code

@Client.on_message(filters.command(["merge"]))
@force_sub
async def merge_cmd(c, m):
    uid = m.from_user.id
    if len(m.command) < 2:
        cur = await db.get_cfg(uid, "merge_count", 1)
        return await m.reply(
            RichMessage("Merge chapters", "📦")
            .kv([("Current", code(cur))])
            .section("Usage", f"{code('/merge 5')} — combine every 5 chapters\n{code('/merge 1')} — one file per chapter")
            .build()
        )
    try:
        n = max(1, min(int(m.command[1]), 50))
    except ValueError:
        return await m.reply(RichMessage("Merge", "📦").warn("Need a number 1–50.").build())
    await db.set_cfg(uid, "merge_count", n)
    await m.reply(RichMessage("Merge", "📦").success(f"Set to {code(n)} chapter(s) per file.").build())

@Client.on_message(filters.command(["pdfpass", "pdfpassword", "password"]))
@force_sub
async def pdfpass_cmd(c, m):
    uid = m.from_user.id
    if len(m.command) < 2:
        cur = await db.get_cfg(uid, "pdf_password", "") or "(none)"
        return await m.reply(
            RichMessage("PDF password", "🔐")
            .kv([("Current", code(cur))])
            .section("Usage", f"{code('/pdfpass YourChannel')}\n{code('/pdfpass off')}")
            .build()
        )
    arg = " ".join(m.command[1:])
    if arg.lower() in ("off", "none", "clear", "0"):
        await db.set_cfg(uid, "pdf_password", "")
        return await m.reply(RichMessage("PDF password", "🔐").success("Cleared.").build())
    await db.set_cfg(uid, "pdf_password", arg)
    await m.reply(RichMessage("PDF password", "🔐").success(f"Set to {code(arg)}").build())
