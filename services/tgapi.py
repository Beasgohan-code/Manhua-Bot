# Manhua-Bot - Bot API 10.3 transport (aiogram)
#
# Kurigram (MTProto) runs the bot: it holds the session, dispatches handlers
# and uploads large files. But MTProto does not expose several Bot API 10.x
# features we want:
#
#   * sendRichMessage            (Bot API 10.1) real tables/headings/lists
#   * disabled buttons           (10.3) DisabledButton
#   * force_reply on inline kb   (10.3)
#   * ephemeral messages         (10.2/10.3) visible to one user in a group
#   * message_effect_id          animated effects in private chats
#
# So we keep one shared aiogram Bot as a *transport* for those calls and fall
# back to Kurigram whenever the Bot API path is unavailable or errors.
#
# Everything here is defensive: if aiogram is missing, the token is unset, or
# the API server is older than 10.3, callers still work via the fallback.

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Optional

log = logging.getLogger(__name__)

try:
    import aiogram
    from aiogram import Bot
    from aiogram.client.default import DefaultBotProperties
    from aiogram.enums import ParseMode

    HAS_AIOGRAM = True
    AIOGRAM_VERSION = getattr(aiogram, "__version__", "?")
    AIOGRAM_API = getattr(aiogram, "__api_version__", "?")
except Exception:  # pragma: no cover
    HAS_AIOGRAM = False
    AIOGRAM_VERSION = AIOGRAM_API = None

_bot = None
_lock = asyncio.Lock()
_state: Dict[str, Any] = {
    "probed": False,
    "ok": False,
    "reason": "not probed",
    "username": None,
    "rich": False,
}

# After this many consecutive transport errors we stop attempting the Bot API
# and go straight to the Kurigram fallback; otherwise every send pays a full
# connection timeout before falling back.
_FAIL_LIMIT = 3
_fails = {"n": 0, "disabled": False}


def transport_healthy() -> bool:
    return not _fails["disabled"]


def _note_failure(exc: Exception) -> None:
    _fails["n"] += 1
    if _fails["n"] >= _FAIL_LIMIT and not _fails["disabled"]:
        _fails["disabled"] = True
        log.warning(
            f"[TGAPI] Bot API transport disabled after {_FAIL_LIMIT} failures "
            f"({type(exc).__name__}); using Kurigram only"
        )


def _note_success() -> None:
    _fails["n"] = 0
    if _fails["disabled"]:
        _fails["disabled"] = False
        log.info("[TGAPI] Bot API transport recovered")


def reset_transport() -> None:
    _fails["n"] = 0
    _fails["disabled"] = False


def _token() -> str:
    try:
        from config import Config

        return getattr(Config, "BOT_TOKEN", "") or ""
    except Exception:
        return ""


def configured() -> bool:
    """Cheap check — does not touch the network."""
    return bool(HAS_AIOGRAM and _token() and not _fails["disabled"])


async def get_bot():
    """Shared aiogram Bot, created lazily. None when unavailable."""
    global _bot
    if not configured():
        return None
    if _bot is not None:
        return _bot
    async with _lock:
        if _bot is None:
            _bot = Bot(
                token=_token(),
                default=DefaultBotProperties(parse_mode=ParseMode.HTML),
            )
    return _bot


async def probe(timeout: float = 10.0) -> Dict[str, Any]:
    """Verify the token actually works and cache the result."""
    if _state["probed"]:
        return dict(_state)
    _state["probed"] = True
    if not HAS_AIOGRAM:
        _state["reason"] = "aiogram not installed"
        return dict(_state)
    if not _token():
        _state["reason"] = "BOT_TOKEN not configured"
        return dict(_state)
    try:
        bot = await get_bot()
        me = await asyncio.wait_for(bot.get_me(), timeout=timeout)
        _state.update(ok=True, reason="ready", username=me.username, rich=True)
    except Exception as exc:
        _state["reason"] = f"{type(exc).__name__}: {str(exc)[:120]}"
        # A failed probe means no usable transport; release the session now
        # rather than leaking an open aiohttp connector.
        await close()
    return dict(_state)


def status() -> Dict[str, Any]:
    st = dict(_state)
    st.update(
        aiogram=HAS_AIOGRAM,
        version=AIOGRAM_VERSION,
        api=AIOGRAM_API,
        configured=bool(HAS_AIOGRAM and _token()),
        healthy=transport_healthy(),
        failures=_fails["n"],
    )
    return st


def _markup(reply_markup, aiogram_side: bool = True):
    """Accept a tgui.Keyboard or a raw markup object."""
    if reply_markup is None:
        return None
    if aiogram_side and hasattr(reply_markup, "render_aiogram"):
        return reply_markup.render_aiogram()
    if not aiogram_side and hasattr(reply_markup, "render"):
        return reply_markup.render()
    return reply_markup


def ephemeral(
    user_id: int,
    callback_query_id: Optional[str] = None,
    replace: bool = False,
):
    """Build EphemeralMessageParameters (Bot API 10.3).

    An ephemeral message is delivered into a group chat but is visible only
    to `user_id` — ideal for per-user progress and errors that should not
    spam everyone else.
    """
    if not HAS_AIOGRAM:
        return None
    try:
        from aiogram.types import EphemeralMessageParameters

        kw: Dict[str, Any] = {"receiver_user_id": user_id}
        if callback_query_id:
            kw["callback_query_id"] = callback_query_id
        if replace:
            kw["replace_callback_query_message"] = True
        return EphemeralMessageParameters(**kw)
    except Exception as exc:
        log.debug(f"[TGAPI] ephemeral params unsupported: {exc}")
        return None


async def send_message(
    chat_id: int,
    text: str,
    reply_markup=None,
    fallback_client=None,
    ephemeral_for: Optional[int] = None,
    callback_query_id: Optional[str] = None,
    effect_id: Optional[str] = None,
    **kwargs,
):
    """Send via Bot API (10.3 features), falling back to Kurigram.

    Returns (message, used_bot_api).
    """
    if configured():
        try:
            bot = await get_bot()
            extra = dict(kwargs)
            if ephemeral_for is not None:
                params = ephemeral(ephemeral_for, callback_query_id)
                if params is not None:
                    extra["ephemeral_message_parameters"] = params
            if effect_id:
                extra["message_effect_id"] = effect_id
            msg = await bot.send_message(
                chat_id=chat_id,
                text=text,
                reply_markup=_markup(reply_markup, True),
                **extra,
            )
            _note_success()
            return msg, True
        except Exception as exc:
            _note_failure(exc)
            log.warning(f"[TGAPI] send_message fell back: {exc}")

    if fallback_client is not None:
        msg = await fallback_client.send_message(
            chat_id, text, reply_markup=_markup(reply_markup, False)
        )
        return msg, False
    return None, False


async def close():
    """Close the aiogram HTTP session (call on shutdown)."""
    global _bot
    if _bot is not None:
        try:
            await _bot.session.close()
        except Exception:
            pass
        _bot = None
