
import logging
from pyrogram import Client
from pyrogram.errors import FloodWait, ChannelPrivate
import asyncio
log = logging.getLogger(__name__)
async def fetch_channel_thumb(bot: Client, cid: int) -> bytes | None:
    try:
        log.info(f"[THUMB] Scanning msgs 1-5 in channel {cid}")
        for mid in range(1, 6):
            try:
                msg = await bot.get_messages(cid, mid)
                if not msg:
                    continue
                if msg.photo:
                    log.info(f"[THUMB] Found photo in msg {mid}")
                    fp = await bot.download_media(msg.photo, in_memory=True)
                    if hasattr(fp, 'getvalue'):
                        return fp.getvalue()
                    with open(fp, 'rb') as f:
                        return f.read()
                if msg.document:
                    mime = msg.document.mime_type or ""
                    if mime.startswith("image/"):
                        log.info(f"[THUMB] Found img doc in msg {mid}")
                        fp = await bot.download_media(msg.document, in_memory=True)
                        if hasattr(fp, 'getvalue'):
                            return fp.getvalue()
                        with open(fp, 'rb') as f:
                            return f.read()
            except FloodWait as e:
                log.warning(f"[THUMB] FloodWait {e.value}s at msg {mid}")
                await asyncio.sleep(e.value)
                continue
            except Exception as e:
                log.debug(f"[THUMB] Msg {mid} err: {e}")
                continue
        log.info("[THUMB] No image found in msgs 1-5")
        return None
    except ChannelPrivate:
        log.error(f"[THUMB] Channel {cid} is private")
        return None
    except Exception as e:
        log.error(f"[THUMB] Error: {e}")
        return None
