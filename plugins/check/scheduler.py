
import logging
import shutil
import asyncio
import time
import gc
from pathlib import Path
from database.db import db
from services.mgr import mgr
from services.dl import DL
from services.util import sanitize, extract_chap_no, clean_chap
from plugins.settings.shared import get_img_data, get_wmark_data, base64_to_file
from config import Config
from pyrogram.types import InlineKeyboardMarkup as KM, InlineKeyboardButton as KB
from .shared import (
    get_dl_dir, get_temp_dir, cleanup_promos, send_promos,
    DEF_CAP, parse_chap_num, cleanup_last_check, get_last_check, set_last_check,
    is_download_cancelled, clear_cancel_flag, is_sub_still_valid
)
log = logging.getLogger(__name__)
async def check_job(app):
    cleanup_last_check()
    current_time = time.time()
    subs = await db.get_subs()
    user_subs = {}
    for sub in subs:
        uid = sub.get('uid')
        if uid:
            user_subs.setdefault(uid, []).append(sub)
    del subs
    for uid, user_sub_list in user_subs.items():
        try:
            if not await db.get_cfg(uid, "mon", True):
                continue
            interval = await db.get_cfg(uid, "interval", 30) or 30
            interval_seconds = interval * 60
            last_time = get_last_check(uid)
            if current_time - last_time < interval_seconds:
                continue
            set_last_check(uid, current_time)
            for sub in user_sub_list:
                try:
                    await process_sub_check(app, uid, sub)
                except Exception as e:
                    log.error(f"[CHECK] Sub {sub.get('sid')} error: {e}")
            gc.collect()
        except Exception as e:
            log.error(f"[CHECK] User {uid} error: {e}")
    gc.collect()
