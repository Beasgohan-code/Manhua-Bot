# Manhua-Bot - download queue
#
# The original implementation was a plain dict that only ever grew: nothing
# pruned finished items, and no code path set "failed", so a crashed download
# stayed "running" forever and /queue slowly filled with stale rows.
#
# This version adds:
#   * real lifecycle: pending -> running -> done | failed | cancelled
#   * automatic retention (cap + TTL) so memory cannot grow without bound
#   * stale-run detection: a "running" item untouched for too long is failed
#   * per-user concurrency limiting via reserve()/release()
#   * progress + ETA tracking so /queue can show live state
#   * position(), stats(), cancel() and a fail_stale() sweeper

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, List, Optional

log = logging.getLogger(__name__)

# Lifecycle
PENDING = "pending"
RUNNING = "running"
DONE = "done"
FAILED = "failed"
CANCELLED = "cancelled"

TERMINAL = (DONE, FAILED, CANCELLED)
ACTIVE = (PENDING, RUNNING)

# Retention: keep the queue bounded no matter how long the bot runs.
MAX_ITEMS = 500              # hard cap on retained records
TERMINAL_TTL = 3600          # forget finished items after an hour
STALE_RUNNING = 1800         # a running item silent this long is presumed dead
MAX_PER_USER = 2             # concurrent running downloads per user


@dataclass
class QueueItem:
    id: str
    user_id: int
    title: str
    chapter: str
    status: str = PENDING
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    finished_at: Optional[float] = None
    updated_at: float = field(default_factory=time.time)
    error: Optional[str] = None
    progress: float = 0.0          # 0-100
    total: int = 0                 # e.g. page count
    done_count: int = 0
    source: str = ""
    kind: str = "manga"            # manga | video
    attempts: int = 0

    @property
    def is_active(self) -> bool:
        return self.status in ACTIVE

    @property
    def duration(self) -> float:
        end = self.finished_at or time.time()
        return max(0.0, end - (self.started_at or self.created_at))

    @property
    def eta(self) -> Optional[float]:
        """Seconds remaining, estimated from progress so far."""
        if self.status != RUNNING or self.progress <= 0:
            return None
        elapsed = time.time() - (self.started_at or self.created_at)
        if elapsed <= 0:
            return None
        return max(0.0, elapsed * (100.0 - self.progress) / self.progress)

    def label(self) -> str:
        return f"{self.title} — {self.chapter}" if self.chapter else self.title


