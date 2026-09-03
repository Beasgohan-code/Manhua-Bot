# Manhua-Bot
# Advanced Telegram Manhua / Manga chapter tracker
# PostgreSQL backend • Enhanced formatting • Extra sources

from pyrogram import Client, idle
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from config import Config
import logging

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

app = Client(
    "manhua_bot",
    api_id=Config.API_ID,
    api_hash=Config.API_HASH,
    bot_token=Config.BOT_TOKEN,
    plugins=dict(root="plugins")
)
sched = AsyncIOScheduler()

async def main():
    async with app:
        log.info("Manhua-Bot started!")
        from database.db import db
        await db.connect()
        await db.cleanup_indexes()

        async def cache_cleanup():
            try:
                result = await db.clear_all_cache()
                log.info(f"[CACHE] Cleared {result.deleted_count} entries")
            except Exception as e:
                log.error(f"[CACHE] Cleanup error: {e}")

        async def storage_cleanup():
            import shutil
            import os
            import gc
            try:
                if os.path.exists(Config.DOWNLOAD_DIR):
                    for filename in os.listdir(Config.DOWNLOAD_DIR):
                        file_path = os.path.join(Config.DOWNLOAD_DIR, filename)
                        try:
                            if os.path.isfile(file_path) or os.path.islink(file_path):
                                os.unlink(file_path)
                            elif os.path.isdir(file_path):
                                shutil.rmtree(file_path)
                        except Exception as e:
                            log.error(f"Failed to delete {file_path}: {e}")
                if os.path.exists("temp"):
                    for filename in os.listdir("temp"):
                        file_path = os.path.join("temp", filename)
                        try:
                            if os.path.isdir(file_path):
                                shutil.rmtree(file_path)
                            else:
                                os.unlink(file_path)
                        except Exception:
                            pass
                gc.collect()
                log.info("[STORAGE] Cleanup complete")
            except Exception as e:
                log.error(f"[STORAGE] Cleanup error: {e}")

        async def memory_cleanup():
            import gc
            gc.collect(0)
            gc.collect(1)
            gc.collect(2)
            log.info("[MEM] Memory cleanup and garbage collection complete")

        async def process_persistent_tasks():
            try:
                from plugins.broadcast import delete_broadcast_msgs
                tasks = await db.get_tasks()
                for task in tasks:
                    if task['name'] == "broadcast_delete":
                        await delete_broadcast_msgs(app, task['data'])
                    await db.del_task(task['_id'])
            except Exception as e:
                log.error(f"[TASKS] Process error: {e}")

        from plugins.chan_listen import init_listener, chan_listener, start_listener
        init_listener(app)
        app.add_handler(chan_listener)
        await start_listener()
        log.info("Channel listener ready")

        # Report video engine + hanime-plugin availability at boot so a
        # missing ffmpeg/extractor shows up in logs, not mid-download.
        try:
            from services.hplugin import log_status
            from services import vengine
            log_status()
            log.info(f"[VENGINE] {vengine.engine_status()}")
        except Exception as e:
            log.warning(f"[VENGINE] status check failed: {e}")

        from plugins.check.scheduler import check_job
        from services.backup import create_db_backup

        sched.add_job(check_job, "interval", minutes=5, args=[app])
        sched.add_job(cache_cleanup, "interval", minutes=10)
        sched.add_job(storage_cleanup, "interval", minutes=10)
        sched.add_job(memory_cleanup, "interval", minutes=5)
        sched.add_job(create_db_backup, "interval", hours=24, args=[app])
        sched.add_job(process_persistent_tasks, "interval", minutes=1)
        sched.start()
        log.info("Scheduler started (check: 5m, cache: 10m, storage: 10m, memory: 5m, backup: 24h)")
        try:
            await idle()
        finally:
            # Release the aiogram HTTP session used for native rich messages.
            try:
                from utils.richmsg import close_rich

                await close_rich()
            except Exception:
                pass

if __name__ == "__main__":
    import asyncio
    asyncio.get_event_loop().run_until_complete(main())
