
from pyrogram import Client, filters
from database.db import db
from config import Config
import logging
from pyrogram.types import InlineKeyboardMarkup as KM, InlineKeyboardButton as KB
from datetime import datetime
log = logging.getLogger(__name__)
START_BANNER = "https://files.catbox.moe/14iv3j.jpg"
from plugins.fsub import force_sub
@Client.on_message(filters.command("start"))
@force_sub
async def start(c, m):
    uid = m.from_user.id
    is_new_user = False
    try:
        is_new_user = await db.add_usr(uid)
    except Exception as e:
        log.error(f"DB Error in start: {e}")
    if is_new_user and Config.LOG_GROUP:
        try:
            user = m.from_user
            username = f"@{user.username}" if user.username else "None"
            name = user.first_name + (f" {user.last_name}" if user.last_name else "")
            time_now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            log_text = (
                "<b>#NEWUSER</b>\n\n"
                f"<b>ID:</b> <code>{uid}</code>\n"
                f"<b>Username:</b> {username}\n"
                f"<b>Name:</b> {name}\n"
                f"<b>Time:</b> <code>{time_now}</code>"
            )
            await c.send_message(Config.LOG_GROUP, log_text)
        except Exception as e:
            log.error(f"Failed to log new user: {e}")
    # Deep-link: /start track_<cache_key>  or track_<src>_<id>
    args = m.command[1:] if len(m.command) > 1 else []
    if args:
        payload = args[0]
        if payload.startswith("track_"):
            key = payload[len("track_"):]
            data = await db.get_cache(key) or await db.get_cache(f"m_{key}")
            if data:
                title = data.get("title") or key
                src = data.get("src") or "?"
                await m.reply(
                    f"<b>📌 Deep-link Track</b>\n\n"
                    f"<blockquote><b>{title}</b>\nSource: <code>{src}</code></blockquote>\n"
                    f"Use /search to finish channel setup, or continue from search results.\n"
                    f"<i>Cache key:</i> <code>{key}</code>",
                    reply_markup=KM([
                        [KB("▸ Open Search", "search_help")],
                        [KB("✗ Close", "close")],
                    ]),
                )
                return
            await m.reply(
                f"<blockquote>⚠ Track link expired or invalid.\n"
                f"Key: <code>{key}</code></blockquote>\n"
                f"Run /search again and share a fresh link."
            )
            return
        if payload == "adult":
            await db.set_cfg(uid, "adult", True)
            await m.reply("✅ Adult sources enabled. Use /sources or /search.")
            return

    subs = await db.get_subs(uid)
    sub_count = len(subs) if subs else 0
    from utils.ui import START_TEXT
    sub_line = f"<b>Tracking:</b> <code>{sub_count}</code> series"
    txt = START_TEXT + "\n" + sub_line
    btns_list = [
        [
            KB("🔍 Search", "search_help"),
            KB("📚 My Subs", "open_subs"),
        ],
        [
            KB("📥 Queue", "open_queue"),
            KB("📊 Stats", "open_stats"),
        ],
        [
            KB("❓ Help", "help_msg"),
            KB("🌐 Sources", "open_sources"),
        ],
    ]
    if uid in Config.OWNER_ID:
        btns_list.append([KB("✦ Admin Panel", "open_admin")])
    btns = KM(btns_list)
    await c.send_photo(m.chat.id, START_BANNER, caption=txt, reply_markup=btns)
@Client.on_callback_query(filters.regex("^search_help$"))
async def search_help(c, q):
    txt = (
        "<b>▸ Search Guide</b>\n\n"
        "<blockquote>"
        "<b>Usage:</b>\n"
        "<code>/search solo leveling</code>\n"
        "<code>/search one piece</code>"
        "</blockquote>\n\n"
        "<blockquote>"
        "<b>Steps:</b>\n"
        "1│ Send /search with manga name\n"
        "2│ Select a source (50+ available)\n"
        "3│ Pick your manga from results\n"
        "4│ Choose starting chapter\n"
        "5│ Link your target channel\n"
        "6│ Add more sources (optional)\n"
        "7│ Bot auto-uploads new chapters!"
        "</blockquote>\n\n"
        "<blockquote>"
        "<b>Multi-Source:</b>\n"
        "Add multiple sources for same manga\n"
        "Bot checks all and uploads fastest!"
        "</blockquote>\n\n"
        "<i>Tip: Use full manga names for best results</i>"
    )
    btns = KM([
        [KB("◂ Back", "start_back")]
    ])
    try:
        await q.message.edit_caption(txt, reply_markup=btns)
    except:
        await q.message.edit_text(txt, reply_markup=btns)
    await q.answer()
