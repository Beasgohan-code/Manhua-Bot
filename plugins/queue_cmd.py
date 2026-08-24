from pyrogram import Client, filters
from config import Config
from plugins.fsub import force_sub
from services.queue import dl_queue
from utils.ui import RichMessage, code, italic

@Client.on_message(filters.command(["queue", "q"]))
@force_sub
async def queue_cmd(c, m):
    items = await dl_queue.user_items(m.from_user.id)
    if not items:
        return await m.reply(
            RichMessage("Download Queue", "📥").tip("Queue is empty.").build()
        )
    msg = RichMessage("Download Queue", "📥").line()
    for it in items[-20:]:
        msg.line(f"• {code(it.id)} · <b>{it.status}</b>")
        msg.line(f"  {italic(it.title)} — {code(it.chapter)}")
        if it.error:
            msg.line(f"  ⚠️ {it.error}")
        msg.line()
    await m.reply(msg.build())

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
