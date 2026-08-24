
from pyrogram import Client, filters, StopPropagation, ContinuePropagation
from pyrogram.types import InlineKeyboardMarkup as KM, InlineKeyboardButton as KB
from database.db import db
from config import Config
import logging
log = logging.getLogger(__name__)
def owner_only(_, __, m):
    return m.from_user and m.from_user.id in Config.OWNER_ID
owner_filter = filters.create(owner_only)
async def not_banned(_, __, m):
    if not m.from_user:
        return True
    banned, _ = await db.is_banned(m.from_user.id)
    return not banned
not_banned_filter = filters.create(not_banned)
@Client.on_message(filters.private & ~owner_filter, group=-1)
async def ban_check_msg(c, m):
    if not m.from_user:
        raise ContinuePropagation
    banned, reason = await db.is_banned(m.from_user.id)
    if banned:
        await m.reply(
            "<b>[X] Access Denied</b>\n\n"
            "You have been banned from using this bot.\n"
            f"<b>Reason:</b> <code>{reason}</code>"
        )
        raise StopPropagation
    raise ContinuePropagation
@Client.on_callback_query(filters.create(lambda _, __, q: q.from_user and q.from_user.id not in Config.OWNER_ID), group=-1)
async def ban_check_cb(c, q):
    banned, reason = await db.is_banned(q.from_user.id)
    if banned:
        await q.answer(f"[X] Banned: {reason}", show_alert=True)
        raise StopPropagation
    raise ContinuePropagation
@Client.on_message(filters.command("ban") & filters.private & owner_filter)
async def ban_usr_cmd(c, m):
    args = m.text.split(None, 2)
    if len(args) < 2:
        return await m.reply(
            "<b>[BAN] Usage</b>\n\n"
            "<code>/ban &lt;uid&gt; [reason]</code>\n\n"
            "<b>Example:</b>\n"
            "<code>/ban 123456789 Spamming</code>"
        )
    try:
        uid = int(args[1])
    except ValueError:
        return await m.reply("[X] Invalid UID. Must be a number.")
    if uid in Config.OWNER_ID:
        return await m.reply("[X] Cannot ban owner!")
    reason = args[2] if len(args) > 2 else "No reason"
    await db.ban_usr(uid, reason)
    await m.reply(
        f"<b>[+] User Banned</b>\n\n"
        f"<b>UID:</b> <code>{uid}</code>\n"
        f"<b>Reason:</b> <code>{reason}</code>"
    )
    log.info(f"[ADMIN] User {uid} banned. Reason: {reason}")
@Client.on_message(filters.command("unban") & filters.private & owner_filter)
async def unban_usr_cmd(c, m):
    args = m.text.split(None, 1)
    if len(args) < 2:
        return await m.reply(
            "<b>[UNBAN] Usage</b>\n\n"
            "<code>/unban &lt;uid&gt;</code>\n\n"
            "<b>Example:</b>\n"
            "<code>/unban 123456789</code>"
        )
    try:
        uid = int(args[1])
    except ValueError:
        return await m.reply("[X] Invalid UID. Must be a number.")
    banned, reason = await db.is_banned(uid)
    if not banned:
        return await m.reply(f"[!] User <code>{uid}</code> is not banned.")
    await db.unban_usr(uid)
    await m.reply(
        f"<b>┌─ USER UNBANNED ─┐</b>\n\n"
        f"│ <b>UID:</b> <code>{uid}</code>\n"
        f"│ <b>Was:</b> <code>{reason}</code>\n"
        "└───────────────────"
    )
    log.info(f"[ADMIN] User {uid} unbanned")
@Client.on_message(filters.command("banned") & filters.private & owner_filter)
async def banned_list(c, m):
    banned = await db.get_banned_users()
    if not banned:
        return await m.reply("<b>[=] No banned users.</b>")
    txt = "<b>┌─ BANNED USERS ─┐</b>\n\n"
    for u in banned[:50]:
        uid = u.get('id')
        reason = u.get('ban_reason', 'No reason')
        txt += f"│ <code>{uid}</code> ─► {reason}\n"
    if len(banned) > 50:
        txt += f"│ <i>... +{len(banned) - 50} more</i>\n"
    txt += "└───────────────────"
    await m.reply(txt)
@Client.on_message(filters.command("dbstats") & filters.private & owner_filter)
async def db_stats_cmd(c, m):
    stats = await db.db_stats()
    txt = (
        "<b>[DB] Statistics</b>\n\n"
        f"<b>Users:</b> <code>{stats['users']}</code>\n"
        f"<b>Subs:</b> <code>{stats['subs']}</code>\n"
        f"<b>Conf:</b> <code>{stats['conf']}</code>\n"
        f"<b>Cache:</b> <code>{stats['cache']}</code>\n"
        f"<b>Banned:</b> <code>{stats['banned']}</code>"
    )
    await m.reply(txt, reply_markup=KM([
        [KB("[CLEAR] Menu", "admin_clr_menu")]
    ]))
@Client.on_callback_query(filters.regex("^admin_clr_menu") & owner_filter)
async def clr_menu(c, q):
    await q.message.edit(
        "<b>[!] Database Cleanup</b>\n\n"
        "<i>Select what to clear. IRREVERSIBLE!</i>",
        reply_markup=KM([
            [KB("[DEL] Users", "admin_clr_users")],
            [KB("[DEL] Subs", "admin_clr_subs")],
            [KB("[DEL] Conf", "admin_clr_conf")],
            [KB("[DEL] Cache", "admin_clr_cache")],
            [KB("[DEL] ALL", "admin_clr_all")],
            [KB("<< Back", "admin_back_stats")]
        ])
    )
