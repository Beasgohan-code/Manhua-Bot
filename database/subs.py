# Manhua-Bot - Subscriptions mixin (PostgreSQL)
# Same public API as original, JSONB document storage for flexibility

import random
import string
import json

class SubsMixin:
    async def _next_sid(self, uid):
        async with self.pool.acquire() as conn:
            while True:
                prefix = "".join(random.choices(string.ascii_uppercase, k=4))
                digits = "".join(random.choices(string.digits, k=6))
                sid = f"{prefix}{digits}"
                exists = await conn.fetchval("SELECT 1 FROM subs WHERE sid = $1", sid)
                if not exists:
                    return sid

    async def add_sub(self, uid, d):
        d = dict(d)
        d['uid'] = uid
        async with self.pool.acquire() as conn:
            # check existing by title + cid
            rows = await conn.fetch(
                "SELECT sid, data FROM subs WHERE uid = $1", int(uid)
            )
            for row in rows:
                data = row["data"] or {}
                if data.get("title") == d.get("title") and data.get("cid") == d.get("cid"):
                    sid = row["sid"]
                    if "sources" not in data:
                        data["sources"] = [{"mid": data.get("mid"), "src": data.get("src")}]
                        await conn.execute(
                            "UPDATE subs SET data = $1::jsonb WHERE sid = $2",
                            json.dumps(data), sid
                        )
                    return sid

            sid = await self._next_sid(uid)
            d['sid'] = sid
            d['sources'] = [{"mid": d.get('mid'), "src": d.get('src')}]
            await conn.execute(
                "INSERT INTO subs (sid, uid, data) VALUES ($1, $2, $3::jsonb)",
                sid, int(uid), json.dumps(d)
            )
            return sid

    async def add_source_to_sub(self, uid, sid, mid, src, last=None, lurl=None):
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT data FROM subs WHERE uid = $1 AND sid = $2", int(uid), sid
            )
            if not row:
                return
            data = dict(row["data"] or {})
            sources = data.get("sources") or []
            source_data = {"mid": mid, "src": src}
            if last:
                source_data["last"] = last
            if lurl:
                source_data["lurl"] = lurl
            # avoid exact duplicates
            if not any(s.get("mid") == mid and s.get("src") == src for s in sources):
                sources.append(source_data)
            data["sources"] = sources
            await conn.execute(
                "UPDATE subs SET data = $1::jsonb WHERE uid = $2 AND sid = $3",
                json.dumps(data), int(uid), sid
            )

    async def get_subs(self, uid=None):
        async with self.pool.acquire() as conn:
            if uid:
                rows = await conn.fetch("SELECT data FROM subs WHERE uid = $1", int(uid))
            else:
                rows = await conn.fetch("SELECT data FROM subs")
            return [dict(r["data"] or {}) for r in rows]

    async def get_user_channels(self, uid):
        subs = await self.get_subs(uid)
        return list({s.get("cid") for s in subs if s.get("cid") is not None})

    async def get_sub(self, uid, sid):
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT data FROM subs WHERE uid = $1 AND sid = $2", int(uid), sid
            )
            return dict(row["data"]) if row else None

    async def del_sub(self, uid, sid):
        async with self.pool.acquire() as conn:
            result = await conn.execute(
                "DELETE FROM subs WHERE uid = $1 AND sid = $2", int(uid), sid
            )
            return result

    async def up_sub_promos(self, uid, sid, pids):
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT data FROM subs WHERE uid = $1 AND sid = $2", int(uid), sid
            )
            if not row:
                return
            data = dict(row["data"] or {})
            data["last_promo_ids"] = pids
            await conn.execute(
                "UPDATE subs SET data = $1::jsonb WHERE uid = $2 AND sid = $3",
                json.dumps(data), int(uid), sid
            )

    async def up_sub(self, uid, sid, chap_num, chap_title, url):
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT data FROM subs WHERE uid = $1 AND sid = $2", int(uid), sid
            )
            if not row:
                return
            data = dict(row["data"] or {})
            data["last"] = chap_num
            data["last_title"] = chap_title
            data["lurl"] = url
            await conn.execute(
                "UPDATE subs SET data = $1::jsonb WHERE uid = $2 AND sid = $3",
                json.dumps(data), int(uid), sid
            )

    async def up_source(self, uid, sid, src_name, chap_num, chap_title, url):
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT data FROM subs WHERE uid = $1 AND sid = $2", int(uid), sid
            )
            if not row:
                return
            data = dict(row["data"] or {})
            sources = data.get("sources") or []
            for s in sources:
                if s.get("src") == src_name:
                    s["last"] = chap_num
                    s["last_title"] = chap_title
                    s["lurl"] = url
                    break
            data["sources"] = sources
            await conn.execute(
                "UPDATE subs SET data = $1::jsonb WHERE uid = $2 AND sid = $3",
                json.dumps(data), int(uid), sid
            )

    async def set_sub_thumb(self, uid, sid, b64_data):
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT data FROM subs WHERE uid = $1 AND sid = $2", int(uid), sid
            )
            if not row:
                return
            data = dict(row["data"] or {})
            data["thumb_b64"] = b64_data
            await conn.execute(
                "UPDATE subs SET data = $1::jsonb WHERE uid = $2 AND sid = $3",
                json.dumps(data), int(uid), sid
            )

    async def clear_sub_thumb(self, uid, sid):
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT data FROM subs WHERE uid = $1 AND sid = $2", int(uid), sid
            )
            if not row:
                return
            data = dict(row["data"] or {})
            data.pop("thumb_b64", None)
            await conn.execute(
                "UPDATE subs SET data = $1::jsonb WHERE uid = $2 AND sid = $3",
                json.dumps(data), int(uid), sid
            )

    async def delete_all_for_user(self, uid):
        async with self.pool.acquire() as conn:
            await conn.execute("DELETE FROM subs WHERE uid = $1", int(uid))
