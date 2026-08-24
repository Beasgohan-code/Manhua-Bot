from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup as KM, InlineKeyboardButton as KB
from database.db import db
from services.mgr import mgr
from config import Config
from plugins.fsub import force_sub
from utils.ui import RichMessage, code, kb, btn
import time, platform

_bot_start = time.time()

@Client.on_message(filters.command(["stats", "health", "status"]))
@force_sub
async def stats_cmd(c, m):
    uid = m.from_user.id
    is_owner = uid in (Config.OWNER_ID or [])
    try:
        users = await db.tot_usrs()
    except Exception:
        users = "?"
    try:
        all_subs = await db.get_subs()
        subs_n = len(all_subs) if all_subs else 0
    except Exception:
        subs_n = "?"
    try:
        banned = len(await db.get_banned_users()) if hasattr(db, "get_banned_users") else 0
    except Exception:
        banned = "?"
    srcs = len(getattr(mgr, "srcs", {}) or {})
    uptime = int(time.time() - _bot_start)
    h, rem = divmod(uptime, 3600)
    mins, secs = divmod(rem, 60)
    me = await c.get_me()
    msg = (
        RichMessage("Health Dashboard", "📊")
        .tip("Live bot status")
        .line()
        .kv([
            ("Bot", f"@{me.username}"),
            ("Uptime", code(f"{h}h {mins}m {secs}s")),
            ("Sources", code(srcs)),
            ("Users", code(users)),
            ("Subscriptions", code(subs_n)),
            ("Banned", code(banned)),
            ("Python", code(platform.python_version())),
            ("Engine", code("PostgreSQL")),
        ])
    )
    if is_owner:
        msg.tip("Owner: /webhook /album /poll /adult")
    await m.reply(
        msg.build(),
        reply_markup=KM([[KB("↻ Refresh", "stats_refresh"), KB("✗ Close", "close")]]),
    )

@Client.on_callback_query(filters.regex(r"^stats_refresh$"))
async def stats_refresh(c, q):
    await q.answer("Refreshing…")
    class M:
        from_user = q.from_user
        async def reply(self, *a, **k):
            try:
                return await q.message.edit_text(*a, **k)
            except Exception:
                return await q.message.reply(*a, **k)
    await stats_cmd(c, M())
