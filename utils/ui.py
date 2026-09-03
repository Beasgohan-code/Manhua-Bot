"""
Rich message helpers for Manhua-Bot.
Consistent HTML cards, headings, tables, buttons across the bot.
"""
from __future__ import annotations
from html import escape
from typing import Optional, Sequence, List, Any, Union
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def h(text: Any) -> str:
    return escape(str(text), quote=False)


def bold(text: Any) -> str:
    return f"<b>{h(text)}</b>"


def italic(text: Any) -> str:
    return f"<i>{h(text)}</i>"


def code(text: Any) -> str:
    return f"<code>{h(text)}</code>"


def pre(text: Any) -> str:
    return f"<pre>{h(text)}</pre>"


def link(text: str, url: str) -> str:
    return f'<a href="{h(url)}">{h(text)}</a>'


def block(text: str) -> str:
    return f"<blockquote>{text}</blockquote>"


def heading(text: str, emoji: str = "📌") -> str:
    return f"{emoji} {bold(text)}"


def kv_block(rows: Sequence[tuple], bullet: str = "") -> str:
    lines = []
    for label, value in rows:
        if value is None or value == "":
            continue
        # value may already contain HTML (code/link) — only escape label
        lines.append(f"{bold(label)}: {value}")
    body = "\n".join(lines)
    return block(body) if body else ""


def table(
    headers: Sequence[str],
    rows: Sequence[Sequence[Any]],
    max_col: int = 16,
    align: Optional[Sequence[str]] = None,
    borders: bool = True,
) -> str:
    """Monospaced table. Delegates to the display-width-aware renderer in
    utils.tgui so emoji/CJK cells do not break column alignment."""
    from utils.tgui import table as _t

    return _t(headers, rows, align=align, max_col=max_col, borders=borders)


def columns(items: Sequence[Any], cols: int = 2, gap: int = 2) -> str:
    """Lay a flat list out in aligned monospaced columns."""
    from utils.tgui import columns as _c

    return _c(items, cols=cols, gap=gap)


def heading2(text: str, emoji: str = "") -> str:
    from utils.tgui import heading as _h

    return _h(text, 2, emoji)


def divider(width: int = 26) -> str:
    from utils.tgui import divider as _d

    return _d(width)


class RichMessage:
    """Builder for structured Telegram HTML messages."""

    def __init__(self, title: str = "", emoji: str = "📖"):
        self.parts: List[str] = []
        if title:
            self.parts.append(heading(title, emoji))
            self.parts.append("")

    def line(self, text: str = "") -> "RichMessage":
        self.parts.append(text)
        return self

    def section(self, title: str, body: str) -> "RichMessage":
        self.parts.append(f"{bold(title)}")
        self.parts.append(block(body))
        self.parts.append("")
        return self

    def kv(self, rows: Sequence[tuple]) -> "RichMessage":
        self.parts.append(kv_block(rows))
        self.parts.append("")
        return self

    def text(self, text: str) -> "RichMessage":
        self.parts.append(text)
        return self

    def table(
        self,
        headers: Sequence[str],
        rows: Sequence[Sequence[Any]],
        align: Optional[Sequence[str]] = None,
        max_col: int = 16,
        borders: bool = True,
    ) -> "RichMessage":
        """Add a bordered, emoji-safe table."""
        if rows:
            self.parts.append(table(headers, rows, max_col, align, borders))
        return self

    def columns(self, items: Sequence[Any], cols: int = 2) -> "RichMessage":
        """Add a flat list rendered as aligned columns."""
        if items:
            self.parts.append(columns(items, cols))
        return self

    def heading(self, text: str, emoji: str = "", level: int = 2) -> "RichMessage":
        from utils.tgui import heading as _h

        self.parts.append(_h(text, level, emoji))
        return self

    def divider(self, width: int = 26) -> "RichMessage":
        self.parts.append(divider(width))
        return self

    def progress(self, pct: float, label: str = "") -> "RichMessage":
        from utils.tgui import bar

        self.parts.append(
            f"{bar(pct)} {bold(f'{pct:.0f}%')}" + (f" {label}" if label else "")
        )
        return self

    def field(self, label: str, value: Any) -> "RichMessage":
        self.parts.append(f"{bold(label)}: {value}")
        return self

    def tip(self, text: str) -> "RichMessage":
        self.parts.append(italic(text))
        return self

    def success(self, text: str) -> "RichMessage":
        self.parts.append(f"✅ {text}")
        return self

    def error(self, text: str) -> "RichMessage":
        self.parts.append(f"❌ {text}")
        return self

    def warn(self, text: str) -> "RichMessage":
        self.parts.append(f"⚠️ {text}")
        return self

    def build(self, limit: int = 4096) -> str:
        out = "\n".join(p for p in self.parts if p is not None)
        out = out.replace("\n\n\n", "\n\n").strip()
        return out[:limit]


def btn(text: str, data: str = None, url: str = None) -> InlineKeyboardButton:
    if url:
        return InlineKeyboardButton(text, url=url)
    return InlineKeyboardButton(text, callback_data=data or "noop")


def kb(rows: List[List[InlineKeyboardButton]]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(rows)


def nav_row(back: str = None, close: bool = True) -> list:
    row = []
    if back:
        row.append(btn("◂ Back", back))
    if close:
        row.append(btn("✗ Close", "close"))
    return row


# ---- Standard screens ----

START_TEXT = (
    RichMessage("Manhua-Bot", "📖")
    .tip("Auto chapter tracker · PDF/CBZ · 60+ sources")
    .line()
    .section(
        "Quick start",
        "1. /search <code>title</code>\n"
        "2. Pick source → series\n"
        "3. 📚 Chapters · ⬇️ Download or 📌 Track\n"
        "4. /settings for style &amp; file type",
    )
    .section(
        "Handy",
        "/subs · /queue · /sources · /stats · /help\n"
        "/adult on — unlock NSFW sources",
    )
    .build()
)

HELP_TEXT = (
    RichMessage("Command Center", "📖")
    .section(
        "Discover",
        "/search &lt;name&gt; — multi-source search\n"
        "/sources — site list\n"
        "/dl &lt;src&gt; &lt;id&gt; [10-15] — direct / range DL",
    )
    .section(
        "Anime & Video",
        "/anime &lt;name&gt; — search anime sources\n"
        "/hentai &lt;name&gt; — adult video search (/adult on)\n"
        "/vsearch &lt;name&gt; — all video sources\n"
        "/vdl &lt;src&gt; &lt;id&gt; [1-5] — direct episode DL\n"
        "/vsources — video site list\n"
        "/vengine — engine &amp; plugin status\n"
        "/audit — health check\n"
        "/vhistory — recent searches",
    )
    .section(
        "Library",
        "/subs — tracked series\n"
        "/unsubs &lt;sid&gt; — stop tracking\n"
        "/queue — download queue\n"
        "/clean_tasks — clear your queue",
    )
    .section(
        "Output",
        "/usettings — your upload settings\n"
        "  · video or document · thumbnail · metadata\n"
        "/merge N — chapters per PDF\n"
        "/pdfpass text — lock PDFs\n"
        "Settings file types: PDF · CBZ · Links",
    )
    .section(
        "Safety & status",
        "/adult on|off — NSFW gate\n"
        "/stats — health dashboard\n"
        "/help — this menu",
    )
    .section(
        "Owner",
        "/webhook · /album · /poll · /polltext\n"
        "/add /del /premium_users /del_expired",
    )
    .build()
)