@Client.on_callback_query(filters.regex("^list_help$"))
async def list_help(c, q):
    uid = q.from_user.id
    subs = await db.get_subs(uid)
    sub_count = len(subs) if subs else 0
    txt = (
        "<b>▸ Subscription Management</b>\n\n"
        f"<b>Active:</b> {sub_count} manga\n\n"
        "<blockquote>"
        "<b>Commands:</b>\n"
        "<code>/list</code> ─ View all subscriptions\n"
        "<code>/info ID</code> ─ Full manga details\n"
        "<code>/check ID</code> ─ Force check updates\n"
        "<code>/del ID</code> ─ Remove subscription"
        "</blockquote>\n\n"
        "<blockquote>"
        "<b>Examples:</b>\n"
        "<code>/info ABC123</code>\n"
        "<code>/check ABC123</code>\n"
        "<code>/del ABC123</code>"
        "</blockquote>\n\n"
        "<i>Get ID from /list command</i>"
    )
    btns = KM([
        [KB("▸ Open List", "open_list_cmd")],
        [KB("◂ Back", "start_back")]
    ])
    try:
        await q.message.edit_caption(txt, reply_markup=btns)
    except:
        await q.message.edit_text(txt, reply_markup=btns)
    await q.answer()
@Client.on_callback_query(filters.regex("^open_list_cmd$"))
async def open_list_cmd(c, q):
    from plugins.list import show_list
    await show_list(q, q.from_user.id, 0)
@Client.on_callback_query(filters.regex("^about_msg$"))
async def about_handler(c, q):
    about_txt = (
        "<b>ℹ About Manhua-Bot</b>\n\n"
        "<blockquote>"
        "<b>Features:</b>\n"
        "● 35+ manga sources\n"
        "● Auto PDF/CBZ generation\n"
        "● Multi-source tracking\n"
        "● Custom watermarks/promos\n"
        "● Channel broadcasting\n"
        "● 15-min update checks"
        "</blockquote>\n\n"
        "<blockquote>"
        "<b>Supported Sources:</b>\n"
        "Asura, Comick, MangaDex, Flame,\n"
        "Weebcentral, LikeManga, Batoto,\n"
        "MangaPark, MangaKatana, and more!"
        "</blockquote>\n\n"
        "<blockquote>"
        "<b>Developer:</b> @nullzair\n"
        "<b>Channel:</b> @codexnano\n"
        "<b>Version:</b> <code>1.0</code>"
        "</blockquote>"
    )
    btns = KM([
        [
            KB("▸ Channel", url="https://t.me/codexnano"),
            KB("▸ Developer", url="https://t.me/nullzair")
        ],
        [KB("◂ Back", "start_back")]
    ])
    try:
        await q.message.edit_caption(about_txt, reply_markup=btns)
    except:
        await q.message.edit_text(about_txt, reply_markup=btns)
    await q.answer()