@Client.on_callback_query(filters.regex("^admin_back_stats") & owner_filter)
async def back_stats(c, q):
    stats = await db.db_stats()
    txt = (
        "<b>[DB] Statistics</b>\n\n"
        f"<b>Users:</b> <code>{stats['users']}</code>\n"
        f"<b>Subs:</b> <code>{stats['subs']}</code>\n"
        f"<b>Conf:</b> <code>{stats['conf']}</code>\n"
        f"<b>Cache:</b> <code>{stats['cache']}</code>\n"
        f"<b>Banned:</b> <code>{stats['banned']}</code>"
    )
    await q.message.edit(txt, reply_markup=KM([
        [KB("[CLEAR] Menu", "admin_clr_menu")]
    ]))
@Client.on_callback_query(filters.regex("^admin_clr_users") & owner_filter)
async def clr_users(c, q):
    await q.message.edit(
        "<b>[!] Clear ALL Users?</b>\n\n"
        "<i>Removes all user records.</i>",
        reply_markup=KM([
            [KB("[YES] Clear", "admin_ok_clr_users")],
            [KB("[X] Cancel", "admin_clr_menu")]
        ])
    )
@Client.on_callback_query(filters.regex("^admin_ok_clr_users") & owner_filter)
async def ok_clr_users(c, q):
    res = await db.clear_all_users()
    await q.answer(f"Deleted {res.deleted_count} users!", show_alert=True)
    log.warning(f"[ADMIN] All users cleared by {q.from_user.id}")
    await back_stats(c, q)
@Client.on_callback_query(filters.regex("^admin_clr_subs") & owner_filter)
async def clr_subs(c, q):
    await q.message.edit(
        "<b>[!] Clear ALL Subs?</b>\n\n"
        "<i>Removes all manga subs.</i>",
        reply_markup=KM([
            [KB("[YES] Clear", "admin_ok_clr_subs")],
            [KB("[X] Cancel", "admin_clr_menu")]
        ])
    )
@Client.on_callback_query(filters.regex("^admin_ok_clr_subs") & owner_filter)
async def ok_clr_subs(c, q):
    res = await db.clear_all_subs()
    await q.answer(f"Deleted {res.deleted_count} subs!", show_alert=True)
    log.warning(f"[ADMIN] All subs cleared by {q.from_user.id}")
    await back_stats(c, q)
@Client.on_callback_query(filters.regex("^admin_clr_conf") & owner_filter)
async def clr_conf(c, q):
    await q.message.edit(
        "<b>[!] Clear ALL Conf?</b>\n\n"
        "<i>Removes all user settings.</i>",
        reply_markup=KM([
            [KB("[YES] Clear", "admin_ok_clr_conf")],
            [KB("[X] Cancel", "admin_clr_menu")]
        ])
    )
@Client.on_callback_query(filters.regex("^admin_ok_clr_conf") & owner_filter)
async def ok_clr_conf(c, q):
    res = await db.clear_all_conf()
    await q.answer(f"Deleted {res.deleted_count} conf!", show_alert=True)
    log.warning(f"[ADMIN] All conf cleared by {q.from_user.id}")
    await back_stats(c, q)
@Client.on_callback_query(filters.regex("^admin_clr_cache") & owner_filter)
async def clr_cache(c, q):
    await q.message.edit(
        "<b>[!] Clear ALL Cache?</b>\n\n"
        "<i>Removes all cached data.</i>",
        reply_markup=KM([
            [KB("[YES] Clear", "admin_ok_clr_cache")],
            [KB("[X] Cancel", "admin_clr_menu")]
        ])
    )
@Client.on_callback_query(filters.regex("^admin_ok_clr_cache") & owner_filter)
async def ok_clr_cache(c, q):
    res = await db.clear_all_cache(force=True)
    await q.answer(f"Deleted {res.deleted_count} cache!", show_alert=True)
    log.warning(f"[ADMIN] All cache cleared by {q.from_user.id}")
    await back_stats(c, q)
@Client.on_callback_query(filters.regex("^admin_clr_all") & owner_filter)
async def clr_all(c, q):
    await q.message.edit(
        "<b>[!!] CLEAR ENTIRE DB?</b>\n\n"
        "<b>Deletes:</b>\n"
        "- All users\n"
        "- All subs\n"
        "- All conf\n"
        "- All cache\n\n"
        "<i>[!] IRREVERSIBLE!</i>",
        reply_markup=KM([
            [KB("[YES] CLEAR ALL", "admin_final_clr")],
            [KB("[X] Cancel", "admin_clr_menu")]
        ])
    )
@Client.on_callback_query(filters.regex("^admin_final_clr") & owner_filter)
async def final_clr(c, q):
    r1 = await db.clear_all_users()
    r2 = await db.clear_all_subs()
    r3 = await db.clear_all_conf()
    r4 = await db.clear_all_cache(force=True)
    total = r1.deleted_count + r2.deleted_count + r3.deleted_count + r4.deleted_count
    await q.answer(f"Deleted {total} total!", show_alert=True)
    log.warning(f"[ADMIN] ENTIRE DB cleared by {q.from_user.id}")
    await back_stats(c, q)
@Client.on_message(filters.command("deluser") & filters.private & owner_filter)
async def del_usr_data(c, m):
    args = m.text.split(None, 1)
    if len(args) < 2:
        return await m.reply(
            "<b>[DEL] User Data</b>\n\n"
            "<code>/deluser &lt;uid&gt;</code>\n\n"
            "<i>Removes all data for user.</i>"
        )
    try:
        uid = int(args[1])
    except ValueError:
        return await m.reply("[X] Invalid UID. Must be a number.")
    await db.clear_user_data(uid)
    await m.reply(f"<b>[+] All data for <code>{uid}</code> deleted.</b>")
    log.info(f"[ADMIN] User {uid} data deleted by {m.from_user.id}")
