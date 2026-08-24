# Manhua-Bot - Cache mixin (PostgreSQL)

import json
from datetime import datetime, timezone, timedelta

class CacheMixin:
    async def set_cache(self, key, value, ttl=3600):
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO cache (key, value, ts)
                VALUES ($1, $2::jsonb, NOW())
                ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, ts = NOW()
                """,
                key, json.dumps(value, default=str)
            )

    async def get_cache(self, key):
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT value, ts FROM cache WHERE key = $1", key
            )
            if not row:
                return None
            # simple TTL check (1 hour default)
            age = datetime.now(timezone.utc) - row["ts"]
            if age > timedelta(hours=1):
                await conn.execute("DELETE FROM cache WHERE key = $1", key)
                return None
            return row["value"]

    async def del_cache(self, key):
        async with self.pool.acquire() as conn:
            await conn.execute("DELETE FROM cache WHERE key = $1", key)

    async def clear_all_cache(self):
        async with self.pool.acquire() as conn:
            result = await conn.execute("DELETE FROM cache")
            # fake mongo-like result
            class R:
                def __init__(self, n):
                    self.deleted_count = n
            try:
                n = int(result.split()[-1])
            except Exception:
                n = 0
            return R(n)
