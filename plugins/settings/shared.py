
import logging
import time
from pathlib import Path
from database.db import db
log = logging.getLogger(__name__)
_user_states_raw = {}
_temp_data_raw = {}
STATE_TTL = 1800
class StateDictWrapper:
    def __init__(self, data_dict, ttl=STATE_TTL):
        self._data = data_dict
        self._ttl = ttl
    def _cleanup(self):
        now = time.time()
        expired = [k for k, v in self._data.items()
                   if isinstance(v, dict) and now - v.get('_ts', 0) > self._ttl]
        for k in expired:
            del self._data[k]
    def get(self, key, default=None):
        self._cleanup()
        entry = self._data.get(key)
        if entry is None:
            return default
        if isinstance(entry, dict) and '_val' in entry:
            return entry['_val']
        return entry
    def __getitem__(self, key):
        self._cleanup()
        if key not in self._data:
            raise KeyError(key)
        entry = self._data[key]
        if isinstance(entry, dict) and '_val' in entry:
            return entry['_val']
        return entry
    def __setitem__(self, key, value):
        self._data[key] = {'_val': value, '_ts': time.time()}
    def __contains__(self, key):
        self._cleanup()
        return key in self._data
    def pop(self, key, *args):
        self._cleanup()
        entry = self._data.pop(key, *args)
        if isinstance(entry, dict) and '_val' in entry:
            return entry['_val']
        return entry
    def __iter__(self):
        self._cleanup()
        return iter(self._data)
    def items(self):
        self._cleanup()
        for k, v in self._data.items():
            if isinstance(v, dict) and '_val' in v:
                yield k, v['_val']
            else:
                yield k, v
user_states = StateDictWrapper(_user_states_raw)
temp_data = StateDictWrapper(_temp_data_raw)
SETTINGS_BANNER = "https://files.catbox.moe/vhm5zo.jpg"
IMG_KEYS = {
    "first": "promo_first_b64",
    "last": "promo_last_b64",
    "thumb": "promo_thumb_b64",
}
WMARK_KEY = "wmark_b64"
IMG_URL_KEYS = {
    "first": "promo_first_url",
    "last": "promo_last_url",
    "thumb": "promo_thumb_url",
}
WMARK_URL_KEY = "wmark_url"
import base64
import aiofiles
import os
async def img_to_base64(file_path):
    async with aiofiles.open(file_path, 'rb') as f:
        data = await f.read()
    return base64.b64encode(data).decode('utf-8')
async def base64_to_file(b64_str, dest_path):
    data = base64.b64decode(b64_str)
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    async with aiofiles.open(dest_path, 'wb') as f:
        await f.write(data)
    return dest_path
async def has_img(uid, img_type):
    key = IMG_KEYS.get(img_type)
    if not key: return False
    val = await db.get_cfg(uid, key)
    if val: return True
    url_key = IMG_URL_KEYS.get(img_type)
    return bool(await db.get_cfg(uid, url_key)) if url_key else False
async def get_img_data(uid, img_type):
    key = IMG_KEYS.get(img_type)
    if key:
        b64 = await db.get_cfg(uid, key)
        if b64: return ('b64', b64)
    url_key = IMG_URL_KEYS.get(img_type)
    if url_key:
        url = await db.get_cfg(uid, url_key)
        if url: return ('url', url)
    return (None, None)
async def set_img_b64(uid, img_type, b64_data):
    key = IMG_KEYS.get(img_type)
    if not key: return
    await db.set_cfg(uid, key, b64_data)
    url_key = IMG_URL_KEYS.get(img_type)
    if url_key:
        await db.set_cfg(uid, url_key, None)
async def clear_img(uid, img_type):
    key = IMG_KEYS.get(img_type)
    if key:
        await db.set_cfg(uid, key, None)
    url_key = IMG_URL_KEYS.get(img_type)
    if url_key:
        await db.set_cfg(uid, url_key, None)
async def get_img_url(uid, img_type):
    url_key = IMG_URL_KEYS.get(img_type)
    if url_key:
        return await db.get_cfg(uid, url_key)
    return None
async def set_img_url(uid, img_type, url):
    url_key = IMG_URL_KEYS.get(img_type)
    if url_key:
        await db.set_cfg(uid, url_key, url)
async def clear_img_url(uid, img_type):
    await clear_img(uid, img_type)
async def has_wmark(uid):
    val = await db.get_cfg(uid, WMARK_KEY)
    if val: return True
    return bool(await db.get_cfg(uid, WMARK_URL_KEY))
async def get_wmark_data(uid):
    b64 = await db.get_cfg(uid, WMARK_KEY)
    if b64: return ('b64', b64)
    url = await db.get_cfg(uid, WMARK_URL_KEY)
    if url: return ('url', url)
    return (None, None)
async def set_wmark_b64(uid, b64_data):
    await db.set_cfg(uid, WMARK_KEY, b64_data)
    await db.set_cfg(uid, WMARK_URL_KEY, None)
async def clear_wmark(uid):
    await db.set_cfg(uid, WMARK_KEY, None)
    await db.set_cfg(uid, WMARK_URL_KEY, None)
async def get_wmark_url(uid):
    return await db.get_cfg(uid, WMARK_URL_KEY)
async def set_wmark_url(uid, url):
    await db.set_cfg(uid, WMARK_URL_KEY, url)
async def clear_wmark_url(uid):
    await clear_wmark(uid)
def get_temp_dir(uid):
    p = Path(f"temp/{uid}")
    p.mkdir(parents=True, exist_ok=True)
    return p
SYM = {
    "on": "●",
    "off": "○",
    "set": "◆",
    "unset": "◇",
    "ok": "✓",
    "x": "✗",
    "add": "⊕",
    "rem": "⊖",
    "warn": "⚠",
    "nav": "▸",
    "back": "◂",
    "toggle": "↻",
    "load": "⋯",
    "edit": "✎",
    "info": "ℹ",
    "search": "⌕",
    "home": "⌂",
}
def _s(val, on="●", off="○"):
    return on if val else off
def _set(val):
    return "◆" if val else "◇"
async def edit_msg(c, msg, text, reply_markup=None):
    m = msg.message if hasattr(msg, 'message') else msg
    chat_id = m.chat.id
    try:
        if m.photo or (hasattr(m, 'caption') and m.caption):
            await m.edit_caption(text, reply_markup=reply_markup)
        else:
            await m.edit_text(text, reply_markup=reply_markup)
    except Exception as e:
        log.warning(f"Edit failed: {e}")
        try:
            await m.delete()
        except: pass
        try:
            await c.send_photo(chat_id, SETTINGS_BANNER, caption=text, reply_markup=reply_markup)
        except Exception as e2:
            log.error(f"Send photo failed: {e2}")
            try:
                await c.send_message(chat_id, text, reply_markup=reply_markup)
            except: pass