@Client.on_callback_query(filters.regex("^start_back$"))
async def start_back(c, q):
    uid = q.from_user.id
    # Deep-link: /start track_<cache_key>  or track_<src>_<id>
    args = m.command[1:] if len(m.command) > 1 else []
    if args:
        payload = args[0]
        if payload.startswith("track_"):
            key = payload[len("track_"):]
            data = await db.get_cache(key) or await db.get_cache(f"m_{key}")
            if data:
                title = data.get("title") or key
                src = data.get("src") or "?"
                await m.reply(
                    f"<b>📌 Deep-link Track</b>\n\n"
                    f"<blockquote><b>{title}</b>\nSource: <code>{src}</code></blockquote>\n"
                    f"Use /search to finish channel setup, or continue from search results.\n"
                    f"<i>Cache key:</i> <code>{key}</code>",
                    reply_markup=KM([
                        [KB("▸ Open Search", "search_help")],
                        [KB("✗ Close", "close")],
                    ]),
                )
                return
            await m.reply(
                f"<blockquote>⚠ Track link expired or invalid.\n"
                f"Key: <code>{key}</code></blockquote>\n"
                f"Run /search again and share a fresh link."
            )
            return
        if payload == "adult":
            await db.set_cfg(uid, "adult", True)
            await m.reply("✅ Adult sources enabled. Use /sources or /search.")
            return

    subs = await db.get_subs(uid)
    sub_count = len(subs) if subs else 0
    txt = (
        "<b>░ Manhua-Bot</b>\n"
        "<i>Automatic Manga Chapter Uploader</i>\n\n"
        "<blockquote>"
        "<b>Quick Start:</b>\n"
        "1│ /search <code>manga name</code>\n"
        "2│ Select source and manga\n"
        "3│ Choose starting chapter\n"
        "4│ Link your channel\n"
        "5│ /settings to configure"
        "</blockquote>\n\n"
        f"<b>Tracking:</b> <code>{sub_count}</code> manga"
    )
    btns_list = []
    btns_list.append([
        KB("▸ Search", "search_help"),
        KB("? Help", "help_msg")
    ])
    btns_list.append([
        KB("ℹ About", "about_msg"),
        KB("⚠ Updates", url="https://t.me/codexnano")
    ])
    if q.from_user.id in Config.OWNER_ID:
        btns_list.append([KB("✦ Admin Panel", "open_admin")])
    try:
        await q.message.edit_caption(caption=txt, reply_markup=KM(btns_list))
    except:
        await q.message.edit_text(txt, reply_markup=KM(btns_list))
    await q.answer()
@Client.on_callback_query(filters.regex("^cb$"))
async def cb_void(c, q): await q.answer("This button has no action.", show_alert=False)
@Client.on_message(filters.command("help"))
@Client.on_callback_query(filters.regex("^help_msg$"))
async def help_handler(c, u):
    uid = u.from_user.id
    is_owner = uid in Config.OWNER_ID
    help_txt = (
        "<b>? Command Guide</b>\n\n"
        "<blockquote>"
        "<b>▸ Search & Track</b>\n"
        "<code>/search name</code> ─ Find manga\n"
        "<code>/list</code> ─ View subscriptions\n"
        "<code>/info ID</code> ─ Manga details\n"
        "<code>/check ID</code> ─ Force update\n"
        "<code>/del ID</code> ─ Remove tracking"
        "</blockquote>\n\n"
        "<blockquote>"
        "<b>▸ Settings</b>\n"
        "<code>/settings</code> ─ All preferences\n"
        "<code>/help</code> ─ This menu\n"
        "<code>/start</code> ─ Home screen"
        "</blockquote>\n\n"
        "<blockquote>"
        "<b>▸ Broadcast</b>\n"
        "<code>/cbroadcast</code> ─ Send to all channels\n"
        "<i>Reply to a message to broadcast</i>"
        "</blockquote>"
    )
    if is_owner:
        help_txt += (
            "\n\n<blockquote>"
            "<b>✦ Admin Commands</b>\n"
            "<code>/stats</code> ─ Bot statistics\n"
            "<code>/dbstats</code> ─ Database info\n"
            "<code>/broadcast</code> ─ Send to all users\n"
            "<code>/ban ID</code> ─ Ban user\n"
            "<code>/unban ID</code> ─ Unban user\n"
            "<code>/banned</code> ─ List banned\n"
            "<code>/deluser ID</code> ─ Delete user data"
            "</blockquote>"
        )
    btns_list = []
    btns_list.append([KB("◂ Back", "start_back"), KB("✕ Close", "close")])
    markup = KM(btns_list)
    target = u.message if hasattr(u, "message") else u
    if hasattr(u, "message"):
        try:
            await u.message.edit_caption(help_txt, reply_markup=markup)
        except:
            await u.message.edit_text(help_txt, reply_markup=markup)
    else:
        await target.reply(help_txt, reply_markup=markup)
    if hasattr(u, "answer"): await u.answer()