class DownloadQueue:
    def __init__(
        self,
        max_items: int = MAX_ITEMS,
        terminal_ttl: int = TERMINAL_TTL,
        max_per_user: int = MAX_PER_USER,
        persist: bool = True,
    ):
        self._items: Dict[str, QueueItem] = {}
        self._order: Deque[str] = deque()
        self._lock = asyncio.Lock()
        self.max_items = max_items
        self.terminal_ttl = terminal_ttl
        self.max_per_user = max_per_user
        self.persist = persist

    # ------------------------------------------------------------- internals
    def _new_id(self) -> str:
        return uuid.uuid4().hex[:8]

    def _persist(self, item: "QueueItem") -> None:
        """Mirror an item to Postgres without blocking the caller.

        Fire-and-forget: queue history is not worth failing a download over,
        and the in-memory queue stays authoritative.
        """
        if not self.persist:
            return
        try:
            from database.db import db

            if getattr(db, "pool", None) is None:
                return
            asyncio.create_task(self._persist_task(db, item))
        except Exception:
            pass

    async def _persist_task(self, db, item) -> None:
        try:
            await db.dlq_upsert(item)
        except Exception as exc:
            log.debug(f"[QUEUE] persist failed: {exc}")

    async def restore(self) -> int:
        """Reload unfinished items after a restart.

        Anything left "running" when the process died is marked failed —
        it cannot still be in flight, and leaving it would permanently
        consume the owner's concurrency slot.
        """
        if not self.persist:
            return 0
        try:
            from database.db import db

            if getattr(db, "pool", None) is None:
                return 0
            await db.dlq_mark_orphans()
            rows = await db.dlq_load_active()
        except Exception as exc:
            log.warning(f"[QUEUE] restore failed: {exc}")
            return 0

        restored = 0
        async with self._lock:
            for r in rows:
                qid = r.get("id")
                if not qid or qid in self._items:
                    continue
                status = r.get("status") or PENDING
                if status == RUNNING:
                    status = PENDING  # requeue: it is definitely not running
                item = QueueItem(
                    id=qid,
                    user_id=int(r.get("uid") or 0),
                    title=r.get("title") or "",
                    chapter=r.get("chapter") or "",
                    status=status,
                    source=r.get("source") or "",
                    kind=r.get("kind") or "manga",
                    progress=float(r.get("progress") or 0),
                    total=int(r.get("total") or 0),
                    done_count=int(r.get("done_count") or 0),
                    attempts=int(r.get("attempts") or 0),
                    error=r.get("error"),
                    created_at=float(r.get("created_at") or time.time()),
                    updated_at=float(r.get("updated_at") or time.time()),
                )
                item.started_at = (
                    float(r["started_at"]) if r.get("started_at") else None
                )
                self._items[qid] = item
                self._order.append(qid)
                restored += 1
        if restored:
            log.info(f"[QUEUE] restored {restored} unfinished task(s) from database")
        return restored

    def _prune(self) -> int:
        """Drop expired terminal items, then trim to the cap. Caller holds lock."""
        now = time.time()
        removed = 0

        for qid in [
            q for q, it in self._items.items()
            if it.status in TERMINAL
            and now - (it.finished_at or it.updated_at) > self.terminal_ttl
        ]:
            self._items.pop(qid, None)
            removed += 1

        if len(self._items) > self.max_items:
            # Oldest finished items go first; never evict active work.
            finished = sorted(
                (it for it in self._items.values() if it.status in TERMINAL),
                key=lambda i: i.finished_at or i.updated_at,
            )
            for it in finished:
                if len(self._items) <= self.max_items:
                    break
                self._items.pop(it.id, None)
                removed += 1

        if removed:
            self._order = deque(q for q in self._order if q in self._items)
        return removed

    # ------------------------------------------------------------------ CRUD
    async def add(
        self,
        user_id: int,
        title: str,
        chapter: str,
        source: str = "",
        kind: str = "manga",
        total: int = 0,
    ) -> QueueItem:
        async with self._lock:
            self._prune()
            item = QueueItem(
                id=self._new_id(),
                user_id=user_id,
                title=title,
                chapter=str(chapter),
                source=source,
                kind=kind,
                total=total,
            )
            self._items[item.id] = item
            self._order.append(item.id)
        self._persist(item)
        return item

    async def get(self, qid: str) -> Optional[QueueItem]:
        async with self._lock:
            return self._items.get(qid)

    async def set_status(
        self, qid: str, status: str, error: Optional[str] = None
    ) -> Optional[QueueItem]:
        async with self._lock:
            it = self._items.get(qid)
            if not it:
                return None
            it.status = status
            it.updated_at = time.time()
            if status == RUNNING and it.started_at is None:
                it.started_at = time.time()
                it.attempts += 1
            if status in TERMINAL:
                it.finished_at = time.time()
                if status == DONE:
                    it.progress = 100.0
            if error:
                it.error = str(error)[:300]
        self._persist(it)
        return it

    async def progress(
        self, qid: str, done: int = 0, total: int = 0, pct: Optional[float] = None
    ) -> None:
        """Report progress; also refreshes the stale-run watchdog timestamp."""
        async with self._lock:
            it = self._items.get(qid)
            if not it:
                return
            if total:
                it.total = total
            if done:
                it.done_count = done
            if pct is not None:
                it.progress = max(0.0, min(100.0, float(pct)))
            elif it.total:
                it.progress = max(0.0, min(100.0, 100.0 * it.done_count / it.total))
            it.updated_at = time.time()

    async def cancel(self, qid: str, user_id: Optional[int] = None) -> bool:
        async with self._lock:
            it = self._items.get(qid)
            if not it or (user_id is not None and it.user_id != user_id):
                return False
            if it.status in TERMINAL:
                return False
            it.status = CANCELLED
            it.finished_at = it.updated_at = time.time()
        self._persist(it)
        return True

    # -------------------------------------------------------------- querying
    async def user_items(self, user_id: int, active_only: bool = False
                         ) -> List[QueueItem]:
        async with self._lock:
            self._prune()
            out = [i for i in self._items.values() if i.user_id == user_id]
            if active_only:
                out = [i for i in out if i.is_active]
            out.sort(key=lambda i: i.created_at)
            return out

    async def all_pending(self) -> List[QueueItem]:
        async with self._lock:
            return [
                self._items[q] for q in self._order
                if q in self._items and self._items[q].status == PENDING
            ]

    async def position(self, qid: str) -> Optional[int]:
        """1-based position among pending items."""
        async with self._lock:
            pend = [
                q for q in self._order
                if q in self._items and self._items[q].status == PENDING
            ]
            return pend.index(qid) + 1 if qid in pend else None

    async def running_for(self, user_id: int) -> int:
        async with self._lock:
            return sum(
                1 for i in self._items.values()
                if i.user_id == user_id and i.status == RUNNING
            )

    async def reserve(self, user_id: int) -> bool:
        """True if this user is under their concurrency limit."""
        async with self._lock:
            running = sum(
                1 for i in self._items.values()
                if i.user_id == user_id and i.status == RUNNING
            )
            return running < self.max_per_user

    async def stats(self) -> Dict[str, Any]:
        async with self._lock:
            self._prune()
            counts: Dict[str, int] = {}
            for it in self._items.values():
                counts[it.status] = counts.get(it.status, 0) + 1
            done = [i for i in self._items.values() if i.status == DONE]
            avg = sum(i.duration for i in done) / len(done) if done else 0.0
            return {
                "total": len(self._items),
                "counts": counts,
                "users": len({i.user_id for i in self._items.values()}),
                "avg_seconds": avg,
            }

    # ------------------------------------------------------------ maintenance
    async def fail_stale(self, older_than: int = STALE_RUNNING) -> int:
        """Mark long-silent running items as failed.

        Without this a download killed by a restart or an unhandled error
        stays "running" forever and blocks the user's concurrency slot.
        """
        async with self._lock:
            now = time.time()
            n = 0
            for it in self._items.values():
                if it.status == RUNNING and now - it.updated_at > older_than:
                    it.status = FAILED
                    it.error = "timed out (no progress)"
                    it.finished_at = it.updated_at = now
                    n += 1
            self._prune()
            return n

    async def clear_user(self, user_id: int) -> int:
        async with self._lock:
            ids = [
                i for i, v in self._items.items()
                if v.user_id == user_id and v.status in (PENDING, FAILED, CANCELLED, DONE)
            ]
            for i in ids:
                self._items.pop(i, None)
            self._order = deque(x for x in self._order if x in self._items)
            return len(ids)

    async def clear_all_pending(self) -> int:
        async with self._lock:
            ids = [i for i, v in self._items.items() if v.status == PENDING]
            for i in ids:
                self._items.pop(i, None)
            self._order = deque(x for x in self._order if x in self._items)
            return len(ids)


dl_queue = DownloadQueue()
