from pyrogram import Client, filters

from services.mgr import mgr
from plugins.fsub import force_sub
from plugins.adult_cmd import is_adult_source, user_allows_adult
from utils.ui import RichMessage, code
from utils.tgui import Btn, Keyboard, NOOP_CB, PRIMARY, DANGER, SUCCESS

PER_PAGE = 24


def _split(allow: bool):
    safe, adult = [], []
    for n in sorted(mgr.srcs.keys()):
        short = n.replace("Webs", "")
        (adult if is_adult_source(n) else safe).append(short)
    return safe, adult


def _kind(name: str) -> str:
    """Which scraper interface a source implements."""
    from sources.compat import is_legacy

    src = mgr.srcs.get(name) or mgr.srcs.get(name + "Webs")
    if src is None:
        return "?"
    if callable(getattr(src, "get_manga", None)):
        return "std"
    return "alt" if is_legacy(src) else "!"


def _render(page: int, allow: bool):
    safe, adult = _split(allow)
    listing = safe + (adult if allow else [])
    pages = max(1, (len(listing) + PER_PAGE - 1) // PER_PAGE)
    page = max(0, min(page, pages - 1))
    chunk = listing[page * PER_PAGE : (page + 1) * PER_PAGE]

    msg = RichMessage("Manga Sources", "📚")
    msg.table(
        ["Group", "Count"],
        [
            ["Total", len(safe) + len(adult)],
            ["Safe", len(safe)],
            ["Adult", len(adult) if allow else f"{len(adult)} 🔒"],
        ],
        align=["l", "r"],
    )
    msg.heading(f"Page {page + 1}/{pages}", "📄")
    # Three aligned columns keeps 24 names readable in one screen.
    msg.columns([f"{'🔞' if n in adult else '•'} {n}" for n in chunk], cols=2)
    if not allow and adult:
        msg.tip(f"{len(adult)} adult sources hidden — /adult on")
    msg.tip("Use /dl <code> <id> · /audit for health")

    kb = Keyboard().row(
        Btn("◂ Prev", f"srcpg_{page - 1}", disabled=page == 0),
        Btn(f"{page + 1}/{pages}", NOOP_CB, disabled=True, mark_disabled=False),
        Btn("Next ▸", f"srcpg_{page + 1}", disabled=page >= pages - 1),
    )
    kb.row(
        Btn("🎬 Video sources", "vsrc_open", style=PRIMARY),
        Btn("🩺 Health", "audit_open", style=SUCCESS),
    )
    kb.row(Btn("✗ Close", "close", style=DANGER))
    return msg.build(), kb.render()


@Client.on_message(filters.command(["sources", "sites"]))
@force_sub
async def sources_cmd(c, m):
    allow = await user_allows_adult(m.from_user.id)
    text, kb = _render(0, allow)
    await m.reply(text, reply_markup=kb)


@Client.on_callback_query(filters.regex(r"^srcpg_"))
async def sources_page(c, q):
    allow = await user_allows_adult(q.from_user.id)
    try:
        page = int(q.data.split("_")[-1])
    except ValueError:
        return await q.answer()
    text, kb = _render(page, allow)
    await q.answer()
    try:
        await q.message.edit(text, reply_markup=kb)
    except Exception:
        pass


# NOTE: this pattern used to be an unanchored r"^noop", which also matched
# "noop_adult" / other plugins' inert callbacks and swallowed them depending
# on plugin load order. Keep it scoped to this plugin's own buttons.
@Client.on_callback_query(filters.regex(r"^noop_src_"))
async def noop_src_cb(c, q):
    await q.answer(q.data.replace("noop_src_", ""), cache_time=1)
