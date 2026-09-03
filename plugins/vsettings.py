# Manhua-Bot - /usettings : per-user upload & video settings
#
# Owner-only management of *other* users lives in plugins/usettings.py and is
# triggered by `/usettings <user_id>`. This module handles the bare
# `/usettings` call, which every user may run on their own account.

from __future__ import annotations

import base64
import logging

from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup as KM, InlineKeyboardButton as KB

from database.db import db
from plugins.fsub import force_sub
from plugins.settings.shared import StateDictWrapper, get_temp_dir

# Isolated from plugins.settings.shared.user_states on purpose: the settings
# listener claims every private message for any uid present in that dict, which
# would swallow input meant for this panel.
_vstates = StateDictWrapper({})
from services.video_dl import DEFAULTS, vget, vset, has_ffmpeg

log = logging.getLogger(__name__)

QUALITIES = ["480", "720", "1080", "best"]


def _s(val) -> str:
    return "●" if val else "○"


def _set(val) -> str:
    return "◆" if val else "◇"


async def _panel_text(uid: int) -> str:
    mode = await vget(uid, "v_upload")
    quality = await vget(uid, "v_quality")
    thumb = await vget(uid, "v_thumb")
    m_title = await vget(uid, "v_meta_title")
    m_author = await vget(uid, "v_meta_author")
    caption = await vget(uid, "v_caption")
    split = await vget(uid, "v_split")
    subs = await vget(uid, "v_subs")
    ftype = await db.get_cfg(uid, "ftype", "pdf")

    warn = "" if has_ffmpeg() else "\n<i>⚠️ ffmpeg not found — metadata/thumb limited</i>"

    return (
        "<b>░ Your Settings</b>\n"
        f"<b>ID:</b> <code>{uid}</code>\n\n"
        "<blockquote>"
        "<b>▸ Video / Anime</b>\n"
        f"Upload as: <code>{'Document' if mode == 'document' else 'Video'}</code>\n"
        f"Quality: <code>{quality if quality == 'best' else quality + 'p'}</code>\n"
        f"Thumbnail: {_set(thumb)}\n"
        f"Auto-split &gt;2GB: {_s(split)}\n"
        f"Subtitles (eng): {_s(subs)}"
        "</blockquote>\n\n"
        "<blockquote>"
        "<b>▸ Metadata</b>\n"
        f"Title: <code>{m_title}</code>\n"
        f"Author: <code>{m_author or 'Not set'}</code>\n"
        f"Caption: {_set(caption)}"
        "</blockquote>\n\n"
        "<blockquote>"
        "<b>▸ Manga</b>\n"
        f"File type: <code>{ftype}</code>  (pdf/cbz/links)"
        "</blockquote>\n\n"
        "<i>Placeholders: {title} {ep} {source} {quality} {size} {dur}</i>"
        + warn
    )


def _panel_kb(mode: str, thumb, split, subs) -> KM:
    return KM(
        [
            [
                KB(f"{'📄' if mode == 'document' else '🎬'} Upload: "
                   f"{'Document' if mode == 'document' else 'Video'}", "vs_mode"),
            ],
            [KB("▸ Quality", "vs_qmenu"), KB("▸ Metadata", "vs_meta")],
            [
                KB(f"🖼 Thumbnail {_set(thumb)}", "vs_thumb"),
                KB(f"✂️ Split {_s(split)}", "vs_split"),
            ],
            [
                KB(f"💬 Subtitles {_s(subs)}", "vs_subs"),
                KB("⚙ Engine", "vengine_cb"),
            ],
            [KB("▸ Manga file type", "vs_ftype"), KB("↻ Reset", "vs_reset")],
            [KB("✕ Close", "close")],
        ]
    )


async def show_panel(target, uid: int, edit: bool = False):
    text = await _panel_text(uid)
    kb = _panel_kb(
        await vget(uid, "v_upload"),
        await vget(uid, "v_thumb"),
        await vget(uid, "v_split"),
        await vget(uid, "v_subs"),
    )
    if edit and hasattr(target, "message"):
        try:
            await target.message.edit(text, reply_markup=kb)
            return
        except Exception:
            pass
    msg = target.message if hasattr(target, "message") else target
    await msg.reply(text, reply_markup=kb)


@Client.on_message(
    filters.command("usettings")
    & filters.create(lambda _, __, m: len(getattr(m, "command", [])) == 1)
)
@force_sub
async def usettings_self(c, m):
    uid = m.from_user.id
    await db.add_usr(uid)
    await show_panel(m, uid)


