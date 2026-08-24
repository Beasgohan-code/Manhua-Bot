
import logging
import shutil
import asyncio
from pathlib import Path
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup as KM, InlineKeyboardButton as KB
from database.db import db
from services.mgr import mgr
from services.dl import DL
from services.util import sanitize, extract_chap_no, clean_chap
from plugins.settings.shared import get_img_data, get_wmark_data, base64_to_file
from config import Config
from .shared import (
    get_dl_dir, get_temp_dir, cleanup_promos, send_promos,
    DEF_CAP, parse_chap_num, cancel_download, is_download_cancelled
)
log = logging.getLogger(__name__)
@Client.on_message(filters.command("stop") & filters.private)
async def stop_cmd(c, m):
    uid = m.from_user.id
    args = m.command[1:]
    if not args:
        cancel_download(uid)
        return await m.reply(
            "<b>✓ Cancellation Signal Sent</b>\n\n"
            "<blockquote>All ongoing downloads will stop after the current chapter completes.</blockquote>\n"
            "<i>Note: If a chapter is mid-download, it will finish that chapter first.</i>"
        )
    sid = args[0].upper()
    sub = await db.get_sub(uid, sid)
    if not sub:
        return await m.reply(f"[X] Subscription `{sid}` not found.")
    cancel_download(uid, sid)
    await m.reply(
        f"<b>✓ Cancellation Signal Sent</b>\n\n"
        f"<blockquote>Downloads for <code>{sid}</code> ({sub.get('title', 'Unknown')}) will stop.</blockquote>\n"
        f"<i>Current chapter will complete before stopping.</i>"
    )
@Client.on_message(filters.command("info") & filters.private)
async def info_cmd(c, m):
    uid = m.from_user.id
    args = m.command[1:]
    if not args:
        return await m.reply("`/info <id>` - View subscription details\nExample: `/info M001`")
    sid = args[0].upper()
    sub = await db.get_sub(uid, sid)
    if not sub:
        return await m.reply(f"[X] Subscription `{sid}` not found.")
    txt = f"<b>Subscription Info:</b> <code>{sid}</code>\n\n"
    for k, v in sub.items():
        if k in ['_id', 'uid']:
            continue
        val = str(v)[:50] + "..." if len(str(v)) > 50 else str(v)
        txt += f"<b>{k}:</b> <code>{val}</code>\n"
    btns = KM([
        [KB("⊕ Set Thumb", f"st_th_{sid}")],
        [KB("◂ Back", "open_list_cmd")]
    ])
    await m.reply(txt, reply_markup=btns)
@Client.on_message(filters.command("check") & filters.private)
async def check_cmd(c, m):
    uid = m.from_user.id
    args = m.command[1:]
    if not args:
        return await m.reply("`/check <id>` - Check manga by ID\nExample: `/check M001`")
    sid = str(args[0]).upper()
    sub = await db.get_sub(uid, sid)
    if not sub:
        return await m.reply(f"[X] Subscription `{sid}` not found.")
    title = sub.get('title', 'Unknown')
    src = sub.get('src')
    mid = sub.get('mid')
    if not src or not mid:
        return await m.reply(f"[X] Subscription `{sid}` is corrupted (missing src/mid).")
    msg = await m.reply(f"<blockquote>[...] Checking <code>{sid}</code>: <b>{title}</b>...</blockquote>")
    try:
        s = mgr.get(src)
        if not s:
            return await msg.edit(f"[X] Source `{src}` not available.")
        d = {'url': mid, 'id': mid.split('/')[-1], 'title': title}
        chaps = await s.get_chapters(d)
        if not chaps:
            return await msg.edit(f"[X] Could not fetch chapters for **{title}**")
        clist = s.iter_chapters(chaps, page=1)
        if not clist:
            return await msg.edit(f"[X] No chapters found for **{title}**")
        current = sub.get('last', 'None')
        current_num = parse_chap_num(current) if current != 'None' else 0
        new_chaps = []
        for ch in clist:
            ch_title = ch.get('title', '')
            ch_num = parse_chap_num(ch_title)
            if ch_num <= 0 or ch_num > 100000:
                continue
            if ch_num > current_num:
                new_chaps.append((ch_num, ch_title))
        new_chaps.sort(key=lambda x: x[0])
        if not new_chaps:
            latest = clist[0].get('title', 'Unknown')
            latest_num = parse_chap_num(latest)
            await msg.edit(
                f"<b>┌─ CHECK RESULT ─┐</b>\n\n"
                f"│ <b>Manga:</b> {title}\n"
                f"│ <b>ID:</b> <code>{sid}</code>\n│\n"
                f"│ <b>Tracked:</b> Ch {current_num}\n"
                f"│ <b>Latest:</b> Ch {latest_num}\n"
                f"└───────────────────\n\n<i>No new chapters.</i>"
            )
        else:
            chap_list = "\n".join([f"Ch {n}: {t}" for n, t in new_chaps[:10]])
            if len(new_chaps) > 10:
                chap_list += f"\n... +{len(new_chaps) - 10} more"
            await msg.edit(
                f"<b>┌─ NEW CHAPTERS!! ─┐</b>\n\n"
                f"│ <b>Manga:</b> {title}\n"
                f"│ <b>ID:</b> <code>{sid}</code>\n│\n"
                f"│ <b>Tracked:</b> Ch {current_num}\n"
                f"│ <b>Found:</b> {len(new_chaps)} new (Ch {new_chaps[0][0]} → {new_chaps[-1][0]})\n"
                f"└───────────────────\n\n"
                f"<blockquote expandable>{chap_list}</blockquote>",
                reply_markup=KM([[KB("[DL] Download Latest", f"dl_{sid}")]])
            )
    except Exception as e:
        log.error(f"Check cmd error for {sid}: {e}")
        await msg.edit(f"[X] Error checking: `{e}`")
