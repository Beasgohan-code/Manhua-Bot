from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup as KM, InlineKeyboardButton as KB
from plugins.fsub import force_sub
from utils.ui import HELP_TEXT

@Client.on_message(filters.command(["help", "cmds", "commands"]))
@force_sub
async def help_cmd(c, m):
    await m.reply(
        HELP_TEXT,
        reply_markup=KM([
            [KB("🔍 Search tip", "search_help"), KB("📊 Stats", "open_stats")],
            [KB("✗ Close", "close")],
        ]),
    )
