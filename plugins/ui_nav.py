# Manhua-Bot - UI navigation callbacks
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup as KM, InlineKeyboardButton as KB

@Client.on_callback_query(filters.regex(r"^open_subs$"))
async def open_subs(c, q):
    await q.answer()
    from plugins.subs_cmd import subs_cmd
    class M:
        from_user = q.from_user
        command = ["subs"]
        async def reply(self, *a, **k):
            return await q.message.reply(*a, **k)
    await subs_cmd(c, M())

@Client.on_callback_query(filters.regex(r"^open_queue$"))
async def open_queue(c, q):
    await q.answer()
    from plugins.queue_cmd import queue_cmd
    class M:
        from_user = q.from_user
        command = ["queue"]
        async def reply(self, *a, **k):
            return await q.message.reply(*a, **k)
    await queue_cmd(c, M())

@Client.on_callback_query(filters.regex(r"^open_stats$"))
async def open_stats(c, q):
    await q.answer()
    from plugins.stats_cmd import stats_cmd
    class M:
        from_user = q.from_user
        command = ["stats"]
        async def reply(self, *a, **k):
            try:
                return await q.message.edit_text(*a, **k)
            except Exception:
                return await q.message.reply(*a, **k)
    await stats_cmd(c, M())

@Client.on_callback_query(filters.regex(r"^open_sources$"))
async def open_sources(c, q):
    await q.answer()
    from plugins.sources_cmd import sources_cmd
    class M:
        from_user = q.from_user
        command = ["sources"]
        async def reply(self, *a, **k):
            return await q.message.reply(*a, **k)
    await sources_cmd(c, M())

@Client.on_callback_query(filters.regex(r"^close$"))
async def close_cb(c, q):
    try:
        await q.message.delete()
    except Exception:
        await q.answer("Closed")