@Client.on_message(filters.command("stats") & filters.user(Config.OWNER_ID))
@Client.on_callback_query(filters.regex("^open_admin$"))
async def admin_handler(c, u):
    if u.from_user.id not in Config.OWNER_ID:
        if hasattr(u, "answer"): await u.answer("Access Denied", show_alert=True)
        return
    cnt = await db.tot_usrs()
    stats = await db.db_stats()
    txt = (
        "<b>✦ Admin Panel</b>\n\n"
        "<blockquote>"
        "<b>Statistics:</b>\n"
        f"Users: <code>{cnt}</code>\n"
        f"Subscriptions: <code>{stats['subs']}</code>\n"
        f"Banned: <code>{stats['banned']}</code>\n"
        f"Cache: <code>{stats['cache']}</code>\n"
        f"Status: <code>Running</code>"
        "</blockquote>\n\n"
        "<blockquote>"
        "<b>Commands:</b>\n"
        "<code>/ban ID [reason]</code>\n"
        "<code>/unban ID</code>\n"
        "<code>/banned</code> │ List banned\n"
        "<code>/dbstats</code> │ DB cleanup\n"
        "<code>/deluser ID</code> │ Wipe user"
        "</blockquote>"
    )
    markup = KM([
        [
            KB("▸ DB Stats", "db_stats_panel"),
            KB("▸ Banned", "banned_list_panel")
        ],
        [KB("✕ Close", "close")]
    ])
    if hasattr(u, "message"):
        try:
            await u.message.edit_caption(txt, reply_markup=markup)
        except:
            await u.message.edit_text(txt, reply_markup=markup)
    else:
        await u.reply(txt, reply_markup=markup)
    if hasattr(u, "answer"): await u.answer()
@Client.on_callback_query(filters.regex("^db_stats_panel$"))
async def db_stats_panel(c, q):
    if q.from_user.id not in Config.OWNER_ID:
        return await q.answer("Access Denied", show_alert=True)
    stats = await db.db_stats()
    txt = (
        "<b>▸ Database Stats</b>\n\n"
        "<blockquote>"
        "<b>Collections:</b>\n"
        f"Users: <code>{stats['users']}</code>\n"
        f"Subscriptions: <code>{stats['subs']}</code>\n"
        f"Config: <code>{stats['conf']}</code>\n"
        f"Cache: <code>{stats['cache']}</code>\n"
        f"Banned: <code>{stats['banned']}</code>"
        "</blockquote>"
    )
    markup = KM([
        [
            KB("⊖ Clear Cache", "clr_cache"),
            KB("⊖ Clear Conf", "clr_conf")
        ],
        [KB("◂ Back", "open_admin")]
    ])
    try:
        await q.message.edit_caption(txt, reply_markup=markup)
    except:
        await q.message.edit_text(txt, reply_markup=markup)
    await q.answer()
@Client.on_callback_query(filters.regex("^banned_list_panel$"))
async def banned_list_panel(c, q):
    if q.from_user.id not in Config.OWNER_ID:
        return await q.answer("Access Denied", show_alert=True)
    banned = await db.get_banned_users()
    if not banned:
        txt = "<b>▸ Banned Users</b>\n\n<blockquote><i>No banned users</i></blockquote>"
    else:
        txt = "<b>▸ Banned Users</b>\n\n<blockquote>"
        for i, user in enumerate(banned[:10], 1):
            uid = user.get('id', '?')
            reason = user.get('ban_reason', 'No reason')[:30]
            txt += f"{i}. <code>{uid}</code> │ {reason}\n"
        if len(banned) > 10:
            txt += f"\n<i>...and {len(banned) - 10} more</i>"
        txt += "</blockquote>"
    markup = KM([[KB("◂ Back", "open_admin")]])
    try:
        await q.message.edit_caption(txt, reply_markup=markup)
    except:
        await q.message.edit_text(txt, reply_markup=markup)
    await q.answer()
@Client.on_callback_query(filters.regex("^close$"))
async def close_cb(c, q):
    try: await q.message.delete()
    except: pass