@Client.on_callback_query(filters.regex(r"^dl_"))
async def dl_now(c, q):
    uid = q.from_user.id
    sid = q.data.replace("dl_", "")
    sub = await db.get_sub(uid, sid)
    if not sub:
        return await q.answer("Subscription not found", show_alert=True)
    title = sub.get('title', 'Unknown')
    cid = sub.get('cid')
    sources = sub.get('sources', [])
    if not sources and sub.get('mid') and sub.get('src'):
        sources = [{"mid": sub.get('mid'), "src": sub.get('src')}]
    if not sources or not cid:
        return await q.answer("Subscription corrupted", show_alert=True)
    await q.message.edit(f"<blockquote>[...] Checking {len(sources)} sources...</blockquote>")
    try:
        combined_new = {}
        current_last = sub.get('last')
        global_last_num = parse_chap_num(current_last)
        for source in sources:
            mid = source.get('mid')
            src_name = source.get('src')
            if not mid or not src_name:
                continue
            s = mgr.get(src_name)
            if not s:
                continue
            source_last = source.get('last') or current_last
            source_last_num = parse_chap_num(source_last) if source_last else global_last_num
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
                        ch['_ch_num'] = ch_num
                        combined_new[ch_num] = ch
            except Exception as e:
                log.error(f"[DL] Source {src_name} fail: {e}")
        if not combined_new:
            return await q.message.edit(f"<b>{title}</b> is up to date!\n<i>Last: {current_last}</i>")
        new_chapters = sorted(combined_new.values(), key=lambda c: c.get('_ch_num', 0))
        first_ch, last_ch = new_chapters[0].get('_ch_num'), new_chapters[-1].get('_ch_num')
        await q.message.edit(f"<blockquote>[DL] Found {len(new_chapters)} new (Ch {first_ch} → {last_ch})...</blockquote>")
        await cleanup_promos(c, uid, sub)
        sent_chapters = []
        first_post_link = None
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
            chap_title = chapter.get('title', 'Unknown')
            chap_url = chapter.get('url', '')
            s = chapter.get('src_obj')
            if not s:
                continue
            imgs = await s.get_pictures(chap_url)
            if not imgs:
                continue
            dl_dir = get_dl_dir(uid)
            p = dl_dir / sanitize(f"{title}_{chap_title}")
            async with DL() as dl:
                qual = await db.get_cfg(uid, "quality", 80) or 80
                if await dl.get_imgs(imgs, p, wmark_path=wm_path, quality=qual):
                    ft = await db.get_cfg(uid, "ftype", "pdf") or "pdf"
                    fname_fmt = await db.get_cfg(uid, "fname", None)
                    chap_no = extract_chap_no(chap_title)
                    fp = await dl.make(p, title, chap_no, ft, qual, fname_fmt, first_data, last_data)
                    if fp:
                        btn_cfg = await db.get_cfg(uid, "btn")
                        markup = KM([[KB(btn_cfg['txt'], url=btn_cfg['url'])]]) if btn_cfg and isinstance(btn_cfg, dict) and 'txt' in btn_cfg else None
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
                        sent = await c.send_document(cid, fp, thumb=thumb_path, reply_markup=markup)
                        link = sent.link if sent and sent.link else chap_url
                        if not first_post_link:
                            first_post_link = link
                        tmpl = await db.get_cfg(uid, "caption") or DEF_CAP
                        # Use chapter number for all placeholders
                        chap_no = extract_chap_no(chap_title)
                        await sent.edit_caption(tmpl.format(title=title, chapter=chap_no, link=link, num=chap_no), reply_markup=markup)
                        dump_cid = await db.get_cfg(uid, "dump_cid") or Config.LOG_GROUP
                        if dump_cid:
                            try:
                                dump_cid = int(dump_cid)
                            except (ValueError, TypeError):
                                dump_cid = None
                        if dump_cid and dump_cid != cid:
                            try:
                                await sent.copy(dump_cid)
                            except Exception as e:
                                log.warning(f"[DUMP] Copy fail: {e}")
                        fp.unlink()
                        chap_num = chapter.get('_ch_num', 0)
                        await db.up_sub(uid, sid, chap_num, chap_title, chap_url)
                        sent_chapters.append(extract_chap_no(chap_title))
            shutil.rmtree(p, ignore_errors=True)
            await asyncio.sleep(1)
        if wm_path and Path(wm_path).exists():
            Path(wm_path).unlink(missing_ok=True)
        if sent_chapters:
            await send_promos(c, uid, sub)
            await q.message.edit(f"<b>[OK] Posted {len(sent_chapters)} chapters of {title}!</b>")
            update_cid = await db.get_cfg(uid, "update_cid")
            u_cid = None
            if update_cid:
                try:
                    u_cid = int(update_cid)
                except:
                    u_cid = None
            if u_cid:
                try:
                    if len(sent_chapters) > 1:
                        try:
                            start_n, end_n = extract_chap_no(sent_chapters[0]), extract_chap_no(sent_chapters[-1])
                            chap_range = f"{start_n} ~ {end_n}"
                        except:
                            chap_range = f"{sent_chapters[0]} ~ {sent_chapters[-1]}"
                    else:
                        chap_range = sent_chapters[0]
                    channel_link = sub.get('inv')
                    if not channel_link:
                        try:
                            channel_link = f"https://t.me/c/{str(cid).replace('-100', '')}"
                        except:
                            channel_link = "https://t.me/"
                    f_link = first_post_link if first_post_link else channel_link
                    def_tmpl = "<blockquote><b>{manga_title}</b></blockquote>\n➥ <b><a href=\"{chapter_link}\">Cʜᴀᴘᴛᴇʀ {chapter_num}</a> Uᴘʟᴏᴀᴅᴇᴅ</b>\n➥ <b><a href=\"{channel_link}\">Rᴇᴀᴅ Nᴏᴡ</a></b>"
                    update_tmpl = await db.get_cfg(uid, "update_msg") or def_tmpl
                    try:
                        update_msg = update_tmpl.format(manga_title=title, title=title, chapter_num=chap_range, chapter_link=f_link, channel_link=channel_link, num=chap_range)
                    except Exception as e:
                        log.warning(f"Update msg format error: {e}")
                        update_msg = def_tmpl.format(manga_title=title, chapter_num=chap_range, chapter_link=f_link, channel_link=channel_link)
                    up_btn_on = await db.get_cfg(uid, "update_btn_on", True)
                    up_markup = None
                    if up_btn_on:
                        up_btn_txt = await db.get_cfg(uid, "update_btn", "Click Here to Read")
                        up_markup = KM([[KB(str(up_btn_txt), url=channel_link)]])
                    banner = sub.get('banner')
                    sent_ok = False
                    if banner:
                        try:
                            await c.send_photo(u_cid, banner, caption=update_msg, reply_markup=up_markup)
                            sent_ok = True
                        except Exception as e:
                            log.warning(f"Update banner failed: {e}")
                    if not sent_ok:
                        await c.send_message(u_cid, update_msg, disable_web_page_preview=True, reply_markup=up_markup)
                    stick = await db.get_cfg(uid, "update_sticker")
                    if stick:
                        try:
                            await c.send_sticker(u_cid, stick)
                        except:
                            pass
                except Exception as e:
                    log.error(f"Update msg fail: {e}")
    except Exception as e:
        log.error(f"DL cmd error for {sid}: {e}")
        await q.message.edit(f"[X] Error: `{e}`")
