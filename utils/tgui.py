# Manhua-Bot - modern Telegram Bot API UI layer (Kurigram + aiogram hybrid)
#
# Why two libraries:
#   Kurigram (MTProto) runs the bot and supports button `style`, `copy_text`
#   and `icon_custom_emoji_id` — but it has NO `disabled` button field.
#   aiogram 3.31 targets Bot API 10.3 and *does* model `disabled`
#   (DisabledButton) plus CopyTextButton.
#
# So: build keyboards declaratively here, then render to whichever backend is
# in play. Kurigram renders natively where it can and degrades gracefully
# where it cannot (a "disabled" button becomes an inert no-op callback, which
# is what a disabled button does anyway). If the aiogram bridge is enabled,
# the same spec is sent through the Bot API with true `disabled` support.
#
# Nothing here raises if aiogram is absent — it is an optional dependency.

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from html import escape
from typing import Any, Dict, List, Optional, Sequence

log = logging.getLogger(__name__)

# ---------------------------------------------------------------- backends
try:
    from pyrogram.types import (
        InlineKeyboardButton as _KB,
        InlineKeyboardMarkup as _KM,
    )

    HAS_PYRO = True
except Exception:  # pragma: no cover
    HAS_PYRO = False

try:
    from pyrogram.enums import ButtonStyle as _PyroStyle

    HAS_PYRO_STYLE = True
except Exception:
    HAS_PYRO_STYLE = False

try:
    import aiogram  # noqa: F401
    from aiogram.types import (
        InlineKeyboardButton as _AB,
        InlineKeyboardMarkup as _AM,
    )

    HAS_AIOGRAM = True
    AIOGRAM_VERSION = getattr(aiogram, "__version__", "?")
    AIOGRAM_API = getattr(aiogram, "__api_version__", "?")
except Exception:
    HAS_AIOGRAM = False
    AIOGRAM_VERSION = AIOGRAM_API = None

# aiogram models `disabled` as an object, older builds as a bool.
_AIOGRAM_DISABLED_OBJ = None
if HAS_AIOGRAM:
    try:
        from aiogram.types.disabled_button import DisabledButton as _DB

        _AIOGRAM_DISABLED_OBJ = _DB
    except Exception:
        _AIOGRAM_DISABLED_OBJ = None


# Button styles as understood by Bot API / MTProto.
PRIMARY = "primary"
DANGER = "danger"
SUCCESS = "success"
DEFAULT = "default"

_PYRO_STYLE_MAP = {}
if HAS_PYRO_STYLE:
    _PYRO_STYLE_MAP = {
        PRIMARY: _PyroStyle.PRIMARY,
        DANGER: _PyroStyle.DANGER,
        SUCCESS: _PyroStyle.SUCCESS,
        DEFAULT: _PyroStyle.DEFAULT,
    }

# Callback data used by inert buttons; a global handler answers it silently.
NOOP_CB = "ui_noop"


@dataclass
class Btn:
    """Backend-agnostic button spec.

    style    — "primary" | "danger" | "success" | None
    disabled — greyed out and unclickable (native on aiogram, emulated on
               Kurigram by routing to an inert callback)
    copy     — tap-to-copy text (Bot API 9.x CopyTextButton)
    emoji_id — custom emoji shown on the button
    """

    text: str
    data: Optional[str] = None
    url: Optional[str] = None
    style: Optional[str] = None
    disabled: bool = False
    copy: Optional[str] = None
    emoji_id: Optional[str] = None
    # Pure indicators (e.g. "2/5") look wrong with a disabled marker.
    mark_disabled: bool = True

    def render_pyro(self):
        if not HAS_PYRO:
            raise RuntimeError("pyrogram/kurigram not available")
        kw: Dict[str, Any] = {}

        if self.copy is not None:
            kw["copy_text"] = self.copy[:256]
        elif self.url and not self.disabled:
            kw["url"] = self.url
        else:
            # Disabled buttons must stay clickable-but-inert on MTProto,
            # otherwise Telegram rejects the row for having no action.
            kw["callback_data"] = NOOP_CB if self.disabled else (self.data or NOOP_CB)

        if self.style and self.style != DEFAULT and _PYRO_STYLE_MAP:
            st = _PYRO_STYLE_MAP.get(self.style)
            if st is not None:
                kw["style"] = st
        if self.emoji_id:
            kw["icon_custom_emoji_id"] = self.emoji_id

        text = self.text
        if self.disabled and self.mark_disabled:
            # Visual cue, since MTProto cannot actually grey the button out.
            text = f"· {text} ·"
        return _KB(text, **kw)

    def render_aiogram(self):
        if not HAS_AIOGRAM:
            raise RuntimeError("aiogram not available")
        kw: Dict[str, Any] = {"text": self.text}
        if self.copy is not None:
            from aiogram.types import CopyTextButton

            kw["copy_text"] = CopyTextButton(text=self.copy[:256])
        elif self.url:
            kw["url"] = self.url
        else:
            kw["callback_data"] = self.data or NOOP_CB
        if self.style and self.style != DEFAULT:
            kw["style"] = self.style
        if self.emoji_id:
            kw["icon_custom_emoji_id"] = self.emoji_id
        if self.disabled:
            kw["disabled"] = _AIOGRAM_DISABLED_OBJ() if _AIOGRAM_DISABLED_OBJ else True
        return _AB(**kw)


