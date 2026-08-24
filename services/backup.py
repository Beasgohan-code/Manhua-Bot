# Manhua-Bot - Database backup (PostgreSQL)

import json
import logging
from datetime import datetime
from pathlib import Path
from database.db import db
from config import Config

log = logging.getLogger(__name__)

async def create_db_backup(app):
    if not Config.LOG_GROUP:
        log.warning("[BACKUP] No LOG_GROUP configured. Skipping backup.")
        return
    try:
        log.info("[BACKUP] Starting database backup...")
        users = await db.get_all_users()
        subs = await db.get_subs()
        # conf is per-user; skip full dump for size or collect lightly
        backup_data = {
            "users": users,
            "subs": subs,
            "meta": {
                "engine": "postgresql",
                "generated_at": datetime.now().isoformat(),
            },
        }
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"db_backup_{timestamp}.json"
        filepath = Path(filename)
        with open(filepath, "w") as f:
            json.dump(backup_data, f, indent=2, default=str)
        await app.send_document(
            chat_id=Config.LOG_GROUP,
            document=str(filepath),
            caption=(
                f"<b>[#BACKUP] Manhua-Bot Database Backup</b>\n\n"
                f"<b>Date:</b> <code>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</code>\n"
                f"<b>Users:</b> <code>{len(users)}</code>\n"
                f"<b>Subscriptions:</b> <code>{len(subs)}</code>"
            ),
        )
        filepath.unlink(missing_ok=True)
        log.info(f"[BACKUP] Backup sent successfully: {filename}")
    except Exception as e:
        log.error(f"[BACKUP] Backup failed: {e}")

async def create_user_backup(app, uid: int, chat_id: int):
    try:
        log.info(f"[USER_BACKUP] Creating backup for user {uid}")
        subs = await db.get_subs(uid)
        settings = await db.get_all_conf(uid)
        backup_data = {
            "user_id": uid,
            "backup_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "subscriptions": subs,
            "settings": settings,
        }
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"user_backup_{uid}_{timestamp}.json"
        filepath = Path(filename)
        with open(filepath, "w") as f:
            json.dump(backup_data, f, indent=2, default=str)
        await app.send_document(
            chat_id=chat_id,
            document=str(filepath),
            caption=(
                f"<b>📦 Your Data Backup</b>\n\n"
                f"<b>Subscriptions:</b> <code>{len(subs)}</code>\n"
                f"<b>Settings keys:</b> <code>{len(settings)}</code>"
            ),
        )
        filepath.unlink(missing_ok=True)
    except Exception as e:
        log.error(f"[USER_BACKUP] failed: {e}")