async def process_sub_check(app, uid, sub):
    sid = sub.get('sid')
    title = sub.get('title', 'Unknown')
    cid = sub.get('cid')
    fresh_sub = await db.get_sub(uid, sid)
    if not fresh_sub:
        log.warning(f"[CHECK] Subscription {sid} deleted, skipping")
        return
    sub = fresh_sub
    sources = sub.get('sources', [])
    if not sources and sub.get('mid') and sub.get('src'):
        sources = [{"mid": sub.get('mid'), "src": sub.get('src')}]
    if not sources:
        return
    current_last = sub.get('last')
    if isinstance(current_last, (int, float)):
        global_last_num = float(current_last)
    else:
        global_last_num = parse_chap_num(current_last)
    combined_new = {}
    log.info(f"[CHECK] {title} - Last tracked: {global_last_num}")
    for source in sources:
        mid = source.get('mid')
        src_name = source.get('src')
        if not mid or not src_name:
            continue
        s = mgr.get(src_name)
        if not s:
            continue
        source_last = source.get('last')
        if isinstance(source_last, (int, float)):
            source_last_num = float(source_last)
        elif source_last:
            source_last_num = parse_chap_num(source_last)
        else:
            source_last_num = global_last_num
        d = {'url': mid, 'id': mid.split('/')[-1], 'title': title}
        try:
            chaps = await s.get_chapters(d)
            clist = s.iter_chapters(chaps, page=1) if chaps else []
            for ch in clist:
                ch_title = ch.get('title', '')
                ch_num = parse_chap_num(ch_title)
                if ch_num <= 0 or ch_num > 100000:
                    continue
                threshold = max(global_last_num, source_last_num)
                if ch_num <= threshold:
                    continue
                if ch_num not in combined_new:
                    ch['src_obj'] = s
                    ch['src_name'] = src_name
                    ch['_ch_num'] = ch_num
                    combined_new[ch_num] = ch
                    log.debug(f"[CHECK] New: {ch_title} ({ch_num}) from {src_name}")
        except Exception as e:
            log.error(f"[CHECK] Source {src_name} fail for {title}: {e}")
    if not combined_new:
        return
    new_chapters = sorted(combined_new.values(), key=lambda c: c.get('_ch_num', 0))
    if new_chapters:
        first_ch = new_chapters[0].get('_ch_num', 0)
        last_ch = new_chapters[-1].get('_ch_num', 0)
        log.info(f"[UPD] User:{uid} {title} -> {len(new_chapters)} new (Ch {first_ch} to {last_ch})")
    await cleanup_promos(app, uid, sub)
    first_post_link = None
    sent_chapters = []
    first_data = await get_img_data(uid, "first")
    last_data = await get_img_data(uid, "last")
    thumb_data = await get_img_data(uid, "thumb")
    wm_path = None
    if await db.get_cfg(uid, "wmark_on", False):
        wmark_data = await get_wmark_data(uid)
        if wmark_data[0]:
            temp_dir = get_temp_dir(uid)
            wm_path = str(temp_dir / "wmark.png")
            if wmark_data[0] == 'b64':
                await base64_to_file(wmark_data[1], wm_path)
            elif wmark_data[0] == 'url':
                from services.catbox import Catbox
                await Catbox.download(wmark_data[1], wm_path)
    for chapter in new_chapters:
        if is_download_cancelled(uid, sid):
            log.info(f"[CHECK] Download cancelled for {sid}, stopping")
            clear_cancel_flag(uid, sid)
            break
        if not await is_sub_still_valid(uid, sid):
            log.warning(f"[CHECK] Subscription {sid} was deleted, stopping upload")
            break
        chap_title = chapter.get('title', 'Unknown')
        chap_url = chapter.get('url', '')
        s = chapter.get('src_obj')
        if not s:
            continue
        imgs = await s.get_pictures(chap_url)
        if not imgs:
            log.warning(f"[CHECK] No images for {title} - {chap_title}")
            continue
        dl_dir = get_dl_dir(uid)
        folder_name = sanitize(f"{title}_{chap_title}")
        p = dl_dir / folder_name
        async with DL() as dl:
            qual = await db.get_cfg(uid, "quality", 80) or 80
            ft = await db.get_cfg(uid, "ftype", "pdf") or "pdf"
            # Image-links mode: skip download, post URL list
            if str(ft).lower() in ("links", "link", "urls", "images"):
                try:
                    cl_chap = clean_chap(chap_title)
                    link_lines = [f"{i+1}. {u}" for i, u in enumerate(imgs[:80])]
                    body = "\n".join(link_lines)
                    if len(imgs) > 80:
                        body += f"\n… +{len(imgs)-80} more"
                    cap = (
                        f"<b>{title}</b>\n"
                        f"<blockquote>Chapter: <code>{cl_chap}</code>\n"
                        f"Pages: <code>{len(imgs)}</code></blockquote>\n"
                        f"<pre>{body[:3500]}</pre>"
                    )
                    btn_cfg = await db.get_cfg(uid, "btn")
                    markup = None
                    if btn_cfg and isinstance(btn_cfg, dict) and "txt" in btn_cfg:
                        markup = KM([[KB(btn_cfg["txt"], url=btn_cfg["url"])]])
                    await app.send_message(cid, cap, reply_markup=markup, disable_web_page_preview=True)
                    log.info(f"[CHECK] Posted image links for {title} ch {cl_chap}")
                    continue
                except Exception as e:
                    log.error(f"[CHECK] links mode failed: {e}")
                    continue

            # Album mode: small chapters as Telegram media group
            try:
                album_max = int(getattr(Config, "ALBUM_MAX_PAGES", 0) or 0)
                user_album = await db.get_cfg(uid, "album", None)
                if user_album is not None:
                    album_max = int(user_album) if user_album else 0
                if album_max > 0 and len(imgs) <= album_max and len(imgs) > 0:
                    from pyrogram.types import InputMediaPhoto
                    cl_chap = clean_chap(chap_title)
                    media = []
                    # download first N pages quickly into temp for album
                    album_dir = get_temp_dir(uid) / f"album_{sid}"
                    album_dir.mkdir(parents=True, exist_ok=True)
                    qual = await db.get_cfg(uid, "quality", 80) or 80
                    if await dl.get_imgs(imgs[:album_max], album_dir, quality=qual):
                        files = sorted(album_dir.glob("*.jpg")) + sorted(album_dir.glob("*.png")) + sorted(album_dir.glob("*.webp"))
                        for i, fpath in enumerate(files[:10]):  # TG limit 10
                            cap = (
                                f"<b>{title}</b>\n<blockquote>Ch <code>{cl_chap}</code> · {i+1}/{len(files)}</blockquote>"
                                if i == 0 else ""
                            )
                            media.append(InputMediaPhoto(str(fpath), caption=cap if cap else None))
                        if media:
                            await app.send_media_group(cid, media)
                            log.info(f"[CHECK] Album posted {title} ch {cl_chap} ({len(media)} pages)")
                            # webhook
                            try:
                                from services.webhook import post_webhook
                                wh = await db.get_cfg(uid, "webhook") or getattr(Config, "WEBHOOK_URL", "")
                                if wh:
                                    await post_webhook(wh, title=title, chapter=cl_chap, source=str(sub.get("src") or ""), link=chap_url)
                            except Exception as we:
                                log.warning(f"[WEBHOOK] {we}")
                            # rate poll
                            if getattr(Config, "ENABLE_RATE_POLL", False) or await db.get_cfg(uid, "rate_poll", False):
                                try:
                                    poll_q = await db.get_cfg(uid, "poll_text") or "Rate: {title} Ch {chapter}"
                                    try:
                                        poll_q = poll_q.format(title=title, chapter=cl_chap)
                                    except Exception:
                                        poll_q = f"Rate: {title} Ch {cl_chap}"
                                    await app.send_poll(
                                        cid,
                                        question=poll_q,
                                        options=["⭐", "⭐⭐", "⭐⭐⭐", "⭐⭐⭐⭐", "⭐⭐⭐⭐⭐"],
                                        is_anonymous=True,
                                    )
                                except Exception as pe:
                                    log.warning(f"[POLL] {pe}")
                            continue
            except Exception as e:
                log.warning(f"[ALBUM] fallback to file: {e}")

            if await dl.get_imgs(imgs, p, wmark_path=wm_path, quality=qual):
                fname_fmt = await db.get_cfg(uid, "fname", None)
                cl_chap = clean_chap(chap_title)
                chap_no = extract_chap_no(chap_title)
                fp = await dl.make(p, title, chap_no, ft, qual, fname_fmt, first_data, last_data)
                if fp:
                    btn_cfg = await db.get_cfg(uid, "btn")
                    markup = None
                    if btn_cfg and isinstance(btn_cfg, dict) and 'txt' in btn_cfg:
                        markup = KM([[KB(btn_cfg['txt'], url=btn_cfg['url'])]])
                    thumb_path = None
                    sub_thumb = sub.get('thumb_b64')
                    if sub_thumb:
                        temp_thumb = get_temp_dir(uid) / f"thumb_{sid}.jpg"
                        await base64_to_file(sub_thumb, str(temp_thumb))
                        thumb_path = str(temp_thumb)
                    else:
                        thumb_src = await db.get_cfg(uid, "thumb_src", "first")
                        if thumb_src == "custom" and thumb_data[0]:
                            temp_thumb = get_temp_dir(uid) / "thumb.jpg"
                            if thumb_data[0] == 'b64':
                                await base64_to_file(thumb_data[1], str(temp_thumb))
                                thumb_path = str(temp_thumb)
                            elif thumb_data[0] == 'url':
                                from services.catbox import Catbox
                                if await Catbox.download(thumb_data[1], str(temp_thumb)):
                                    thumb_path = str(temp_thumb)
                    if not thumb_path:
                        all_imgs = sorted(p.glob("*.jpg"))
                        if all_imgs:
                            thumb_path = str(all_imgs[-1] if thumb_src == "last" else all_imgs[0])
                    sent = await app.send_document(
                        cid, fp, caption="",
                        thumb=thumb_path,
                        reply_markup=markup
                    )
                    tmpl = await db.get_cfg(uid, "caption") or DEF_CAP
                    link = sent.link if sent and sent.link else chap_url
                    if not first_post_link:
                        first_post_link = link
                    chap_no = extract_chap_no(chap_title)
                    msg = tmpl.format(title=title, chapter=chap_no, link=link, num=chap_no)
                    try:
                        await sent.edit_caption(msg, reply_markup=markup)
                    except:
                        pass

                    # Webhook export
                    try:
                        from services.webhook import post_webhook
                        wh = await db.get_cfg(uid, "webhook") or getattr(Config, "WEBHOOK_URL", "")
                        if wh:
                            await post_webhook(
                                wh,
                                title=title,
                                chapter=str(chap_no),
                                source=str(sub.get("src") or ""),
                                link=link,
                            )
                    except Exception as we:
                        log.warning(f"[WEBHOOK] {we}")
                    # Optional rate poll
                    try:
                        if getattr(Config, "ENABLE_RATE_POLL", False) or await db.get_cfg(uid, "rate_poll", False):
                            poll_q = await db.get_cfg(uid, "poll_text") or "Rate: {title} Ch {chapter}"
                            try:
                                poll_q = poll_q.format(title=title, chapter=chap_no)
                            except Exception:
                                poll_q = f"Rate: {title} Ch {chap_no}"
                            await app.send_poll(
                                cid,
                                question=poll_q,
                                options=["⭐", "⭐⭐", "⭐⭐⭐", "⭐⭐⭐⭐", "⭐⭐⭐⭐⭐"],
                                is_anonymous=True,
                            )
                    except Exception as pe:
                        log.warning(f"[POLL] {pe}")

                    dump_cid = await db.get_cfg(uid, "dump_cid") or Config.LOG_GROUP
                    if dump_cid:
                        try:
                            dump_cid = int(dump_cid)
                        except (ValueError, TypeError):
                            dump_cid = None
                            log.warning(f"[DUMP] Invalid dump_cid for user {uid}, must be numeric")
                    if dump_cid and dump_cid != cid:
                        try:
                            await sent.copy(dump_cid)
                        except Exception as e:
                            if "BOT_METHOD_INVALID" in str(e) or "Forbidden" in str(e):
                                log.debug(f"[DUMP] Copy skipped (no access): {dump_cid}")
                            else:
                                log.warning(f"[DUMP] Copy fail: {e}")
                    fp.unlink()
                    chap_num = chapter.get('_ch_num', 0)
                    await db.up_sub(uid, sid, chap_num, chap_title, chap_url)
                    log.info(f"[CHECK] ✓ Updated DB: {sid} last={chap_num} ('{chap_title}')")
                    src_name = chapter.get('src_name')
                    if src_name:
                        await db.up_source(uid, sid, src_name, chap_num, chap_title, chap_url)
                    sent_chapters.append(extract_chap_no(chap_title))
                else:
                    await app.send_message(cid, f"File Make Fail: {title} - {chap_title}")
            else:
                await app.send_message(cid, f"DL Fail: {title} - {chap_title}")
        shutil.rmtree(p, ignore_errors=True)
        gc.collect()
        await asyncio.sleep(2)
    if wm_path and Path(wm_path).exists():
        Path(wm_path).unlink(missing_ok=True)
    if sent_chapters:
        await send_promos(app, uid, sub)
    update_cid = await db.get_cfg(uid, "update_cid") if sent_chapters else None
    if update_cid and sent_chapters:
        update_tmpl = await db.get_cfg(uid, "update_msg")
        if not update_tmpl:
            update_tmpl = "<blockquote><b>{manga_title}</b></blockquote>\n➥ <b><a href=\"{chapter_link}\">Cʜᴀᴘᴛᴇʀ {chapter_num}</a> Uᴘʟᴏᴀᴅᴇᴅ</b>\n➥ <b><a href=\"{channel_link}\">Rᴇᴀᴅ Nᴏᴡ</a></b>"
        if len(sent_chapters) > 1:
            try:
                start_n = extract_chap_no(sent_chapters[0])
                end_n = extract_chap_no(sent_chapters[-1])
                chap_range = f"{start_n} ~ {end_n}"
            except:
                chap_range = f"{sent_chapters[0]} ~ {sent_chapters[-1]}"
        else:
            chap_range = sent_chapters[0]
        channel_link = sub.get('inv', f"https://t.me/c/{str(cid).replace('-100', '')}")
        update_msg = update_tmpl.format(
            manga_title=title,
            chapter_num=chap_range,
            chapter_link=first_post_link,
            channel_link=channel_link,
            title=title, chapters=chap_range, link=first_post_link, channel=channel_link,
            num=chap_range
        )
        try:
            up_btn_on = await db.get_cfg(uid, "update_btn_on", True)
            up_markup = None
            if up_btn_on:
                up_btn_txt = await db.get_cfg(int(uid), "update_btn", "Click Here to Read")
                up_markup = KM([[KB(str(up_btn_txt), url=channel_link)]])
            banner = sub.get('banner')
            if banner:
                await app.send_photo(update_cid, banner, caption=update_msg, reply_markup=up_markup)
            else:
                await app.send_message(update_cid, update_msg, disable_web_page_preview=True, reply_markup=up_markup)
            stick = await db.get_cfg(uid, "update_sticker")
            if stick:
                await app.send_sticker(update_cid, stick)
        except Exception as e:
            log.error(f"Failed to send update msg to {update_cid}: {e}")