@Client.on_callback_query(filters.regex(r"^vs_back$"))
async def vs_back(c, q):
    await show_panel(q, q.from_user.id, edit=True)


@Client.on_callback_query(filters.regex(r"^vs_mode$"))
async def vs_mode(c, q):
    uid = q.from_user.id
    curr = await vget(uid, "v_upload")
    new = "document" if curr == "video" else "video"
    await vset(uid, "v_upload", new)
    await q.answer(f"Uploading as {new}")
    await show_panel(q, uid, edit=True)


@Client.on_callback_query(filters.regex(r"^vs_split$"))
async def vs_split(c, q):
    uid = q.from_user.id
    curr = await vget(uid, "v_split")
    await vset(uid, "v_split", not curr)
    await q.answer(f"Split: {'on' if not curr else 'off'}")
    await show_panel(q, uid, edit=True)


@Client.on_callback_query(filters.regex(r"^vs_subs$"))
async def vs_subs(c, q):
    uid = q.from_user.id
    curr = await vget(uid, "v_subs")
    await vset(uid, "v_subs", not curr)
    await q.answer(
        "Subtitles on — English .ass is muxed into MKV when found"
        if not curr else "Subtitles off",
        show_alert=not curr,
    )
    await show_panel(q, uid, edit=True)


@Client.on_callback_query(filters.regex(r"^vs_qmenu$"))
async def vs_qmenu(c, q):
    uid = q.from_user.id
    curr = await vget(uid, "v_quality")
    from services import vengine
    rows = [
        [KB(f"{'● ' if curr == x else ''}{vengine.quality_label(x)}", f"vs_q_{x}")
         for x in QUALITIES[:2]],
        [KB(f"{'● ' if curr == x else ''}{vengine.quality_label(x)}", f"vs_q_{x}")
         for x in QUALITIES[2:]],
        [KB("◂ Back", "vs_back")],
    ]
    await q.message.edit(
        "<b>▸ Video Quality</b>\n\n"
        "<blockquote>Highest available stream at or below the selected "
        "height is picked. <code>best</code> ignores the cap.</blockquote>",
        reply_markup=KM(rows),
    )


@Client.on_callback_query(filters.regex(r"^vs_q_"))
async def vs_q(c, q):
    uid = q.from_user.id
    val = q.data.split("_", 2)[2]
    await vset(uid, "v_quality", val)
    await q.answer(f"Quality: {val}")
    await vs_qmenu(c, q)


@Client.on_callback_query(filters.regex(r"^vs_ftype$"))
async def vs_ftype(c, q):
    uid = q.from_user.id
    curr = await db.get_cfg(uid, "ftype", "pdf")
    rows = [
        [
            KB(f"{'● ' if curr == x else ''}{x.upper()}", f"vs_ft_{x}")
            for x in ("pdf", "cbz", "links")
        ],
        [KB("◂ Back", "vs_back")],
    ]
    await q.message.edit(
        "<b>▸ Manga File Type</b>\n\n"
        "<blockquote>PDF · CBZ · Links (raw image URLs)</blockquote>",
        reply_markup=KM(rows),
    )


@Client.on_callback_query(filters.regex(r"^vs_ft_"))
async def vs_ft(c, q):
    await db.set_cfg(q.from_user.id, "ftype", q.data.split("_", 2)[2])
    await q.answer("Saved")
    await vs_ftype(c, q)


@Client.on_callback_query(filters.regex(r"^vs_meta$"))
async def vs_meta(c, q):
    uid = q.from_user.id
    m_title = await vget(uid, "v_meta_title")
    m_author = await vget(uid, "v_meta_author")
    caption = await vget(uid, "v_caption")
    await q.message.edit(
        "<b>▸ Metadata</b>\n\n"
        "<blockquote>"
        f"Title: <code>{m_title}</code>\n"
        f"Author: <code>{m_author or 'Not set'}</code>\n"
        f"Caption: <code>{caption or 'Default'}</code>"
        "</blockquote>\n\n"
        "<i>Placeholders: {title} {ep} {source} {quality} {size} {dur}</i>",
        reply_markup=KM(
            [
                [KB("✎ Title", "vs_e_v_meta_title"), KB("✎ Author", "vs_e_v_meta_author")],
                [KB("✎ Caption", "vs_e_v_caption"), KB("⊖ Clear caption", "vs_c_v_caption")],
                [KB("◂ Back", "vs_back")],
            ]
        ),
    )


