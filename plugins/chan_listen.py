
import re
import time
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup as KM, InlineKeyboardButton as KB
from pyrogram.enums import ParseMode
from pyrogram.handlers import MessageHandler
import logging
from database.db import db
from config import Config
log = logging.getLogger(__name__)
_sub_chans = {}
_dump_chans = {}
_cache_ts = 0
_CACHE_TTL = 300
_bot = None
def init_listener(bot: Client):
    global _bot
    _bot = bot
    log.info("Channel listener initialized")
async def refresh_cache():
    global _sub_chans, _dump_chans, _cache_ts
    try:
        subs = await db.get_subs()
        new_subs = {}
        for s in subs:
            cid = s.get('cid')
            uid = s.get('uid')
            if cid and uid:
                if cid not in new_subs:
                    new_subs[cid] = []
                if uid not in new_subs[cid]:
                    new_subs[cid].append(uid)
        _sub_chans = new_subs
        new_dumps = {}
        cursor = []  # PSQL: dump_cid handled via get_cfg per-user
        async for doc in cursor:
            uid = doc.get('uid')
            cid_val = doc.get('val')
            if uid and cid_val:
                try:
                    cid = int(cid_val)
                    if cid not in new_dumps:
                        new_dumps[cid] = []
                    new_dumps[cid].append(uid)
                except:
                    continue
        _dump_chans = new_dumps
        _cache_ts = time.time()
        log.info(f"Refreshed cache: {len(_sub_chans)} subs, {len(_dump_chans)} dump channels")
    except Exception as e:
        log.error(f"Cache refresh failed: {e}")
def extract_chapter(msg: Message):
    txt = ""
    if msg.document:
        txt = msg.document.file_name or ""
    if msg.caption:
        txt += " " + msg.caption
    if msg.text:
        txt += " " + msg.text
    if not txt.strip():
        return None, None
    patterns = [
        r'[Cc]hapter\s*[:\-]?\s*(\d+(?:\.\d+)?)',
        r'[Cc]h\.?\s*(\d+(?:\.\d+)?)',
        r'\[(\d+(?:\.\d+)?)\]',
        r'[_\-\s](\d{2,4}(?:\.\d+)?)[_\-\s\.]',
    ]
    ch_num = None
    for p in patterns:
        m = re.search(p, txt)
        if m:
            ch_num = m.group(1)
            break
    if not ch_num:
        return None, None
    title = None
    pdf_pat = r'\[MC\]\s*\[\d+\]\s*(.+?)(?:\s*@|\.pdf|$)'
    m = re.search(pdf_pat, txt, re.IGNORECASE)
    if m:
        title = m.group(1).strip()
    if not title and msg.caption:
        bq = re.search(r'<blockquote[^>]*><b>([^<]+)</b></blockquote>', msg.caption)
        if bq:
            title = bq.group(1).strip()
    if not title:
        lines = txt.strip().split('\n')
        if lines:
            fl = lines[0].strip()
            fl = re.sub(r'^\[MC\]\s*', '', fl)
            fl = re.sub(r'\[\d+\]\s*', '', fl)
            fl = re.sub(r'@\S+', '', fl)
            fl = re.sub(r'\.pdf$', '', fl, flags=re.IGNORECASE)
            if fl and len(fl) > 3:
                title = fl.strip()
    return title, ch_num
async def find_sub(cid, uid, title=None):
    try:
        subs = await db.get_subs()
        chan_subs = [s for s in subs if s.get('cid') == cid and s.get('uid') == uid]
        if not chan_subs:
            return None
        if len(chan_subs) == 1:
            return chan_subs[0]
        if title and len(chan_subs) > 1:
            tl = title.lower()
            for s in chan_subs:
                st = s.get('title', '').lower()
                if st in tl or tl in st:
                    return s
        return chan_subs[0]
    except Exception as e:
        log.error(f"Find sub error: {e}")
        return None
