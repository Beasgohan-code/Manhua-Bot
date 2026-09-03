# Manhua-Bot - progress messages, ephemeral where possible
#
# In a group chat a per-user download produces a stream of progress edits
# every other member has to scroll past. Bot API 10.2/10.3 ephemeral messages
# solve this: the message is delivered to the group but visible only to the
# requesting user.
#
# ProgressMessage picks the best available channel automatically:
#
#   group  + Bot API reachable -> ephemeral message (only the user sees it)
#   private or no Bot API      -> ordinary Kurigram message
#
# Callers use one API (`start` / `update` / `finish`) and never care which.
# Updates are throttled, and identical text is never re-sent, so we do not
# burn rate limit on no-op edits.

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Optional

log = logging.getLogger(__name__)

MIN_INTERVAL = 4.0  # seconds between edits of the same message


class ProgressMessage:
    """One live-updating status message."""

    def __init__(
        self,
        client,
        chat_id: int,
        user_id: int,
        *,
        ephemeral: bool = True,
        min_interval: float = MIN_INTERVAL,
        callback_query_id: Optional[str] = None,
    ):
        self.client = client
        self.chat_id = chat_id
        self.user_id = user_id
        self.want_ephemeral = ephemeral
        self.min_interval = min_interval
        self.callback_query_id = callback_query_id

        self.msg = None                  # Kurigram message
        self.eph_id: Optional[int] = None  # ephemeral message id
        self.is_ephemeral = False
        self._last_edit = 0.0
        self._last_text = ""
        self._closed = False

    # ----------------------------------------------------------- internals
    def _is_group(self) -> bool:
        # Telegram user ids are positive; groups/channels are negative.
        return int(self.chat_id) < 0

    async def _try_ephemeral(self, text: str, reply_markup=None) -> bool:
        if not (self.want_ephemeral and self._is_group()):
            return False
        try:
            from services import tgapi

            if not tgapi.configured():
                return False
            bot = await tgapi.get_bot()
            if bot is None:
                return False
            params = tgapi.ephemeral(self.user_id, self.callback_query_id)
            if params is None:
                return False
            sent = await bot.send_message(
                chat_id=self.chat_id,
                text=text,
                reply_markup=(
                    reply_markup.render_aiogram()
                    if hasattr(reply_markup, "render_aiogram")
                    else reply_markup
                ),
                ephemeral_message_parameters=params,
            )
            self.eph_id = getattr(sent, "ephemeral_message_id", None) or getattr(
                sent, "message_id", None
            )
            self.is_ephemeral = self.eph_id is not None
            tgapi._note_success()
            return self.is_ephemeral
        except Exception as exc:
            try:
                from services import tgapi

                tgapi._note_failure(exc)
            except Exception:
                pass
            log.debug(f"[PROGRESS] ephemeral unavailable: {exc}")
            return False

    # -------------------------------------------------------------- public
    async def start(self, text: str, reply_markup=None):
        """Create the message. Returns self so it can be chained."""
        self._last_edit = time.time()
        if await self._try_ephemeral(text, reply_markup):
            self._last_text = text
            return self
        try:
            markup = (
                reply_markup.render() if hasattr(reply_markup, "render")
                else reply_markup
            )
            self.msg = await self.client.send_message(
                self.chat_id, text, reply_markup=markup
            )
            self._last_text = text
        except Exception as exc:
            log.warning(f"[PROGRESS] could not start: {exc}")
        return self

    async def update(self, text: str, force: bool = False, reply_markup=None) -> bool:
        """Throttled edit. Returns True when the message actually changed."""
        if self._closed:
            return False
        now = time.time()
        if not force and now - self._last_edit < self.min_interval:
            return False
        if text == self._last_text:
            return False
        self._last_edit = now
        self._last_text = text

        if self.is_ephemeral and self.eph_id is not None:
            try:
                from services import tgapi

                bot = await tgapi.get_bot()
                await bot.edit_ephemeral_message_text(
                    ephemeral_message_id=self.eph_id, text=text
                )
                return True
            except Exception as exc:
                log.debug(f"[PROGRESS] ephemeral edit failed: {exc}")
                # Fall through: try to keep the user informed via Kurigram.
                self.is_ephemeral = False

        if self.msg is not None:
            try:
                markup = (
                    reply_markup.render() if hasattr(reply_markup, "render")
                    else reply_markup
                )
                await self.msg.edit(text, reply_markup=markup)
                return True
            except Exception as exc:
                if "MESSAGE_NOT_MODIFIED" not in str(exc).upper():
                    log.debug(f"[PROGRESS] edit failed: {exc}")
        return False

    async def finish(self, text: Optional[str] = None, delete: bool = False,
                     reply_markup=None) -> None:
        """Final update, or remove the message entirely."""
        if text is not None:
            await self.update(text, force=True, reply_markup=reply_markup)
        if delete:
            await self.delete()
        self._closed = True

    async def delete(self) -> None:
        if self.is_ephemeral and self.eph_id is not None:
            try:
                from services import tgapi

                bot = await tgapi.get_bot()
                await bot.delete_ephemeral_message(ephemeral_message_id=self.eph_id)
                self.eph_id = None
                return
            except Exception as exc:
                log.debug(f"[PROGRESS] ephemeral delete failed: {exc}")
        if self.msg is not None:
            try:
                await self.msg.delete()
                self.msg = None
            except Exception:
                pass

    @property
    def channel(self) -> str:
        return "ephemeral" if self.is_ephemeral else "message"


async def progress_message(
    client, chat_id: int, user_id: int, text: str, **kw
) -> ProgressMessage:
    """Convenience constructor."""
    return await ProgressMessage(client, chat_id, user_id, **kw).start(text)
