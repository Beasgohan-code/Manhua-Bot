# Manhua-Bot - native Telegram Rich Messages (Bot API 10.1+)
#
# Telegram shipped "Rich Messages" in Bot API 10.1 (June 2026) and extended
# them through 10.3. Unlike classic HTML — which only has <b>/<i>/<code>/
# <pre>/<blockquote> and forces us to fake tables inside <pre> — rich messages
# support REAL structural blocks:
#
#   <h1>..<h6>                       section headings
#   <table bordered striped compact> real tables, per-column align, caption
#   <ul>/<ol>/<li>                   lists, ordered lists, checkboxes
#   <details open><summary>          collapsible sections
#   <blockquote expandable><cite>    quotes with an author credit
#   <aside>                          pull quotes
#   <hr/> <footer> <p>               dividers, footers, paragraphs
#   <mark> <sub> <sup>               marked / sub / superscript
#   <tg-math> <tg-math-block>        LaTeX
#   <tg-time unix= format=>          locale-aware date/time entity
#
# Rich messages are sent with the `sendRichMessage` Bot API method, which
# MTProto/Kurigram does not expose. The bot therefore keeps Kurigram as its
# runtime and uses an aiogram Bot purely as a transport for rich sends,
# degrading to classic HTML when that is unavailable.
#
# IMPORTANT: in rich HTML a bare "\n" is insignificant whitespace and gets
# collapsed, so every logical line break must be an explicit <br/>.

from __future__ import annotations

import html as _html
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence, Union

log = logging.getLogger(__name__)

_BLOCK_TO_NEWLINE = None


def to_classic(html_text: str) -> str:
    """Downgrade rich-only markup to tags classic Telegram HTML accepts.

    Callers pass rich fragments (e.g. "<p>a</p><p>b</p>") into quote()/
    details(); those tags are invalid in a normal sendMessage and Telegram
    rejects the whole message, so strip them for the fallback path.
    """
    import re as _re

    t = html_text
    t = _re.sub(r"</(?:p|div|li|tr|h[1-6]|footer)>", "\n", t, flags=_re.I)
    t = _re.sub(r"<br\s*/?>", "\n", t, flags=_re.I)
    t = _re.sub(r"<li[^>]*>", "• ", t, flags=_re.I)
    # drop any remaining rich-only container tags, keep their text
    t = _re.sub(
        r"</?(?:p|div|table|caption|thead|tbody|tr|th|td|ul|ol|details|"
        r"summary|aside|cite|footer|figure|input|hr|h[1-6]|mark|sub|sup)"
        r"[^>]*>",
        "",
        t,
        flags=_re.I,
    )
    t = _re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()


__all__ = [
    "RichDoc", "esc", "b", "i", "u", "s", "mark", "sub", "sup", "to_classic",
    "spoiler", "codespan", "a", "emoji", "dt", "math",
    "rich_available", "send_rich", "RICH_LIMIT",
]

# Telegram truncates very long messages; rich payloads share the caption cap.
RICH_LIMIT = 4096


# --------------------------------------------------------------- inline text
def esc(text: Any) -> str:
    return _html.escape(str(text), quote=False)


def b(t: Any) -> str:
    return f"<b>{esc(t)}</b>"


def i(t: Any) -> str:
    return f"<i>{esc(t)}</i>"


def u(t: Any) -> str:
    return f"<u>{esc(t)}</u>"


def s(t: Any) -> str:
    return f"<s>{esc(t)}</s>"


def mark(t: Any) -> str:
    """Highlighted text — rich messages only."""
    return f"<mark>{esc(t)}</mark>"


def sub(t: Any) -> str:
    return f"<sub>{esc(t)}</sub>"


def sup(t: Any) -> str:
    return f"<sup>{esc(t)}</sup>"


def spoiler(t: Any) -> str:
    return f"<tg-spoiler>{esc(t)}</tg-spoiler>"


def codespan(t: Any) -> str:
    return f"<code>{esc(t)}</code>"


def a(text: Any, url: str) -> str:
    return f'<a href="{_html.escape(str(url), quote=True)}">{esc(text)}</a>'


def emoji(emoji_id: str, fallback: str = "⭐") -> str:
    return f'<tg-emoji emoji-id="{esc(emoji_id)}">{fallback}</tg-emoji>'


def dt(unix_time: int, fmt: str = "wDT", label: Optional[str] = None) -> str:
    """A date_time entity — Telegram renders it in the viewer's locale/timezone."""
    inner = esc(label) if label is not None else ""
    return f'<tg-time unix="{int(unix_time)}" format="{esc(fmt)}">{inner}</tg-time>'


def math(latex: str, block: bool = False) -> str:
    tag = "tg-math-block" if block else "tg-math"
    return f"<{tag}>{esc(latex)}</{tag}>"


_ALIGN = {"l": "left", "r": "right", "c": "center",
          "left": "left", "right": "right", "center": "center"}