class Keyboard:
    """Declarative keyboard that renders to Kurigram or aiogram."""

    def __init__(self, rows: Optional[List[List[Btn]]] = None):
        self.rows: List[List[Btn]] = rows or []

    def row(self, *buttons: Btn) -> "Keyboard":
        real = [b for b in buttons if b is not None]
        if real:
            self.rows.append(list(real))
        return self

    def grid(self, buttons: Sequence[Btn], per_row: int = 5) -> "Keyboard":
        row: List[Btn] = []
        for b in buttons:
            row.append(b)
            if len(row) == per_row:
                self.rows.append(row)
                row = []
        if row:
            self.rows.append(row)
        return self

    def render(self):
        if not HAS_PYRO:
            return None
        return _KM([[b.render_pyro() for b in row] for row in self.rows])

    def render_aiogram(self):
        if not HAS_AIOGRAM:
            return None
        return _AM(
            inline_keyboard=[[b.render_aiogram() for b in row] for row in self.rows]
        )

    # Convenience so existing `reply_markup=kb` call sites keep working.
    def __iter__(self):
        return iter(self.render().inline_keyboard)


# ------------------------------------------------------------ rich text
def h(text: Any) -> str:
    return escape(str(text), quote=False)


def heading(text: str, level: int = 1, emoji: str = "") -> str:
    """Rich heading. Telegram has no <h1>, so emulate a visual hierarchy."""
    prefix = f"{emoji} " if emoji else ""
    if level == 1:
        # Upper-case the raw text *before* escaping: uppercasing afterwards
        # turns "&amp;" into "&AMP;", which Telegram rejects as bad HTML.
        return f"<b>{prefix}{h(str(text).upper())}</b>"
    if level == 2:
        return f"<b>{prefix}{h(text)}</b>"
    return f"<u>{prefix}{h(text)}</u>"


def divider(width: int = 26, char: str = "━") -> str:
    return char * width


def quote(text: str, expandable: bool = False) -> str:
    """Blockquote; `expandable` uses the collapsible variant (Bot API 7.4)."""
    return (
        f"<blockquote expandable>{text}</blockquote>"
        if expandable
        else f"<blockquote>{text}</blockquote>"
    )


def spoiler(text: str) -> str:
    return f"<tg-spoiler>{h(text)}</tg-spoiler>"


def code(text: Any) -> str:
    return f"<code>{h(text)}</code>"


def pre(text: str, language: str = "") -> str:
    if language:
        return f'<pre><code class="language-{language}">{h(text)}</code></pre>'
    return f"<pre>{h(text)}</pre>"


def emoji(emoji_id: str, fallback: str = "⭐") -> str:
    """Custom (premium) emoji, degrading to a plain one for non-premium."""
    return f'<tg-emoji emoji-id="{h(emoji_id)}">{fallback}</tg-emoji>'


