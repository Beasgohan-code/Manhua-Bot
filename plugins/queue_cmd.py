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
    from services.queue import RUNNING, PENDING, DONE, FAILED, CANCELLED
    from utils.richmsg import RichDoc, send_rich

    ICON = {DONE: "✅", FAILED: "❌", RUNNING: "⏳", PENDING: "🕒", CANCELLED: "🚫"}
    shown = [i for i in items if i.is_active][:15] or items[-15:]

    counts = {}
    for it in items:
        counts[it.status] = counts.get(it.status, 0) + 1

    def fmt_eta(it):
        e = it.eta
        if e is None:
            return "—"
        m, sec = divmod(int(e), 60)
        return f"{m}m{sec:02d}s" if m else f"{sec}s"

    doc = RichDoc().heading("Download Queue", 1, "📥")
    doc.table(
        ["", "Title", "Ch", "Progress", "ETA"],
        [
            [
                ICON.get(it.status, "•"),
                it.title,
                it.chapter,
                f"{it.progress:.0f}%" if it.is_active else it.status,
                fmt_eta(it),
            ]
            for it in shown
        ],
        align=["c", "l", "r", "r", "r"],
        caption=f"{len(items)} task(s) total",
    )

    active = [i for i in items if i.is_active]
    if active:
        doc.heading("In progress", 2)
        for it in active[:3]:
            doc.progress(it.progress, f"{it.title[:28]} — {it.chapter}")

    if counts:
        doc.heading("Summary", 2)
        doc.bullets([f"{ICON.get(k, '•')} {k}: {v}" for k, v in sorted(counts.items())])

    errs = [it for it in items if it.error]
    if errs:
        doc.details(
            f"⚠️ Errors ({len(errs)})",
            "".join(f"<p>{it.title}: {it.error}</p>" for it in errs[:5]),
        )

    kbd = Keyboard().row(
        Btn("↻ Refresh", "queue_refresh", style=PRIMARY),
        Btn("🧹 Clear", "queue_clear", style=DANGER),
    )
    for it in active[:5]:
        kbd.row(Btn(f"✕ Cancel {it.title[:20]} ({it.chapter})", f"qcancel_{it.id}",
                    style=DANGER))
    kbd.row(Btn("✗ Close", "close", style=DANGER))

    sent = await send_rich(m.chat.id, doc, reply_markup=kbd, fallback_client=None)
    if sent is None:
        await m.reply(doc.fallback(), reply_markup=kbd.render())


@Client.on_callback_query(filters.regex(r"^qcancel_"))
async def queue_cancel_cb(c, q):
    qid = q.data[len("qcancel_"):]
    ok = await dl_queue.cancel(qid, user_id=q.from_user.id)
    await q.answer("Cancelled" if ok else "Already finished", show_alert=not ok)
    if ok:
        fn = queue_cmd
        while hasattr(fn, "__wrapped__"):
            fn = fn.__wrapped__

        class _M:
            from_user = q.from_user
            chat = q.message.chat

            async def reply(self, text, reply_markup=None):
                try:
                    await q.message.edit(text, reply_markup=reply_markup)
                except Exception:
                    pass

        await fn(c, _M())


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
