
from pyrogram import Client, filters
from database.db import db
from config import Config
from plugins.settings.shared import (
    user_states, temp_data, get_temp_dir,
    img_to_base64, set_img_b64, set_wmark_b64
)
from plugins.settings.main import main_menu
from plugins.settings.style import style_menu
from plugins.settings.update import update_menu
from plugins.settings.ppromo import pp_m
from plugins.settings.imgs import imgs_menu
from plugins.settings.wmark import wm_menu
from plugins.fsub import force_sub
@Client.on_message(filters.private & filters.create(lambda _, __, m: m.from_user and m.from_user.id in user_states))
@force_sub
async def settings_listener(c, m):
    uid = m.from_user.id
    state = user_states.get(uid)
    if m.text == "/cancel":
        user_states.pop(uid, None)
        temp_data.pop(uid, None)
        await m.reply("Cancelled.")
        return await main_menu(c, m)
    if m.text and m.text.startswith("/"):
        return
    if state == "await_cap":
        await db.set_cfg(uid, "caption", m.text)
        confirm = await m.reply("<blockquote>✓ Caption saved!</blockquote>")
        user_states.pop(uid, None)
        await style_menu(c, m)
        try: await m.delete()
        except: pass
        try: await confirm.delete()
        except: pass
    elif state == "await_fname":
        if "{" not in m.text: return await m.reply("<blockquote>✗ Must include a variable like {title}</blockquote>")
        await db.set_cfg(uid, "fname", m.text)
        confirm = await m.reply("<blockquote>✓ Filename saved!</blockquote>")
        user_states.pop(uid, None)
        await style_menu(c, m)
        try: await m.delete()
        except: pass
        try: await confirm.delete()
        except: pass
    elif state == "await_u_cid":
        try:
            cid = m.forward_from_chat.id if m.forward_from_chat else int(m.text)
        except ValueError:
            cid = m.text
        await db.set_cfg(uid, "update_cid", cid)
        confirm = await m.reply(f"<blockquote>✓ Update channel saved: <code>{cid}</code></blockquote>")
        user_states.pop(uid, None)
        await update_menu(c, m)
        try: await m.delete()
        except: pass
        try: await confirm.delete()
        except: pass
    elif state == "await_u_msg":
        await db.set_cfg(uid, "update_msg", m.text)
        confirm = await m.reply("<blockquote>✓ Update message saved!</blockquote>")
        user_states.pop(uid, None)
        await update_menu(c, m)
        try: await m.delete()
        except: pass
        try: await confirm.delete()
        except: pass
    elif state == "await_u_sticker":
        if not m.sticker: return await m.reply("<blockquote>⚠ Send a sticker!</blockquote>")
        await db.set_cfg(uid, "update_sticker", m.sticker.file_id)
        confirm = await m.reply("<blockquote>✓ Sticker saved!</blockquote>")
        user_states.pop(uid, None)
        await update_menu(c, m)
        try: await m.delete()
        except: pass
        try: await confirm.delete()
        except: pass
    elif state == "await_u_btn":
        await db.set_cfg(uid, "update_btn", m.text)
        confirm = await m.reply("<blockquote>✓ Button text saved!</blockquote>")
        user_states.pop(uid, None)
        await update_menu(c, m)
        try: await m.delete()
        except: pass
        try: await confirm.delete()
        except: pass
    elif state == "await_d_cid":
        try:
            cid = m.forward_from_chat.id if m.forward_from_chat else int(m.text)
        except ValueError:
            cid = m.text
        await db.set_cfg(uid, "dump_cid", cid)
        confirm = await m.reply(f"<blockquote>✓ Dump channel saved: <code>{cid}</code></blockquote>")
        user_states.pop(uid, None)
        await pp_m(c, m)
        try: await m.delete()
        except: pass
        try: await confirm.delete()
        except: pass
    elif state == "await_p_msgs":
        dump_cid = await db.get_cfg(uid, "dump_cid") or Config.LOG_GROUP
        if not dump_cid: return await m.reply("<blockquote>⚠ Set dump channel first!</blockquote>")
        try:
            dump_cid = int(dump_cid)
        except:
            pass
        current_list = temp_data.get(uid, [])
        if not isinstance(current_list, list):
            current_list = []
        copied = await m.copy(dump_cid)
        current_list.append({"chat_id": dump_cid, "msg_id": copied.id})
        temp_data[uid] = current_list
        confirm = await m.reply(f"<blockquote>✓ Msg {len(current_list)} added</blockquote>")
        try: await m.delete()
        except: pass
        try: await confirm.delete()
        except: pass
    elif state and state.startswith("await_p_"):
        if not m.photo: return await m.reply("<blockquote>⚠ Send an image!</blockquote>")
        t = state.replace("await_p_", "")
        temp_dir = get_temp_dir(uid)
        temp_path = temp_dir / f"{t}.jpg"
        await m.download(file_name=str(temp_path))
        status = await m.reply("<blockquote>⋯ Saving image...</blockquote>")
        try:
            b64_data = await img_to_base64(str(temp_path))
            temp_path.unlink(missing_ok=True)
            await set_img_b64(uid, t, b64_data)
            await status.edit(f"<blockquote>✓ {t.title()} image saved!</blockquote>")
        except Exception as e:
            await status.edit(f"<blockquote>✗ Save failed: {e}</blockquote>")
        user_states.pop(uid, None)
        await imgs_menu(c, m)
        try: await m.delete()
        except: pass
        try: await status.delete()
        except: pass
    elif state == "await_wm":
        if not (m.photo or m.document): return await m.reply("<blockquote>⚠ Send a PNG file!</blockquote>")
        temp_dir = get_temp_dir(uid)
        temp_path = temp_dir / "wmark.png"
        await m.download(file_name=str(temp_path))
        status = await m.reply("<blockquote>⋯ Saving watermark...</blockquote>")
        try:
            b64_data = await img_to_base64(str(temp_path))
            temp_path.unlink(missing_ok=True)
            await set_wmark_b64(uid, b64_data)
            await status.edit("<blockquote>✓ Watermark saved!</blockquote>")
        except Exception as e:
            await status.edit(f"<blockquote>✗ Save failed: {e}</blockquote>")
        user_states.pop(uid, None)
        await wm_menu(c, m)
        try: await m.delete()
        except: pass
        try: await status.delete()
        except: pass
    elif state == "await_sub_thumb":
        if not m.photo: return await m.reply("<blockquote>⚠ Send an image!</blockquote>")
        sid = temp_data.get(uid)
        if not sid: return user_states.pop(uid, None)
        temp_dir = get_temp_dir(uid)
        temp_path = temp_dir / f"th_{sid}.jpg"
        status = await m.reply("<blockquote>⋯ Saving thumbnail...</blockquote>")
        try:
            await m.download(file_name=str(temp_path))
            b64_data = await img_to_base64(str(temp_path))
            temp_path.unlink(missing_ok=True)
            await db.set_sub_thumb(uid, sid, b64_data)
            await status.edit(f"<blockquote>✓ Thumbnail saved for <code>{sid}</code>!</blockquote>")
        except Exception as e:
            await status.edit(f"<blockquote>✗ Save failed: {e}</blockquote>")
        user_states.pop(uid, None)
        temp_data.pop(uid, None)
        try: await m.delete()
        except: pass
        try: await status.delete(delay=5)
        except: pass
