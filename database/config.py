# Manhua-Bot - Config mixin (PostgreSQL)

import json

class ConfigMixin:
    async def set_conf(self, uid, key, value):
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO conf (uid, key, value)
                VALUES ($1, $2, $3::jsonb)
                ON CONFLICT (uid, key) DO UPDATE SET value = EXCLUDED.value
                """,
                int(uid), key, json.dumps(value, default=str)
            )

    async def get_conf(self, uid, key, default=None):
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT value FROM conf WHERE uid = $1 AND key = $2",
                int(uid), key
            )
            return row["value"] if row else default

    async def del_conf(self, uid, key):
        async with self.pool.acquire() as conn:
            await conn.execute(
                "DELETE FROM conf WHERE uid = $1 AND key = $2", int(uid), key
            )

    async def get_all_conf(self, uid):
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("SELECT key, value FROM conf WHERE uid = $1", int(uid))
            return {r["key"]: r["value"] for r in rows}

    # Aliases used across original plugins
    async def get_cfg(self, uid, key, default=None):
        return await self.get_conf(uid, key, default)

    async def set_cfg(self, uid, key, value):
        return await self.set_conf(uid, key, value)

    async def del_cfg(self, uid, key):
        return await self.del_conf(uid, key)

    async def delete_all_conf_for_user(self, uid):
        async with self.pool.acquire() as conn:
            await conn.execute("DELETE FROM conf WHERE uid = $1", int(uid))
