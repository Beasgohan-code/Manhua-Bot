# Manhua-Bot - Admin helpers (PostgreSQL)

class AdminMixin:
    async def get_stats(self):
        async with self.pool.acquire() as conn:
            users = await conn.fetchval("SELECT COUNT(*) FROM users") or 0
            subs = await conn.fetchval("SELECT COUNT(*) FROM subs") or 0
            banned = await conn.fetchval("SELECT COUNT(*) FROM users WHERE banned = TRUE") or 0
            return {
                "users": users,
                "subs": subs,
                "banned": banned,
            }

    async def db_stats(self):
        """Dashboard stats used by admin + start panels."""
        async with self.pool.acquire() as conn:
            users = await conn.fetchval("SELECT COUNT(*) FROM users") or 0
            subs = await conn.fetchval("SELECT COUNT(*) FROM subs") or 0
            banned = await conn.fetchval("SELECT COUNT(*) FROM users WHERE banned = TRUE") or 0
            conf = await conn.fetchval("SELECT COUNT(*) FROM conf") or 0
            cache = await conn.fetchval("SELECT COUNT(*) FROM cache") or 0
            tasks = await conn.fetchval("SELECT COUNT(*) FROM tasks WHERE status = 'pending'") or 0
        return {
            "users": users,
            "subs": subs,
            "subscriptions": subs,
            "banned": banned,
            "conf": conf,
            "cache": cache,
            "tasks": tasks,
            "engine": "postgresql",
        }

    async def clear_all_users(self):
        async with self.pool.acquire() as conn:
            result = await conn.execute("DELETE FROM users")
            try:
                n = int(result.split()[-1])
            except Exception:
                n = 0
            return {"deleted": n}

    async def clear_all_subs(self):
        async with self.pool.acquire() as conn:
            result = await conn.execute("DELETE FROM subs")
            try:
                n = int(result.split()[-1])
            except Exception:
                n = 0
            return {"deleted": n}

    async def clear_all_conf(self):
        async with self.pool.acquire() as conn:
            result = await conn.execute("DELETE FROM conf")
            try:
                n = int(result.split()[-1])
            except Exception:
                n = 0
            return {"deleted": n}

    async def clear_user_data(self, uid: int):
        uid = int(uid)
        async with self.pool.acquire() as conn:
            await conn.execute("DELETE FROM subs WHERE uid = $1", uid)
            await conn.execute("DELETE FROM conf WHERE uid = $1", uid)
            await conn.execute("DELETE FROM users WHERE id = $1", uid)
        return True