@dataclass
class RichDoc:
    """Builder for a native rich message, with a classic-HTML fallback.

    Every method appends a structural block. `.html()` returns rich HTML for
    sendRichMessage; `.fallback()` returns classic HTML that renders
    acceptably through ordinary sendMessage.
    """

    blocks: List[str] = field(default_factory=list)
    _fallback: List[str] = field(default_factory=list)

    # -------------------------------------------------------------- headings
    def heading(self, text: str, level: int = 1, emoji_str: str = "") -> "RichDoc":
        level = max(1, min(6, int(level)))
        prefix = f"{emoji_str} " if emoji_str else ""
        self.blocks.append(f"<h{level}>{prefix}{esc(text)}</h{level}>")
        if self._fallback:
            self._fallback.append("")  # visual separation in classic HTML
        self._fallback.append(f"<b>{prefix}{esc(text)}</b>")
        return self

    def paragraph(self, html_text: str) -> "RichDoc":
        self.blocks.append(f"<p>{html_text}</p>")
        self._fallback.append(to_classic(html_text))
        return self

    # alias
    line = paragraph

    def field_row(self, label: str, value: Any) -> "RichDoc":
        self.blocks.append(f"<p><b>{esc(label)}:</b> {value}</p>")
        self._fallback.append(f"<b>{esc(label)}:</b> {value}")
        return self

    def divider(self) -> "RichDoc":
        self.blocks.append("<hr/>")
        self._fallback.append("━" * 26)
        return self

    def footer(self, html_text: str) -> "RichDoc":
        self.blocks.append(f"<footer>{html_text}</footer>")
        # Avoid <i><i>..</i></i> when the caller already styled the text.
        stripped = html_text.strip()
        if stripped.startswith("<i>") and stripped.endswith("</i>"):
            self._fallback.append(stripped)
        else:
            self._fallback.append(f"<i>{to_classic(html_text)}</i>")
        return self

    # ----------------------------------------------------------------- table
    def table(
        self,
        headers: Sequence[Any],
        rows: Sequence[Sequence[Any]],
        align: Optional[Sequence[str]] = None,
        caption: str = "",
        bordered: bool = True,
        striped: bool = True,
        compact: bool = False,
        escape_cells: bool = True,
    ) -> "RichDoc":
        """A real <table>. Telegram lays out the columns natively."""
        attrs = ""
        if bordered:
            attrs += " bordered"
        if striped:
            attrs += " striped"
        if compact:
            attrs += " compact"

        cols = len(headers)
        aligns = list(align or [])
        aligns += ["l"] * (cols - len(aligns))

        def cell(v: Any) -> str:
            return esc(v) if escape_cells else str(v)

        out = [f"<table{attrs}>"]
        if caption:
            out.append(f"<caption>{esc(caption)}</caption>")
        if headers:
            out.append("<tr>" + "".join(f"<th>{cell(hd)}</th>" for hd in headers) + "</tr>")
        for r in rows:
            tds = []
            for idx in range(cols):
                val = r[idx] if idx < len(r) else ""
                al = _ALIGN.get(str(aligns[idx]).lower(), "left")
                tds.append(f'<td align="{al}">{cell(val)}</td>')
            out.append("<tr>" + "".join(tds) + "</tr>")
        out.append("</table>")
        self.blocks.append("".join(out))

        # Fallback: the monospaced renderer we already ship.
        from utils.tgui import table as _mono

        self._fallback.append(_mono(list(headers), [list(r) for r in rows], align=aligns))
        return self

    # ------------------------------------------------------------------ list
    def bullets(self, items: Iterable[Any], escape_items: bool = True) -> "RichDoc":
        vals = list(items)
        if not vals:
            return self
        lis = "".join(
            f"<li>{esc(x) if escape_items else x}</li>" for x in vals
        )
        self.blocks.append(f"<ul>{lis}</ul>")
        self._fallback.append(
            "\n".join(f"• {esc(x) if escape_items else x}" for x in vals)
        )
        return self

    def numbered(self, items: Iterable[Any], start: int = 1,
                 escape_items: bool = True) -> "RichDoc":
        vals = list(items)
        if not vals:
            return self
        lis = "".join(
            f"<li>{esc(x) if escape_items else x}</li>" for x in vals
        )
        attr = f' start="{int(start)}"' if start != 1 else ""
        self.blocks.append(f"<ol{attr}>{lis}</ol>")
        self._fallback.append(
            "\n".join(
                f"{n}. {esc(x) if escape_items else x}"
                for n, x in enumerate(vals, start)
            )
        )
        return self

    def checklist(self, items: Sequence[tuple]) -> "RichDoc":
        """items: sequence of (text, done: bool) — renders real checkboxes."""
        if not items:
            return self
        lis = []
        for text, done in items:
            chk = ' checked=""' if done else ""
            lis.append(f'<li><input type="checkbox"{chk}/>{esc(text)}</li>')
        self.blocks.append(f"<ul>{''.join(lis)}</ul>")
        self._fallback.append(
            "\n".join(f"{'☑' if d else '☐'} {esc(t)}" for t, d in items)
        )
        return self

    # ------------------------------------------------------------- quotation
    def quote(self, html_text: str, credit: str = "",
              expandable: bool = False) -> "RichDoc":
        cite = f"<cite>{esc(credit)}</cite>" if credit else ""
        attr = " expandable" if expandable else ""
        self.blocks.append(f"<blockquote{attr}>{html_text}{cite}</blockquote>")
        self._fallback.append(
            f"<blockquote{' expandable' if expandable else ''}>"
            + to_classic(html_text)
            + (f"\n— {esc(credit)}" if credit else "")
            + "</blockquote>"
        )
        return self

    def pull_quote(self, html_text: str, credit: str = "") -> "RichDoc":
        cite = f"<cite>{esc(credit)}</cite>" if credit else ""
        self.blocks.append(f"<aside>{html_text}{cite}</aside>")
        self._fallback.append(f"<i>{to_classic(html_text)}</i>")
        return self

    def details(self, summary: str, html_body: str, open_: bool = False) -> "RichDoc":
        """Collapsible section — great for long logs or optional detail."""
        attr = " open" if open_ else ""
        self.blocks.append(
            f"<details{attr}><summary>{esc(summary)}</summary>{html_body}</details>"
        )
        self._fallback.append(
            f"<b>{esc(summary)}</b>\n<blockquote expandable>"
            + to_classic(html_body)
            + "</blockquote>"
        )
        return self

    def code_block(self, text: str, language: str = "") -> "RichDoc":
        if language:
            body = f'<pre><code class="language-{esc(language)}">{esc(text)}</code></pre>'
        else:
            body = f"<pre>{esc(text)}</pre>"
        self.blocks.append(body)
        self._fallback.append(body)
        return self

    def progress(self, pct: float, label: str = "") -> "RichDoc":
        from utils.tgui import bar

        txt = f"{bar(pct)} <b>{pct:.0f}%</b>" + (f" {esc(label)}" if label else "")
        self.blocks.append(f"<p>{txt}</p>")
        self._fallback.append(txt)
        return self

    # ---------------------------------------------------------------- output
    def html(self) -> str:
        """Rich HTML for sendRichMessage."""
        return "".join(self.blocks)

    def fallback(self, limit: int = RICH_LIMIT) -> str:
        """Classic HTML for ordinary sendMessage."""
        lines = []
        for part in self._fallback:
            if part == "" and (not lines or lines[-1] == ""):
                continue  # never emit consecutive blank lines
            lines.append(part)
        out = "\n".join(lines).strip()
        return out[:limit]

    build = fallback  # drop-in for RichMessage.build()

    def __str__(self) -> str:
        return self.fallback()


