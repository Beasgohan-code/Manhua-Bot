# Manhua-Bot - PostgreSQL base (asyncpg)
# Core logic preserved, storage switched from MongoDB

import asyncpg
import json
import logging
from config import Config

log = logging.getLogger(__name__)

class BaseDB:
    def __init__(self):
        self.pool = None
        self._ready = False

    async def connect(self):
        if self.pool:
            return
        url = Config.DATABASE_URL
        if not url:
            raise ValueError("DATABASE_URL is not set in environment variables")
        try:
            self.pool = await asyncpg.create_pool(
                dsn=url,
                min_size=2,
                max_size=12,
                command_timeout=30,
            )
            await self._init_schema()
            self._ready = True
            log.info("[DB] PostgreSQL pool initialized successfully")
        except Exception as e:
            log.critical(f"[DB] Failed to initialize PostgreSQL: {e}")
            raise ConnectionError(f"Could not connect to PostgreSQL: {e}")

    async def close(self):
        if self.pool:
            await self.pool.close()
            self.pool = None
            self._ready = False

    async def _init_schema(self):
        async with self.pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id BIGINT PRIMARY KEY,
                    data JSONB DEFAULT '{}'::jsonb,
                    banned BOOLEAN DEFAULT FALSE,
                    ban_reason TEXT,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                );

                CREATE TABLE IF NOT EXISTS subs (
                    id SERIAL PRIMARY KEY,
                    sid TEXT UNIQUE NOT NULL,
                    uid BIGINT NOT NULL,
                    data JSONB NOT NULL DEFAULT '{}'::jsonb,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                );
                CREATE INDEX IF NOT EXISTS idx_subs_uid ON subs(uid);
                CREATE INDEX IF NOT EXISTS idx_subs_sid ON subs(sid);

                CREATE TABLE IF NOT EXISTS cache (
                    key TEXT PRIMARY KEY,
                    value JSONB NOT NULL,
                    ts TIMESTAMPTZ DEFAULT NOW()
                );
                CREATE INDEX IF NOT EXISTS idx_cache_ts ON cache(ts);

                CREATE TABLE IF NOT EXISTS conf (
                    uid BIGINT NOT NULL,
                    key TEXT NOT NULL,
                    value JSONB NOT NULL,
                    PRIMARY KEY (uid, key)
                );

                CREATE TABLE IF NOT EXISTS tasks (
                    id SERIAL PRIMARY KEY,
                    name TEXT NOT NULL,
                    data JSONB DEFAULT '{}'::jsonb,
                    status TEXT DEFAULT 'pending',
                    created_at TIMESTAMPTZ DEFAULT NOW()
                );
            """)

    async def cleanup_indexes(self):
        # Compatibility shim – schema is created on connect
        if not self.pool:
            await self.connect()
        log.info("[DB] Schema ready (PostgreSQL)")
