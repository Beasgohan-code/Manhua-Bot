# Manhua-Bot - Users mixin (PostgreSQL)

class UsersMixin:
    async def add_usr(self, id):
        async with self.pool.acquire() as conn:
            exists = await conn.fetchval("SELECT 1 FROM users WHERE id = $1", int(id))
            if not exists:
                await conn.execute(
                    "INSERT INTO users (id, data) VALUES ($1, '{}'::jsonb)",
                    int(id)
                )
                return True
            return False

    async def get_usr(self, id):
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM users WHERE id = $1", int(id))
            if not row:
                return None
            d = dict(row["data"] or {})
            d["id"] = row["id"]
            d["banned"] = row["banned"]
            d["ban_reason"] = row["ban_reason"]
            return d

    async def get_all_users(self):
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("SELECT * FROM users")
            out = []
            for row in rows:
                d = dict(row["data"] or {})
                d["id"] = row["id"]
                d["banned"] = row["banned"]
                d["ban_reason"] = row["ban_reason"]
                out.append(d)
            return out

    async def tot_usrs(self):
        async with self.pool.acquire() as conn:
            return await conn.fetchval("SELECT COUNT(*) FROM users") or 0

    async def ban_usr(self, uid, reason="No reason"):
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO users (id, banned, ban_reason)
                VALUES ($1, TRUE, $2)
                ON CONFLICT (id) DO UPDATE SET banned = TRUE, ban_reason = $2
                """,
                int(uid), reason
            )

    async def unban_usr(self, uid):
        async with self.pool.acquire() as conn:
            await conn.execute(
                "UPDATE users SET banned = FALSE, ban_reason = NULL WHERE id = $1",
                int(uid)
            )

    async def is_banned(self, uid):
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT banned, ban_reason FROM users WHERE id = $1", int(uid)
            )
            if row and row["banned"]:
                return True, row["ban_reason"] or "No reason"
            return False, None

    async def get_banned_users(self):
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("SELECT * FROM users WHERE banned = TRUE")
            out = []
            for row in rows:
                d = dict(row["data"] or {})
                d["id"] = row["id"]
                d["banned"] = True
                d["ban_reason"] = row["ban_reason"]
                out.append(d)
            return out

    async def set_premium(self, uid, premium: bool = True, days: int = 30):
        import json
        from datetime import datetime, timezone, timedelta
        exp = None
        if premium and days:
            exp = (datetime.now(timezone.utc) + timedelta(days=int(days))).isoformat()
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("SELECT data FROM users WHERE id = $1", int(uid))
            data = dict(row["data"] or {}) if row else {}
            data["premium"] = bool(premium)
            data["premium_until"] = exp
            if row:
                await conn.execute(
                    "UPDATE users SET data = $2::jsonb WHERE id = $1",
                    int(uid), json.dumps(data),
                )
            else:
                await conn.execute(
                    "INSERT INTO users (id, data) VALUES ($1, $2::jsonb)",
                    int(uid), json.dumps(data),
                )

    async def is_premium(self, uid) -> bool:
        from datetime import datetime, timezone
        u = await self.get_usr(uid)
        if not u:
            return False
        if not u.get("premium"):
            return False
        until = u.get("premium_until")
        if not until:
            return True
        try:
            exp = datetime.fromisoformat(until)
            if exp.tzinfo is None:
                exp = exp.replace(tzinfo=timezone.utc)
            return datetime.now(timezone.utc) < exp
        except Exception:
            return bool(u.get("premium"))

    async def list_premium(self):
        users = await self.get_all_users()
        out = []
        for u in users:
            if u.get("premium"):
                out.append(u)
        return out

    async def del_expired_premium(self):
        from datetime import datetime, timezone
        import json
        users = await self.get_all_users()
        n = 0
        now = datetime.now(timezone.utc)
        for u in users:
            until = u.get("premium_until")
            if not u.get("premium") or not until:
                continue
            try:
                exp = datetime.fromisoformat(until)
                if exp.tzinfo is None:
                    exp = exp.replace(tzinfo=timezone.utc)
                if exp < now:
                    await self.set_premium(u["id"], False, 0)
                    n += 1
            except Exception:
                pass
        return n
