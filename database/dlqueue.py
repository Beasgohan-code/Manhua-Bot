# Manhua-Bot - download queue persistence (PostgreSQL)
#
# The queue lives in memory for speed; this mixin mirrors it to Postgres so a
# restart does not silently lose pending work. Writes are best-effort: if the
# database is unavailable the bot keeps running on the in-memory queue alone,
# because losing queue history must never take the bot down.

import logging
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)


class DLQueueMixin:
    async def dlq_upsert(self, item) -> bool:
        """Insert or update one queue item. Returns False if it could not write."""
        if not getattr(self, "pool", None):
            return False
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO dlqueue (
                        id, uid, title, chapter, status, source, kind,
                        progress, total, done_count, attempts, error,
                        created_at, started_at, finished_at, updated_at
                    ) VALUES (
                        $1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,
                        to_timestamp($13), 
                        CASE WHEN $14::double precision IS NULL THEN NULL
                             ELSE to_timestamp($14) END,
                        CASE WHEN $15::double precision IS NULL THEN NULL
                             ELSE to_timestamp($15) END,
                        to_timestamp($16)
                    )
                    ON CONFLICT (id) DO UPDATE SET
                        status = EXCLUDED.status,
                        progress = EXCLUDED.progress,
                        total = EXCLUDED.total,
                        done_count = EXCLUDED.done_count,
                        attempts = EXCLUDED.attempts,
                        error = EXCLUDED.error,
                        started_at = EXCLUDED.started_at,
                        finished_at = EXCLUDED.finished_at,
                        updated_at = EXCLUDED.updated_at
                    """,
                    item.id, int(item.user_id), str(item.title or ""),
                    str(item.chapter or ""), item.status, item.source or "",
                    item.kind or "manga", float(item.progress or 0),
                    int(item.total or 0), int(item.done_count or 0),
                    int(item.attempts or 0), item.error,
                    float(item.created_at),
                    float(item.started_at) if item.started_at else None,
                    float(item.finished_at) if item.finished_at else None,
                    float(item.updated_at),
                )
            return True
        except Exception as e:
            log.debug(f"[DLQ] upsert failed: {e}")
            return False

    async def dlq_load_active(self) -> List[Dict[str, Any]]:
        """Rows still unfinished — used to restore the queue after a restart."""
        if not getattr(self, "pool", None):
            return []
        try:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT id, uid, title, chapter, status, source, kind,
                           progress, total, done_count, attempts, error,
                           EXTRACT(EPOCH FROM created_at)  AS created_at,
                           EXTRACT(EPOCH FROM started_at)  AS started_at,
                           EXTRACT(EPOCH FROM finished_at) AS finished_at,
                           EXTRACT(EPOCH FROM updated_at)  AS updated_at
                    FROM dlqueue
                    WHERE status IN ('pending', 'running')
                    ORDER BY created_at
                    """
                )
            return [dict(r) for r in rows]
        except Exception as e:
            log.warning(f"[DLQ] load failed: {e}")
            return []

    async def dlq_delete(self, ids: List[str]) -> int:
        if not getattr(self, "pool", None) or not ids:
            return 0
        try:
            async with self.pool.acquire() as conn:
                res = await conn.execute(
                    "DELETE FROM dlqueue WHERE id = ANY($1::text[])", list(ids)
                )
            return int(res.split()[-1]) if res else 0
        except Exception as e:
            log.debug(f"[DLQ] delete failed: {e}")
            return 0

    async def dlq_prune(self, older_than_hours: int = 24) -> int:
        """Drop finished rows so the table cannot grow without bound."""
        if not getattr(self, "pool", None):
            return 0
        try:
            async with self.pool.acquire() as conn:
                res = await conn.execute(
                    """
                    DELETE FROM dlqueue
                    WHERE status NOT IN ('pending', 'running')
                      AND updated_at < NOW() - ($1 || ' hours')::interval
                    """,
                    str(int(older_than_hours)),
                )
            return int(res.split()[-1]) if res else 0
        except Exception as e:
            log.debug(f"[DLQ] prune failed: {e}")
            return 0

    async def dlq_mark_orphans(self, max_attempts: int = 3) -> int:
        """Requeue rows left 'running' by a crash.

        The user asked for these and nothing delivered them, so they go back
        to 'pending' rather than being written off — except after repeated
        attempts, which indicates the item itself is the problem.
        """
        if not getattr(self, "pool", None):
            return 0
        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE dlqueue
                       SET status = 'failed',
                           error = 'gave up after repeated interruptions',
                           finished_at = NOW(),
                           updated_at = NOW()
                     WHERE status = 'running' AND attempts >= $1
                    """,
                    int(max_attempts),
                )
                res = await conn.execute(
                    """
                    UPDATE dlqueue
                       SET status = 'pending',
                           error = 'interrupted by restart, requeued',
                           started_at = NULL,
                           updated_at = NOW()
                     WHERE status = 'running' AND attempts < $1
                    """,
                    int(max_attempts),
                )
            return int(res.split()[-1]) if res else 0
        except Exception as e:
            log.debug(f"[DLQ] orphan sweep failed: {e}")
            return 0