def _dwidth(s: str) -> int:
    """Display width: emoji and CJK occupy two cells in monospace fonts."""
    import unicodedata

    w = 0
    for ch in s:
        if unicodedata.combining(ch):
            continue
        if unicodedata.east_asian_width(ch) in ("W", "F") or ord(ch) >= 0x1F300:
            w += 2
        else:
            w += 1
    return w


def _pad(s: str, width: int, how: str = "l") -> str:
    gap = max(0, width - _dwidth(s))
    if how == "r":
        return " " * gap + s
    if how == "c":
        left = gap // 2
        return " " * left + s + " " * (gap - left)
    return s + " " * gap


def table(
    headers: Sequence[str],
    rows: Sequence[Sequence[Any]],
    align: Optional[Sequence[str]] = None,
    max_col: int = 18,
) -> str:
    """Monospaced table with box-drawing borders.

    Telegram has no table markup, so render inside <pre> where the font is
    fixed-width and column alignment survives.
    """
    cols = len(headers)
    align = list(align or ["l"] * cols)
    align += ["l"] * (cols - len(align))

    def cell(v: Any) -> str:
        s = str(v)
        if _dwidth(s) <= max_col:
            return s
        out = ""
        for ch in s:
            if _dwidth(out + ch) > max_col - 1:
                break
            out += ch
        return out + "…"

    body = [[cell(r[i]) if i < len(r) else "" for i in range(cols)] for r in rows]
    widths = [_dwidth(cell(hd)) for hd in headers]
    for r in body:
        for i, v in enumerate(r):
            widths[i] = max(widths[i], _dwidth(v))

    def fmt(vals: Sequence[str]) -> str:
        return "│ " + " │ ".join(
            _pad(v, widths[i], align[i]) for i, v in enumerate(vals)
        ) + " │"

    top = "┌─" + "─┬─".join("─" * w for w in widths) + "─┐"
    mid = "├─" + "─┼─".join("─" * w for w in widths) + "─┤"
    bot = "└─" + "─┴─".join("─" * w for w in widths) + "─┘"
    lines = [top, fmt([cell(x) for x in headers]), mid]
    lines += [fmt(r) for r in body]
    lines.append(bot)
    return pre("\n".join(lines))


def kv_table(pairs: Sequence[tuple], max_col: int = 22) -> str:
    return table(["Field", "Value"], [[k, v] for k, v in pairs], max_col=max_col)


def bar(pct: float, width: int = 12, fill: str = "█", empty: str = "░") -> str:
    pct = max(0.0, min(100.0, float(pct or 0)))
    n = int(round(width * pct / 100.0))
    return fill * n + empty * (width - n)


class Card:
    """Builder for a consistent, modern message card."""

    def __init__(self, title: str = "", emoji_str: str = "", level: int = 1):
        self.parts: List[str] = []
        if title:
            self.parts.append(heading(title, level, emoji_str))
            self.parts.append(divider())

    def line(self, text: str = "") -> "Card":
        self.parts.append(text)
        return self

    def field(self, label: str, value: Any) -> "Card":
        self.parts.append(f"<b>{h(label)}:</b> {value}")
        return self

    def section(self, title: str, body: str, expandable: bool = False) -> "Card":
        self.parts.append(heading(title, 2))
        self.parts.append(quote(body, expandable))
        return self

    def table(self, headers, rows, **kw) -> "Card":
        self.parts.append(table(headers, rows, **kw))
        return self

    def progress(self, pct: float, label: str = "") -> "Card":
        self.parts.append(f"{bar(pct)} <b>{pct:.0f}%</b>" + (f" {label}" if label else ""))
        return self

    def divider(self) -> "Card":
        self.parts.append(divider())
        return self

    def note(self, text: str) -> "Card":
        self.parts.append(f"<i>{text}</i>")
        return self

    def build(self) -> str:
        return "\n".join(p for p in self.parts if p is not None)

    __str__ = build


def backend_report() -> Dict[str, Any]:
    return {
        "kurigram": HAS_PYRO,
        "kurigram_styles": HAS_PYRO_STYLE,
        "aiogram": HAS_AIOGRAM,
        "aiogram_version": AIOGRAM_VERSION,
        "aiogram_bot_api": AIOGRAM_API,
        "native_disabled": bool(HAS_AIOGRAM),
    }
