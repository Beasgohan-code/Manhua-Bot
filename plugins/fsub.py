
from pyrogram import Client, filters, StopPropagation
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, CallbackQuery
from pyrogram.enums import ChatMemberStatus
from pyrogram.errors import UserNotParticipant, Forbidden
from config import Config
import logging
import time
from functools import wraps
log = logging.getLogger(__name__)
_fsub_cache = {}
_FSUB_CACHE_TTL = 300
_FSUB_CLEANUP_INTERVAL = 600
_last_fsub_cleanup = 0
def _cleanup_fsub_cache():
    global _last_fsub_cleanup
    now = time.time()
    if now - _last_fsub_cleanup < _FSUB_CLEANUP_INTERVAL:
        return
    _last_fsub_cleanup = now
    expired = [uid for uid, (_, ts) in _fsub_cache.items() if now - ts > _FSUB_CACHE_TTL]
    for uid in expired:
        del _fsub_cache[uid]
def invalidate_fsub_cache(uid: int):
    _fsub_cache.pop(uid, None)
async def get_not_subscribed(c: Client, uid: int):
    if not Config.FSUB_CHANNELS:
        return []
    if uid in Config.OWNER_ID:
        return []
    _cleanup_fsub_cache()
    now = time.time()
    if uid in _fsub_cache:
        cached_result, cached_ts = _fsub_cache[uid]
        if now - cached_ts < _FSUB_CACHE_TTL:
            return cached_result
    not_subscribed = []
    for channel in Config.FSUB_CHANNELS:
        try:
            member = await c.get_chat_member(channel, uid)
            is_joined = member.status in (
                ChatMemberStatus.MEMBER,
                ChatMemberStatus.ADMINISTRATOR,
                ChatMemberStatus.OWNER
            )
            if not is_joined:
                not_subscribed.append(channel)
        except (UserNotParticipant, Forbidden):
            not_subscribed.append(channel)
        except Exception:
            not_subscribed.append(channel)
    _fsub_cache[uid] = (not_subscribed, now)
    return not_subscribed
async def check_fsub(c: Client, u):
    if not Config.FSUB_CHANNELS:
        return True
    uid = u.from_user.id if u.from_user else None
    if not uid or uid in Config.OWNER_ID:
        return True
    missing_chans = await get_not_subscribed(c, uid)
    if not missing_chans:
        return True
    try:
        btns = []
        for channel in missing_chans:
            try:
                chat = await c.get_chat(channel)
                link = chat.invite_link or f"https://t.me/{chat.username}" if chat.username else None
                if link:
                    btns.append([InlineKeyboardButton(f"❏ ᴊᴏɪɴ {chat.title}", url=link)])
            except Exception as e:
                log.error(f"Error fetching chat {channel} for fsub: {e}")
                continue
        if not btns:
            return True
        btns.append([InlineKeyboardButton("🔄 ᴛʀʏ ᴀɢᴀɪɴ", callback_data="check_fsub")])
        txt = (
            "<b>░ ᴘᴇʀᴍɪꜱꜱɪᴏɴ ᴅᴇɴɪᴇᴅ</b>\n\n"
            "<blockquote><i>You must join our update channels below to continue using this bot. "
            "This helps us maintain the service and keep you updated!</i></blockquote>\n\n"
            "<b>» ᴘʟᴇᴀꜱᴇ ᴊᴏɪɴ ᴀʟʟ ᴄʜᴀɴɴᴇʟꜱ ᴛᴏ ᴘʀᴏᴄᴇᴇᴅ</b>"
        )
        if isinstance(u, Message):
            await u.reply_text(txt, reply_markup=InlineKeyboardMarkup(btns))
        elif isinstance(u, CallbackQuery):
            await u.message.edit_text(txt, reply_markup=InlineKeyboardMarkup(btns))
        return False
    except Exception as e:
        log.error(f"Error in check_fsub logic: {e}")
        return True
def force_sub(func):
    @wraps(func)
    async def wrapper(c: Client, u, *args, **kwargs):
        if not await check_fsub(c, u):
            raise StopPropagation
        return await func(c, u, *args, **kwargs)
    return wrapper
@Client.on_callback_query(filters.regex("^check_fsub$"))
async def check_fsub_callback(c: Client, q):
    invalidate_fsub_cache(q.from_user.id)
    missing_chans = await get_not_subscribed(c, q.from_user.id)
    if not missing_chans:
        txt = (
            "<b>✓ ᴀᴄᴄᴇꜱꜱ ɢʀᴀɴᴛᴇᴅ</b>\n\n"
            "<blockquote><i>Thank you for supporting us! You have successfully joined all required channels. "
            "You can now use all features of the bot.</i></blockquote>\n\n"
            "<b>» ᴘʀᴇꜱꜱ ᴛʜᴇ ʙᴜᴛᴛᴏɴ ʙᴇʟᴏᴡ ᴛᴏ ꜱᴛᴀʀᴛ</b>"
        )
        await q.message.edit_text(
            txt,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◂ ʙᴀᴄᴋ ᴛᴏ ᴍᴇɴᴜ", callback_data="start_back")]])
        )
    else:
        await q.answer("❌ You haven't joined all channels yet!", show_alert=True)
