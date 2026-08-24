
import logging
import time
from pathlib import Path
from database.db import db
from services.util import extract_chap_no
log = logging.getLogger(__name__)
DEF_CAP = "<blockquote>{title}</blockquote>\n> {chapter}\n> <a href='{link}'>Read Now</a>"
_last_check = {}
_LAST_CHECK_CLEANUP_INTERVAL = 86400
_last_cleanup = 0
_cancelled_downloads = {}
def cancel_download(uid: int, sid: str = None):
    if sid:
        _cancelled_downloads[(uid, sid)] = True
        log.info(f"[CANCEL] Download cancelled for {uid}:{sid}")
    else:
        for key in list(_cancelled_downloads.keys()):
            if key[0] == uid:
                _cancelled_downloads[key] = True
        _cancelled_downloads[(uid, "*")] = True
        log.info(f"[CANCEL] All downloads cancelled for user {uid}")
def is_download_cancelled(uid: int, sid: str) -> bool:
    return _cancelled_downloads.get((uid, sid), False) or _cancelled_downloads.get((uid, "*"), False)
def clear_cancel_flag(uid: int, sid: str = None):
    if sid:
        _cancelled_downloads.pop((uid, sid), None)
    else:
        _cancelled_downloads.pop((uid, "*"), None)
async def is_sub_still_valid(uid: int, sid: str) -> bool:
    sub = await db.get_sub(uid, sid)
    return sub is not None
def get_dl_dir(uid):
    p = Path("downloads") / str(uid)
    p.mkdir(parents=True, exist_ok=True)
    return p
def get_temp_dir(uid):
    p = Path("temp") / str(uid)
    p.mkdir(parents=True, exist_ok=True)
    return p
def cleanup_last_check():
    global _last_cleanup
    now = time.time()
    if now - _last_cleanup < 3600:
        return
    _last_cleanup = now
    cutoff = now - _LAST_CHECK_CLEANUP_INTERVAL
    stale = [uid for uid, ts in _last_check.items() if ts < cutoff]
    for uid in stale:
        del _last_check[uid]
def get_last_check(uid):
    return _last_check.get(uid, 0)
def set_last_check(uid, ts):
    _last_check[uid] = ts
async def cleanup_promos(bot, uid, sub):
    cid = sub.get('cid')
    sid = sub.get('sid')
    if not cid or not sid:
        return
    old_ids = sub.get('last_promo_ids', [])
    if not old_ids:
        return
    del_count = await db.get_cfg(uid, "promo_del_count", 0)
    if not del_count or del_count <= 0:
        return
    to_del = [m for m in old_ids[-del_count:] if m]
    if not to_del:
        return
    deleted_ids = []
    skipped_ids = []
    try:
        messages = await bot.get_messages(cid, to_del)
        ids_to_delete = []
        for msg in messages:
            if not msg or msg.empty:
                continue
            if msg.document or msg.video or msg.audio:
                log.info(f"[PROMO] Skipping deletion of msg {msg.id} (file/media)")
                skipped_ids.append(msg.id)
                continue
            ids_to_delete.append(msg.id)
        if ids_to_delete:
            await bot.delete_messages(cid, ids_to_delete)
            deleted_ids = ids_to_delete
            log.info(f"[PROMO] Deleted {len(deleted_ids)} promos for {sid}")
        if skipped_ids:
            log.warning(f"[PROMO] Skipped {len(skipped_ids)} protected msgs for {sid}")
    except Exception as e:
        log.warning(f"[PROMO] Safe cleanup fail for {sid}: {e}")
        try:
            await bot.delete_messages(cid, to_del)
            deleted_ids = to_del
            log.warning(f"[PROMO] Fallback deletion used for {sid}")
        except Exception as e2:
            log.error(f"[PROMO] Fallback failed for {sid}: {e2}")
    all_processed = deleted_ids + skipped_ids
    remaining = [mid for mid in old_ids if mid not in all_processed]
    remaining.extend(skipped_ids)
    await db.up_sub_promos(uid, sid, remaining)
async def send_promos(bot, uid, sub):
    cid = sub.get('cid')
    sid = sub.get('sid')
    if not cid or not sid:
        return
    promo_list = await db.get_cfg(uid, "promo_msgs", [])
    if not promo_list:
        return
    new_ids = []
    for p in promo_list:
        try:
            sent = await bot.copy_message(cid, p['chat_id'], p['msg_id'])
            new_ids.append(sent.id)
        except Exception as e:
            log.error(f"Promo copy fail {p['chat_id']}:{p['msg_id']} -> {cid}: {e}")
    if new_ids:
        await db.up_sub_promos(uid, sid, new_ids)
        log.info(f"[PROMO] Saved {len(new_ids)} promo IDs for {sid}")
def parse_chap_num(chap_str):
    if not chap_str:
        return 0
    try:
        return float(extract_chap_no(chap_str).replace(',', ''))
    except (ValueError, TypeError):
        return 0
