# Manhua-Bot - download queue (Dra-Sama inspired)

from __future__ import annotations
import asyncio
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, List, Optional

@dataclass
class QueueItem:
    id: str
    user_id: int
    title: str
    chapter: str
    status: str = "pending"  # pending | running | done | failed
    created_at: float = field(default_factory=time.time)
    error: Optional[str] = None

class DownloadQueue:
    def __init__(self):
        self._items: Dict[str, QueueItem] = {}
        self._order: Deque[str] = deque()
        self._lock = asyncio.Lock()
        self._counter = 0

    def _next_id(self) -> str:
        self._counter += 1
        return f"q{self._counter}"

    async def add(self, user_id: int, title: str, chapter: str) -> QueueItem:
        async with self._lock:
            qid = self._next_id()
            item = QueueItem(id=qid, user_id=user_id, title=title, chapter=chapter)
            self._items[qid] = item
            self._order.append(qid)
            return item

    async def set_status(self, qid: str, status: str, error: str = None):
        async with self._lock:
            it = self._items.get(qid)
            if it:
                it.status = status
                if error:
                    it.error = error

    async def user_items(self, user_id: int) -> List[QueueItem]:
        async with self._lock:
            return [i for i in self._items.values() if i.user_id == user_id]

    async def all_pending(self) -> List[QueueItem]:
        async with self._lock:
            return [self._items[i] for i in self._order if self._items[i].status == "pending"]

    async def clear_user(self, user_id: int) -> int:
        async with self._lock:
            ids = [i for i, v in self._items.items() if v.user_id == user_id and v.status in ("pending", "failed")]
            for i in ids:
                self._items.pop(i, None)
            self._order = deque([x for x in self._order if x in self._items])
            return len(ids)

    async def clear_all_pending(self) -> int:
        async with self._lock:
            ids = [i for i, v in self._items.items() if v.status == "pending"]
            for i in ids:
                self._items.pop(i, None)
            self._order = deque([x for x in self._order if x in self._items])
            return len(ids)

dl_queue = DownloadQueue()
