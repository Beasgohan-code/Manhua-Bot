from pyrogram import Client, filters
from config import Config
from plugins.fsub import force_sub
from services.queue import dl_queue
from utils.ui import RichMessage, code, italic
from utils.tgui import Btn, Keyboard, PRIMARY, DANGER

@Client.on_message(filters.command(["queue", "q"]))
@force_sub
async def queue_cmd(c, m):
    items = await dl_queue.user_items(m.from_user.id)
    if not items:
        return await m.reply(
            RichMessage("Download Queue", "📥").tip("Queue is empty.").build()
        )
    shown = items[-20:]
    ICON = {
        "done": "✅", "failed": "❌", "error": "❌",
        "running": "⏳", "active": "⏳",
        "pending": "🕒", "queued": "🕒",
    }
    counts = {}
    for it in items:
        counts[it.status] = counts.get(it.status, 0) + 1

    msg = RichMessage("Download Queue", "📥")
    msg.table(
        ["St", "Title", "Ch", "ID"],
        [
            [
                ICON.get(str(it.status).lower(), "•"),
                it.title or "?",
                it.chapter or "—",
                it.id,
            ]
            for it in shown
        ],
        align=["c", "l", "r", "l"],
        max_col=20,
    )
    if counts:
        msg.heading("Summary", "📊").table(
            ["Status", "Count"],
            [[k, v] for k, v in sorted(counts.items())],
            align=["l", "r"],
        )
    errs = [it for it in shown if getattr(it, "error", None)]
    if errs:
        msg.section(
            "Errors",
            "\n".join(f"{code(e.id)}: {str(e.error)[:80]}" for e in errs[:5]),
        )
    if len(items) > len(shown):
        msg.tip(f"Showing last {len(shown)} of {len(items)}")

    kbd = Keyboard().row(
        Btn("↻ Refresh", "queue_refresh", style=PRIMARY),
        Btn("🧹 Clear", "queue_clear", style=DANGER),
        Btn("✗ Close", "close", style=DANGER),
    )
    await m.reply(msg.build(), reply_markup=kbd.render())


@Client.on_callback_query(filters.regex(r"^queue_refresh$"))
async def queue_refresh_cb(c, q):
    await q.answer("Refreshing…")

    class _M:
        from_user = q.from_user
        chat = q.message.chat

        async def reply(self, text, reply_markup=None):
            try:
                await q.message.edit(text, reply_markup=reply_markup)
            except Exception:
                pass

    fn = queue_cmd
    while hasattr(fn, "__wrapped__"):
        fn = fn.__wrapped__
    await fn(c, _M())


@Client.on_callback_query(filters.regex(r"^queue_clear$"))
async def queue_clear_cb(c, q):
    n = await dl_queue.clear_user(q.from_user.id)
    await q.answer(f"Cleared {n} task(s)", show_alert=True)
    try:
        await q.message.edit(
            RichMessage("Download Queue", "📥")
            .success(f"Cleared {code(n)} pending/failed task(s).")
            .build()
        )
    except Exception:
        pass

@Client.on_message(filters.command(["clean_tasks", "cleartasks", "clearqueue"]))
@force_sub
async def clean_tasks_cmd(c, m):
    uid = m.from_user.id
    if uid in (Config.OWNER_ID or []) and (len(m.command) > 1 and m.command[1].lower() == "all"):
        n = await dl_queue.clear_all_pending()
        return await m.reply(
            RichMessage("Tasks", "🧹").success(f"Cleared {code(n)} pending tasks (all).").build()
        )
    n = await dl_queue.clear_user(uid)
    await m.reply(
        RichMessage("Tasks", "🧹").success(f"Cleared {code(n)} of your pending/failed tasks.").build()
    )