# ------------------------------------------------------------------ transport
_rich_bot = None
_rich_state: Dict[str, Any] = {"checked": False, "ok": False, "reason": ""}


def rich_available() -> Dict[str, Any]:
    """Whether native rich messages can actually be sent from this process."""
    if _rich_state["checked"]:
        return dict(_rich_state)
    _rich_state["checked"] = True
    try:
        import aiogram  # noqa: F401
        from aiogram.methods import SendRichMessage  # noqa: F401
        from aiogram.types import InputRichMessage  # noqa: F401
    except Exception as exc:
        _rich_state["reason"] = f"aiogram missing or too old ({exc})"
        return dict(_rich_state)

    try:
        from config import Config

        token = getattr(Config, "BOT_TOKEN", "") or ""
    except Exception:
        token = ""
    if not token:
        _rich_state["reason"] = "BOT_TOKEN not configured"
        return dict(_rich_state)

    _rich_state["ok"] = True
    _rich_state["reason"] = "ready"
    return dict(_rich_state)


async def _get_bot():
    global _rich_bot
    if _rich_bot is not None:
        return _rich_bot
    from aiogram import Bot
    from config import Config

    _rich_bot = Bot(token=Config.BOT_TOKEN)
    return _rich_bot


async def send_rich(
    chat_id: int,
    doc: RichDoc,
    reply_markup=None,
    fallback_client=None,
    **kwargs,
):
    """Send `doc` as a native rich message, falling back to classic HTML.

    `fallback_client` is the Kurigram client used when rich sending is
    unavailable or fails. Returns the sent message, or None.
    """
    state = rich_available()
    if state["ok"]:
        try:
            from aiogram.types import InputRichMessage

            bot = await _get_bot()
            payload = InputRichMessage(html=doc.html())
            markup = None
            if reply_markup is not None:
                markup = (
                    reply_markup.render_aiogram()
                    if hasattr(reply_markup, "render_aiogram")
                    else reply_markup
                )
            return await bot.send_rich_message(
                chat_id=chat_id, rich_message=payload, reply_markup=markup, **kwargs
            )
        except Exception as exc:
            log.warning(f"[RICH] send failed, using classic HTML: {exc}")

    if fallback_client is not None:
        markup = (
            reply_markup.render()
            if hasattr(reply_markup, "render")
            else reply_markup
        )
        return await fallback_client.send_message(
            chat_id, doc.fallback(), reply_markup=markup
        )
    return None


async def close_rich():
    """Release the aiogram session (call on shutdown)."""
    global _rich_bot
    if _rich_bot is not None:
        try:
            await _rich_bot.session.close()
        except Exception:
            pass
        _rich_bot = None
