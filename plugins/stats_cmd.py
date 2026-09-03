from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup as KM, InlineKeyboardButton as KB
from database.db import db
from services.mgr import mgr
from config import Config
from plugins.fsub import force_sub
from utils.ui import RichMessage, code, kb, btn
from utils.tgui import Btn, Keyboard, PRIMARY, DANGER, SUCCESS
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
    # Engine / source breakdown for the dashboard
    try:
        from services.vmgr import vmgr
        from services import vengine
        from sources.compat import is_legacy

        vsrcs = len(vmgr.srcs)
        legacy = sum(1 for x in mgr.srcs.values() if is_legacy(x))
        est = vengine.engine_status()
    except Exception:
        vsrcs, legacy, est = 0, 0, {}

    def mk(v):
        return "✅" if v else "❌"

    msg = (
        RichMessage("Health Dashboard", "📊")
        .heading("Runtime", "⚙")
        .table(
            ["Metric", "Value"],
            [
                ["Bot", f"@{me.username}"],
                ["Uptime", f"{h}h {mins}m {secs}s"],
                ["Python", platform.python_version()],
                ["Database", "PostgreSQL"],
            ],
        )
        .heading("Content", "📚")
        .table(
            ["Metric", "Count"],
            [
                ["Manga sources", srcs],
                ["  legacy API", legacy],
                ["Video sources", vsrcs],
                ["Users", users],
                ["Subscriptions", subs_n],
                ["Banned", banned],
            ],
            align=["l", "r"],
        )
    )
    if est:
        msg.heading("Engine", "🎬").table(
            ["Tool", "St"],
            [
                ["yt-dlp", mk(est.get("yt_dlp"))],
                ["ffmpeg", mk(est.get("ffmpeg"))],
                ["aria2c", mk(est.get("aria2c"))],
            ],
        )
    if is_owner:
        msg.tip("Owner: /webhook /album /poll /adult")

    kbd = Keyboard().row(
        Btn("↻ Refresh", "stats_refresh", style=PRIMARY),
        Btn("🩺 Audit", "audit_open", style=SUCCESS),
        Btn("✗ Close", "close", style=DANGER),
    )
    await m.reply(msg.build(), reply_markup=kbd.render())

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
