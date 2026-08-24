
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup as KM, InlineKeyboardButton as KB, InputMediaPhoto
from database.db import db
from plugins.settings.shared import edit_msg, _set, user_states, has_img, get_img_url, clear_img_url
@Client.on_callback_query(filters.regex("^menu_imgs"))
async def imgs_menu(c, q):
    uid = q.from_user.id
    has_first = await has_img(uid, "first")
    has_last = await has_img(uid, "last")
    has_thumb = await has_img(uid, "thumb")
    thumb_src = await db.get_cfg(uid, "thumb_src", "first")
    txt = (
        "<b>░ Promo Images</b>\n\n"
        "<blockquote>"
        f"<b>First Page:</b> {_set(has_first)}\n"
        f"<b>Last Page:</b> {_set(has_last)}\n"
        f"<b>Thumbnail:</b> {_set(has_thumb)}\n"
        f"<b>Thumb Src:</b> {thumb_src.title()}"
        "</blockquote>\n\n"
        "<i>Add custom pages and cover to your PDFs</i>"
    )
    btns = KM([
        [
            KB(f"⊕ First {_set(has_first)}", "set_p_first"),
            KB(f"⊕ Last {_set(has_last)}", "set_p_last")
        ],
        [
            KB(f"↻ Src: {thumb_src.title()}", "t_thumb_src"),
            KB(f"⊕ Thumb {_set(has_thumb)}", "set_p_thumb")
        ],
        [
            KB("▸ Preview All", "v_p_imgs"),
            KB("⊖ Clear All", "c_p_imgs")
        ],
        [KB("◂ Back", "open_main")]
    ])
    await edit_msg(c, q, txt, reply_markup=btns)
@Client.on_callback_query(filters.regex("^t_thumb_src"))
async def t_thumb_src(c, q):
    uid = q.from_user.id
    curr = await db.get_cfg(uid, "thumb_src", "first")
    cycle = {"first": "last", "last": "custom", "custom": "first"}
    await db.set_cfg(uid, "thumb_src", cycle.get(curr, "first"))
    await imgs_menu(c, q)
@Client.on_callback_query(filters.regex("^set_p_"))
async def ask_img(c, q):
    uid = q.from_user.id
    type_ = q.data.replace("set_p_", "")
    user_states[uid] = f"await_p_{type_}"
    await q.message.edit(
        f"<b>⊕ Upload {type_.title()} Image</b>\n\n"
        f"<blockquote>Send an image for the {type_} page</blockquote>\n\n"
        "<i>Or /cancel</i>"
    )
@Client.on_callback_query(filters.regex("^c_p_imgs"))
async def clear_imgs(c, q):
    uid = q.from_user.id
    for t in ["first", "last", "thumb"]:
        await clear_img_url(uid, t)
    await q.answer("Cleared.")
    await imgs_menu(c, q)
@Client.on_callback_query(filters.regex("^v_p_imgs"))
async def view_imgs(c, q):
    from plugins.settings.shared import get_img_data, base64_to_file, get_temp_dir
    import os
    uid = q.from_user.id
    found = False
    for t, lab in [("first", "First"), ("last", "Last"), ("thumb", "Thumb")]:
        dtype, dval = await get_img_data(uid, t)
        if not dtype or not dval: continue
        found = True
        try:
            if dtype == 'url':
                await c.send_photo(q.message.chat.id, dval, caption=f"[PREVIEW] {lab} Page")
            elif dtype == 'b64':
                temp_dir = get_temp_dir(uid)
                temp_path = temp_dir / f"prev_{t}.jpg"
                await base64_to_file(dval, str(temp_path))
                await c.send_photo(q.message.chat.id, str(temp_path), caption=f"[PREVIEW] {lab} Page")
                if os.path.exists(temp_path): os.remove(temp_path)
        except Exception as e:
            await q.message.reply(f"Failed to show {lab} preview: {e}")
    if not found: await q.answer("No images set.")
    else: await q.answer("Sent previews.")
