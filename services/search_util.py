# Manhua-Bot - search relevance, de-duplication and history
#
# The aggregated search previously ranked results with a 4-level bucket
# (exact / prefix / contains / other), which left dozens of near-identical
# rows from different sources in arbitrary order and showed the same title
# many times over.
#
# This module adds:
#   * a real relevance score (token overlap + sequence similarity + source
#     trust + a small bonus for having a cover)
#   * cross-source de-duplication that keeps the best-scoring copy and
#     records which other sources carry the same title
#   * per-user recent-search history for one-tap repeat searches

from __future__ import annotations

import re
import time
import unicodedata
from difflib import SequenceMatcher
from typing import Any, Dict, Iterable, List, Optional

# Sources that tend to have complete, well-formed metadata rank slightly
# higher when scores are otherwise tied.
SOURCE_TRUST = {
    "comick": 1.0, "batoto": 0.95, "mangadex": 1.0, "weebcentral": 0.9,
    "asurascans": 0.9, "flamecomics": 0.85, "mangapark": 0.85,
    "allanime": 0.95, "pahe": 0.9, "hanime": 0.95, "hstream": 0.9,
}

_STOP = {"the", "a", "an", "of", "and", "wa", "no", "ga", "wo", "ni", "to"}


def normalize(text: Any) -> str:
    """Casefold, strip accents and punctuation for comparison."""
    s = unicodedata.normalize("NFKD", str(text or ""))
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.casefold()
    s = re.sub(r"[^\w\s]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def tokens(text: Any) -> List[str]:
    return [t for t in normalize(text).split() if t and t not in _STOP]


def score(query: str, title: str, source: str = "", has_cover: bool = False) -> float:
    """Relevance in roughly 0..1. Higher is better."""
    q, t = normalize(query), normalize(title)
    if not q or not t:
        return 0.0

    if t == q:
        base = 1.0
    elif t.startswith(q):
        base = 0.9
    elif q in t:
        # Prefer matches that cover more of the title.
        base = 0.75 * (len(q) / max(len(t), 1)) + 0.1
    else:
        qt, tt = set(tokens(query)), set(tokens(title))
        overlap = len(qt & tt) / len(qt) if qt else 0.0
        ratio = SequenceMatcher(None, q, t).ratio()
        base = 0.6 * overlap + 0.4 * ratio

    base += 0.03 * SOURCE_TRUST.get(str(source).lower(), 0.7)
    if has_cover:
        base += 0.01
    return round(min(base, 1.0), 4)


def dedupe(
    results: Iterable[Dict[str, Any]],
    query: str = "",
    threshold: float = 0.92,
) -> List[Dict[str, Any]]:
    """Collapse the same title appearing across sources.

    The best-scoring entry wins and gains `also_on` (other source names) plus
    `dupe_count`, so the UI can show "Naruto · 6 sources" instead of six rows.
    """
    scored: List[Dict[str, Any]] = []
    for r in results:
        if not isinstance(r, dict):
            continue
        item = dict(r)
        item["_score"] = score(
            query or item.get("title", ""),
            item.get("title", ""),
            item.get("src") or item.get("src_name") or "",
            bool(item.get("cover") or item.get("poster")),
        )
        scored.append(item)

    scored.sort(key=lambda x: x["_score"], reverse=True)

    kept: List[Dict[str, Any]] = []
    keys: List[str] = []
    for item in scored:
        norm = normalize(item.get("title", ""))
        if not norm:
            continue
        match_idx = None
        for idx, existing in enumerate(keys):
            if existing == norm or SequenceMatcher(None, existing, norm).ratio() >= threshold:
                match_idx = idx
                break
        if match_idx is None:
            item["also_on"] = []
            item["dupe_count"] = 1
            kept.append(item)
            keys.append(norm)
        else:
            winner = kept[match_idx]
            name = item.get("src_name") or item.get("src") or "?"
            if name not in winner["also_on"]:
                winner["also_on"].append(name)
                winner["dupe_count"] = len(winner["also_on"]) + 1
            # Fill gaps from the duplicate (e.g. a cover the winner lacked).
            for field in ("cover", "poster", "url", "id"):
                if not winner.get(field) and item.get(field):
                    winner[field] = item[field]
    return kept


def rank(results: Iterable[Dict[str, Any]], query: str) -> List[Dict[str, Any]]:
    """Score and sort without collapsing duplicates."""
    out = []
    for r in results:
        if not isinstance(r, dict):
            continue
        item = dict(r)
        item["_score"] = score(
            query, item.get("title", ""),
            item.get("src") or item.get("src_name") or "",
            bool(item.get("cover") or item.get("poster")),
        )
        out.append(item)
    out.sort(key=lambda x: x["_score"], reverse=True)
    return out


# ------------------------------------------------------------------ history
_HISTORY: Dict[int, List[Dict[str, Any]]] = {}
HISTORY_MAX = 10


def remember(user_id: int, query: str, hits: int = 0, kind: str = "manga") -> None:
    if not query or not query.strip():
        return
    entries = _HISTORY.setdefault(user_id, [])
    low = query.strip().casefold()
    for e in entries:
        if e["query"].casefold() == low:
            e.update(ts=time.time(), hits=hits, kind=kind)
            entries.sort(key=lambda x: x["ts"], reverse=True)
            return
    entries.insert(0, {"query": query.strip(), "ts": time.time(),
                       "hits": hits, "kind": kind})
    del entries[HISTORY_MAX:]


def history(user_id: int) -> List[Dict[str, Any]]:
    return list(_HISTORY.get(user_id, []))


def clear_history(user_id: int) -> int:
    n = len(_HISTORY.get(user_id, []))
    _HISTORY.pop(user_id, None)
    return n


def suggest(user_id: int, prefix: str, limit: int = 5) -> List[str]:
    p = normalize(prefix)
    if not p:
        return [e["query"] for e in history(user_id)[:limit]]
    return [e["query"] for e in history(user_id)
            if normalize(e["query"]).startswith(p)][:limit]