@Client.on_callback_query(filters.regex(r"^vs_e_"))
async def vs_edit_ask(c, q):
    uid = q.from_user.id
    key = q.data.replace("vs_e_", "")
    _vstates[uid] = f"vset:{key}"
    labels = {
        "v_meta_title": "metadata title",
        "v_meta_author": "metadata author",
        "v_caption": "upload caption",
    }
    await q.message.edit(
        f"<b>✎ Set {labels.get(key, key)}</b>\n\n"
        "<blockquote>Send the new text now.\n"
        "Placeholders: <code>{title} {ep} {source} {quality} {size} {dur}</code>"
        "</blockquote>\n\n<i>Or /cancel</i>"
    )


@Client.on_callback_query(filters.regex(r"^vs_c_"))
async def vs_clear(c, q):
    key = q.data.replace("vs_c_", "")
    await vset(q.from_user.id, key, None)
    await q.answer("Cleared")
    await vs_meta(c, q)


@Client.on_callback_query(filters.regex(r"^vs_thumb$"))
async def vs_thumb(c, q):
    uid = q.from_user.id
    thumb = await vget(uid, "v_thumb")
    rows = [[KB("⊕ Send new image", "vs_thumb_set")]]
    if thumb:
        rows.append([KB("⊖ Remove thumbnail", "vs_thumb_del")])
    rows.append([KB("◂ Back", "vs_back")])
    await q.message.edit(
        "<b>▸ Custom Thumbnail</b>\n\n"
        "<blockquote>"
        f"Status: {_set(thumb)}\n"
        "Used for every video/document upload. If unset, a frame is grabbed "
        "from the video automatically."
        "</blockquote>",
        reply_markup=KM(rows),
    )


@Client.on_callback_query(filters.regex(r"^vs_thumb_set$"))
async def vs_thumb_set(c, q):
    _vstates[q.from_user.id] = "vset:thumb"
    await q.message.edit(
        "<b>🖼 Send the thumbnail image</b>\n\n"
        "<blockquote>Send a photo (JPEG works best, ideally 320px wide)."
        "</blockquote>\n\n<i>Or /cancel</i>"
    )


@Client.on_callback_query(filters.regex(r"^vs_thumb_del$"))
async def vs_thumb_del(c, q):
    await vset(q.from_user.id, "v_thumb", None)
    await q.answer("Thumbnail removed")
    await vs_thumb(c, q)


@Client.on_callback_query(filters.regex(r"^vs_reset$"))
async def vs_reset(c, q):
    uid = q.from_user.id
    for key, val in DEFAULTS.items():
        await vset(uid, key, val)
    await q.answer("Video settings reset", show_alert=True)
    await show_panel(q, uid, edit=True)


# ------------------------------------------------------------- input hooks
def _pending(_, __, m):
    state = _vstates.get(m.from_user.id) if m.from_user else None
    return bool(state and str(state).startswith("vset:"))


@Client.on_message(filters.private & filters.photo & filters.create(_pending))
async def vs_thumb_recv(c, m):
    uid = m.from_user.id
    if _vstates.get(uid) != "vset:thumb":
        return
    _vstates.pop(uid, None)
    tmp = get_temp_dir(uid) / "thumb_in.jpg"
    try:
        await c.download_media(m.photo, file_name=str(tmp))
        data = base64.b64encode(tmp.read_bytes()).decode()
        await vset(uid, "v_thumb", data)
        await m.reply("<blockquote>✓ Thumbnail saved.</blockquote>")
    except Exception as exc:
        log.error(f"[VSET] thumb: {exc}")
        await m.reply("<blockquote>⚠ Could not save that image.</blockquote>")
    finally:
        try:
            tmp.unlink(missing_ok=True)
        except Exception:
            pass
    await show_panel(m, uid)


@Client.on_message(filters.private & filters.text & filters.create(_pending))
async def vs_text_recv(c, m):
    uid = m.from_user.id
    state = _vstates.get(uid) or ""
    key = state.split(":", 1)[1]
    if key == "thumb":
        return  # waiting on a photo, ignore stray text
    _vstates.pop(uid, None)
    if m.text.strip() == "/cancel":
        return await m.reply("Cancelled.")
    await vset(uid, key, m.text.strip())
    await m.reply("<blockquote>✓ Saved.</blockquote>")
    await show_panel(m, uid)
