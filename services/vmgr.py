# Manhua-Bot - video source manager (mirrors services/mgr.py for videos)

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional

from sources.video import VIDEO_SOURCES

log = logging.getLogger(__name__)


class VideoMgr:
    def __init__(self):
        self.srcs: Dict[str, Any] = {}
        for cls in VIDEO_SOURCES:
            try:
                inst = cls()
                self.srcs[cls.__name__] = inst
            except Exception as exc:
                log.warning(f"[VMGR] failed to load {cls.__name__}: {exc}")
        log.info(f"[VMGR] Loaded {len(self.srcs)} video sources")

    # ---- lookup --------------------------------------------------------
    def get(self, name: str):
        if not name:
            return None
        if name in self.srcs:
            return self.srcs[name]
        low = name.lower().replace(" ", "").replace(".", "")
        for key, src in self.srcs.items():
            if low in (
                key.lower(),
                key.lower().replace("webs", ""),
                (src.sf or "").lower(),
                (src.name or "").lower().replace(" ", "").replace(".", ""),
            ):
                return src
        for key, src in self.srcs.items():
            if low in key.lower() or low in (src.name or "").lower().replace(" ", ""):
                return src
        return None

    def key_of(self, src) -> str:
        for key, val in self.srcs.items():
            if val is src:
                return key
        return getattr(src, "sf", "?")

    def names(self, allow_adult: bool = False) -> List[Any]:
        return [s for s in self.srcs.values() if allow_adult or not s.adult]

    # ---- search --------------------------------------------------------
    async def search(
        self,
        query: str,
        allow_adult: bool = False,
        timeout: int = 25,
        sources: Optional[List[str]] = None,
        on_progress=None,
    ):
        """Search every allowed source in parallel.

        `on_progress` (optional) is awaited as sources finish with a dict of
        live counters, so the UI can show "searching 14 sources…" style
        feedback instead of a frozen message.
        """
        targets = self.names(allow_adult)
        if sources:
            wanted = {s.lower() for s in sources}
            targets = [
                s for s in targets
                if s.sf.lower() in wanted or self.key_of(s).lower() in wanted
            ]

        total = len(targets)
        state = {"done": 0, "total": total, "found": 0, "ok": [], "failed": []}

        async def _one(src):
            name = getattr(src, "name", src.sf)
            try:
                res = await asyncio.wait_for(src.search(query), timeout=timeout)
                out = []
                for item in res or []:
                    item["src"] = self.key_of(src)
                    item["src_name"] = name
                    item["adult"] = src.adult
                    item["kind"] = "video"
                    out.append(item)
                if out:
                    state["ok"].append(name)
                state["found"] += len(out)
                return out
            except asyncio.TimeoutError:
                state["failed"].append(f"{name} (timeout)")
                return []
            except Exception as exc:
                log.debug(f"[VMGR] {src.sf} search failed: {exc}")
                state["failed"].append(name)
                return []
            finally:
                state["done"] += 1
                if on_progress:
                    try:
                        r = on_progress(dict(state))
                        if asyncio.iscoroutine(r):
                            await r
                    except Exception:
                        pass

        results: List[Dict[str, Any]] = []
        for chunk in await asyncio.gather(*(_one(s) for s in targets)):
            results.extend(chunk)

        # Exact/prefix title matches first, then by source order.
        q = (query or "").lower().strip()

        def rank(item):
            t = (item.get("title") or "").lower()
            if t == q:
                return 0
            if t.startswith(q):
                return 1
            if q in t:
                return 2
            return 3

        results.sort(key=rank)
        self.last_stats = state
        return results

    async def get_series(self, src_name: str, sid: str) -> Optional[Dict[str, Any]]:
        src = self.get(src_name)
        if not src:
            return None
        try:
            data = await asyncio.wait_for(src.get_series(sid), timeout=45)
            if data:
                data["src"] = self.key_of(src)
                data["src_name"] = src.name
            return data
        except Exception as exc:
            log.error(f"[VMGR] get_series {src_name}/{sid}: {exc}")
            return None

    async def get_episode(self, src_name: str, url: str) -> Optional[Dict[str, Any]]:
        src = self.get(src_name)
        if not src:
            return None
        try:
            return await asyncio.wait_for(src.get_episode(url), timeout=45)
        except Exception as exc:
            log.error(f"[VMGR] get_episode {src_name}: {exc}")
            return None


vmgr = VideoMgr()
