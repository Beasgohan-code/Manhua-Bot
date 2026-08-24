from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup as KM, InlineKeyboardButton as KB
from services.mgr import mgr
from plugins.fsub import force_sub
from plugins.adult_cmd import is_adult_source, user_allows_adult
from utils.ui import RichMessage, code

@Client.on_message(filters.command(["sources", "sites"]))
@force_sub
async def sources_cmd(c, m):
    names = sorted(mgr.srcs.keys())
    allow = await user_allows_adult(m.from_user.id)
    safe, adult = [], []
    for n in names:
        short = n.replace("Webs", "")
        if is_adult_source(n):
            if allow:
                adult.append(short)
        else:
            safe.append(short)

    def chunk(lst, n=3):
        rows = []
        row = []
        for x in lst:
            row.append(KB(x, f"noop_src_{x}"))
            if len(row) == n:
                rows.append(row)
                row = []
        if row:
            rows.append(row)
        return rows

    adult_val = code(len(adult))
    if not allow:
        adult_val += " — locked (/adult on)"

    text = (
        RichMessage("Loaded Sources", "📚")
        .kv([
            ("Total loaded", code(len(names))),
            ("Shown (safe)", code(len(safe))),
            ("Adult", adult_val),
        ])
        .tip("Adult sites stay hidden until /adult on.")
        .build()
    )
    btns = chunk(safe[:30])
    if adult:
        btns.append([KB(f"🔞 Adult ({len(adult)})", "noop")])
        btns.extend(chunk(adult[:12]))
    btns.append([KB("✗ Close", "close")])
    await m.reply(text, reply_markup=KM(btns))

@Client.on_callback_query(filters.regex(r"^noop"))
async def noop_cb(c, q):
    await q.answer()
