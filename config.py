# Manhua-Bot Configuration
# Enhanced fork with PostgreSQL backend

import os
from dotenv import load_dotenv
load_dotenv()

class Config:
    API_ID = int(os.getenv("API_ID", "0"))
    API_HASH = os.getenv("API_HASH", "")
    BOT_TOKEN = os.getenv("BOT_TOKEN", "")
    # PostgreSQL connection string
    # Example: postgresql://user:pass@localhost:5432/manhua_bot
    DATABASE_URL = os.getenv("DATABASE_URL", os.getenv("MONGO_DB_URI", ""))
    OWNER_ID = [int(x) for x in os.getenv("OWNER_ID", "").split()] if os.getenv("OWNER_ID") else []
    LOG_GROUP = int(os.getenv("LOG_GROUP", "0") or "0")
    MAX_IMAGE_SIZE = 10 * 1024 * 1024
    MAX_PDF_SIZE = 50 * 1024 * 1024
    DOWNLOAD_DIR = "downloads"
    MAX_IMAGE_WIDTH = 2500
    JPEG_QUALITY = 100
    ENABLE_WEBP = True
    FSUB_CHANNELS = []
    _fsub = os.getenv("FSUB_CHANNELS", "")
    if _fsub:
        for x in _fsub.split():
            try:
                FSUB_CHANNELS.append(int(x))
            except ValueError:
                FSUB_CHANNELS.append(x)
    DEFAULT_FTYPE = os.getenv('DEFAULT_FTYPE', 'pdf')  # pdf | cbz | links
    # Optional global webhook (Discord or generic JSON)
    WEBHOOK_URL = os.getenv("WEBHOOK_URL", "")
    # Album mode: send small chapters as Telegram media groups (max pages)
    ALBUM_MAX_PAGES = int(os.getenv("ALBUM_MAX_PAGES", "10"))
    # Post a rate poll after chapter uploads
    ENABLE_RATE_POLL = os.getenv("ENABLE_RATE_POLL", "0") in ("1", "true", "True", "yes")
    IS_PRIVATE = os.getenv("IS_PRIVATE", "").lower() in ("1", "true", "yes")
    UPDATE_CHANNEL = os.getenv("UPDATE_CHANNEL", "")
