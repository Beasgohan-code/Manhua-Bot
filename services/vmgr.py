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
    async def search(self, query: str, allow_adult: bool = False, timeout: int = 25):
        targets = self.names(allow_adult)

        async def _one(src):
            try:
                res = await asyncio.wait_for(src.search(query), timeout=timeout)
                out = []
                for item in res or []:
                    item["src"] = self.key_of(src)
                    item["src_name"] = src.name
                    item["adult"] = src.adult
                    item["kind"] = "video"
                    out.append(item)
                return out
            except Exception as exc:
                log.debug(f"[VMGR] {src.sf} search failed: {exc}")
                return []

        results: List[Dict[str, Any]] = []
        for chunk in await asyncio.gather(*(_one(s) for s in targets)):
            results.extend(chunk)
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