async def send_promo(sub, ch_num, msg: Message):
    global _bot
    try:
        if not _bot:
            return
        uid = sub.get('uid')
        cid = sub.get('cid')
        title = sub.get('title', 'Unknown')
        chan_listen = await db.get_cfg(uid, "chan_listen", False)
        if not chan_listen:
            return
        update_cid_raw = await db.get_cfg(uid, "update_cid")
        u_cid = None
        if update_cid_raw:
            try:
                u_cid = int(update_cid_raw)
            except:
                pass
        if not u_cid:
            return
        try:
            if '.' in str(ch_num):
                parts = str(ch_num).split('.')
                fmt_ch = f"{int(parts[0]):03d}.{parts[1]}"
            else:
                fmt_ch = f"{int(ch_num):03d}"
        except:
            fmt_ch = str(ch_num).zfill(3)
        try:
            ch_id = str(cid).replace("-100", "")
            ch_link = f"https://t.me/c/{ch_id}/{msg.id}"
            chan_link = f"https://t.me/c/{ch_id}"
        except:
            ch_link = "https://t.me/"
            chan_link = "https://t.me/"
        update_msg_tmpl = await db.get_cfg(int(uid), "update_msg")
        update_btn = await db.get_cfg(int(uid), "update_btn", "Read Now")
        update_sticker = await db.get_cfg(int(uid), "update_sticker")
        caption_tmpl = await db.get_cfg(int(uid), "caption")
        promo_txt = ""
        if update_msg_tmpl:
            try:
                promo_txt = update_msg_tmpl.format(
                    manga_title=title,
                    title=title,
                    chapter_num=fmt_ch,
                    chapter_link=ch_link,
                    channel_link=chan_link
                )
            except:
                pass
        if not promo_txt and caption_tmpl:
            try:
                promo_txt = caption_tmpl.format(
                    title=title,
                    chapter=f"Ch. {fmt_ch}",
                    link=ch_link
                )
            except:
                pass
        if not promo_txt:
            promo_txt = f
        kb = KM([[KB(f"⊕ {update_btn}", url=ch_link)]])
        poster = sub.get('poster')
        sent_ok = False
        if poster:
            try:
                await _bot.send_photo(
                    u_cid,
                    photo=poster,
                    caption=promo_txt,
                    parse_mode=ParseMode.HTML,
                    reply_markup=kb
                )
                sent_ok = True
            except Exception as e:
                log.warning(f"Listener poster send fail: {e}")
        if not sent_ok:
            try:
                await _bot.send_message(
                    u_cid,
                    promo_txt,
                    parse_mode=ParseMode.HTML,
                    reply_markup=kb,
                    disable_web_page_preview=True
                )
            except Exception as e:
                log.warning(f"Listener msg send fail: {e}")
        if update_sticker:
            try:
                await _bot.send_sticker(u_cid, update_sticker)
            except:
                pass
        log.info(f"⊕ Update sent: {title} Ch.{ch_num} → {u_cid}")
    except Exception as e:
        log.error(f"Update send failed: {e}")
async def handle_chan_msg(c: Client, msg: Message):
    global _cache_ts, _bot
    try:
        if not msg.chat:
            return
        cid = msg.chat.id
        if cid is None or cid >= 0:
            return
        if time.time() - _cache_ts > _CACHE_TTL:
            await refresh_cache()
        if cid in _dump_chans:
            uids = _dump_chans[cid]
            for uid in uids:
                try:
                    curr_promos = await db.get_cfg(uid, "promo_msgs", [])
                    if len(curr_promos) < 3:
                        entry = {"chat_id": cid, "msg_id": msg.id}
                        exists = any(e['chat_id'] == cid and e['msg_id'] == msg.id for e in curr_promos)
                        if not exists:
                            curr_promos.append(entry)
                            await db.set_cfg(uid, "promo_msgs", curr_promos)
                            log.info(f"[PROMO] Counted msg {msg.id} for user {uid} (Total: {len(curr_promos)})")
                except Exception as ex:
                    log.error(f"[PROMO] Failed to add promo: {ex}")
        if cid not in _sub_chans:
            return
        if not msg.document:
            return
        if msg.from_user and msg.from_user.is_bot:
            return
        if msg.document.mime_type != "application/pdf":
            return
        log.info(f"⊕ PDF detected in {cid}")
        title, ch_num = extract_chapter(msg)
        if not ch_num:
            log.debug(f"No chapter number found in {cid}")
            return
        log.info(f"Extracted: {title} Ch.{ch_num}")
        uids = _sub_chans.get(cid, [])
        for uid in uids:
            chan_listen = await db.get_cfg(uid, "chan_listen", False)
            if not chan_listen:
                continue
            sub = await find_sub(cid, uid, title)
            if not sub:
                log.debug(f"No sub for uid={uid} cid={cid}")
                continue
            try:
                curr = float(sub.get('last', 0))
                new = float(ch_num)
                if new <= curr:
                    log.debug(f"Ch.{ch_num} not newer than {curr} for uid={uid}")
                    continue
            except:
                pass
            sid = sub.get('sid')
            ch_link = f"https://t.me/c/{str(cid).replace('-100', '')}/{msg.id}"
            await db.up_sub(uid, sid, ch_num, ch_link)
            log.info(f"✓ DB updated: {sub.get('title')} → Ch.{ch_num} (uid={uid})")
            await send_promo(sub, ch_num, msg)
        if Config.LOG_GROUP and _bot and uids:
            try:
                await _bot.send_message(
                    Config.LOG_GROUP,
                    f"<b>⊕ Manual Upload</b>\n\n"
                    f"<b>Channel:</b> {msg.chat.title or cid}\n"
                    f"<b>Manga:</b> {title or 'Unknown'}\n"
                    f"<b>Chapter:</b> {ch_num}\n"
                    f"<b>Users:</b> {len(uids)}",
                    parse_mode=ParseMode.HTML
                )
            except:
                pass
    except Exception as e:
        log.error(f"Channel msg error: {e}")
chan_listener = MessageHandler(
    handle_chan_msg,
    filters.channel
)
async def start_listener():
    await refresh_cache()
    log.info("Channel listener started")
