#!/usr/bin/env python3
"""Live selector verification — hits each real site once and reports health.

This is the check the offline harnesses cannot do. `audit.py` proves nothing
crashes on malformed input and `extract_test.py` proves nothing crashes on
well-formed input, but neither can tell you whether a site redesigned its
HTML last week and every selector now misses.

Run this on a machine with real network access:

    python tools/live_check.py                  # all manga sources
    python tools/live_check.py --video          # video sources too
    python tools/live_check.py -s comick asura  # only these
    python tools/live_check.py --deep           # also fetch chapters + pages
    python tools/live_check.py --json report.json

Exit code is non-zero when any source is BROKEN, so it works in CI/cron.

Nothing here mutates the repo; it only performs GET/POST against the sites
each scraper already targets.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import pathlib
import sys
import time
import warnings
from typing import Any, Dict, List, Optional

warnings.filterwarnings("ignore")
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

GREEN, RED, YELLOW, DIM, RESET = (
    "\033[92m", "\033[91m", "\033[93m", "\033[2m", "\033[0m",
)

# Queries likely to match on almost any manga/anime site.
DEFAULT_QUERIES = ["one piece", "naruto", "solo leveling"]
VIDEO_QUERIES = ["overflow", "love", "school"]

OK = "OK"            # returned usable results
EMPTY = "EMPTY"      # reachable but zero results (possible selector drift)
BROKEN = "BROKEN"    # raised an exception
TIMEOUT = "TIMEOUT"
BLOCKED = "BLOCKED"  # network refused / DNS / TLS


def classify_error(exc: Exception) -> str:
    text = f"{type(exc).__name__}: {exc}".lower()
    net = (
        "ssl", "dns", "nameresolution", "connection", "refused", "unreachable",
        "timed out", "timeout", "certificate", "proxy", "getaddrinfo",
    )
    if any(k in text for k in net):
        return BLOCKED
    return BROKEN


async def probe_source(
    name: str,
    src: Any,
    queries: List[str],
    timeout: float,
    deep: bool,
) -> Dict[str, Any]:
    """Try each query until one yields results."""
    row: Dict[str, Any] = {
        "source": name,
        "code": getattr(src, "sf", "?"),
        "url": getattr(src, "url", ""),
        "status": EMPTY,
        "results": 0,
        "query": None,
        "sample": None,
        "error": None,
        "seconds": 0.0,
        "chapters": None,
        "pages": None,
    }
    started = time.time()

    for q in queries:
        try:
            res = await asyncio.wait_for(src.search(q), timeout=timeout)
        except asyncio.TimeoutError:
            row["status"] = TIMEOUT
            row["error"] = f"no response in {timeout}s"
            continue
        except Exception as exc:
            row["status"] = classify_error(exc)
            row["error"] = f"{type(exc).__name__}: {exc}"[:200]
            continue

        if res:
            first = res[0] if isinstance(res, (list, tuple)) else None
            title = url = None
            if isinstance(first, dict):
                title = first.get("title") or first.get("name")
                url = first.get("url") or first.get("link")
            row.update(
                status=OK if (title and url) else EMPTY,
                results=len(res),
                query=q,
                sample=str(title)[:60] if title else None,
            )
            if not title or not url:
                row["error"] = "results missing title/url"
            if row["status"] == OK:
                break
        else:
            row["status"] = EMPTY
            row["query"] = q

    # Optional deeper walk: chapters, then pages of the first chapter.
    if deep and row["status"] == OK:
        try:
            from sources.compat import resolve_series, resolve_pages

            res = await asyncio.wait_for(src.search(row["query"]), timeout=timeout)
            ident = res[0].get("url") or res[0].get("id")
            series = await asyncio.wait_for(
                resolve_series(src, ident, timeout=int(timeout)), timeout=timeout * 2
            )
            chaps = (series or {}).get("chapters") or []
            row["chapters"] = len(chaps)
            if chaps:
                pages = await asyncio.wait_for(
                    resolve_pages(src, chaps[0], series, timeout=int(timeout)),
                    timeout=timeout * 2,
                )
                row["pages"] = len(pages or [])
                if not pages:
                    row["error"] = (row["error"] or "") + " | chapter yielded no pages"
            else:
                row["error"] = (row["error"] or "") + " | series yielded no chapters"
        except Exception as exc:
            row["error"] = (row["error"] or "") + f" | deep: {type(exc).__name__}"

    row["seconds"] = round(time.time() - started, 2)
    return row


def colour(status: str) -> str:
    return {
        OK: f"{GREEN}OK{RESET}",
        EMPTY: f"{YELLOW}EMPTY{RESET}",
        BROKEN: f"{RED}BROKEN{RESET}",
        TIMEOUT: f"{YELLOW}TIMEOUT{RESET}",
        BLOCKED: f"{DIM}BLOCKED{RESET}",
    }.get(status, status)


async def main() -> int:
    ap = argparse.ArgumentParser(description="Live source health check")
    ap.add_argument("-s", "--sources", nargs="*", help="only these source codes/names")
    ap.add_argument("-t", "--timeout", type=float, default=25.0)
    ap.add_argument("-c", "--concurrency", type=int, default=6)
    ap.add_argument("-q", "--query", action="append", help="custom search term(s)")
    ap.add_argument("--video", action="store_true", help="include video sources")
    ap.add_argument("--only-video", action="store_true")
    ap.add_argument("--deep", action="store_true", help="also fetch chapters + pages")
    ap.add_argument("--json", help="write a JSON report here")
    args = ap.parse_args()

    try:
        from loguru import logger

        logger.remove()
    except Exception:
        pass
    import logging

    logging.disable(logging.WARNING)

    from services.mgr import mgr
    from services.vmgr import vmgr

    targets: List[tuple] = []
    if not args.only_video:
        targets += list(mgr.srcs.items())
    if args.video or args.only_video:
        targets += [(f"[video] {n}", s) for n, s in vmgr.srcs.items()]

    if args.sources:
        wanted = {w.lower() for w in args.sources}
        targets = [
            (n, s) for n, s in targets
            if n.lower() in wanted
            or n.lower().replace("webs", "") in wanted
            or str(getattr(s, "sf", "")).lower() in wanted
        ]
        if not targets:
            print(f"{RED}No sources matched {args.sources}{RESET}")
            return 2

    queries = args.query or DEFAULT_QUERIES
    print(f"\033[1mLive check\033[0m — {len(targets)} source(s), "
          f"queries={queries}, timeout={args.timeout}s"
          + (", deep" if args.deep else ""))
    print(f"{DIM}Hitting real sites; this takes a while.{RESET}\n")

    sem = asyncio.Semaphore(max(1, args.concurrency))
    rows: List[Dict[str, Any]] = []

    async def run(name, src):
        qs = VIDEO_QUERIES if name.startswith("[video]") else queries
        async with sem:
            row = await probe_source(name, src, qs, args.timeout, args.deep)
            rows.append(row)
            extra = ""
            if row["status"] == OK:
                extra = f"{row['results']:>3} hits  {DIM}{row['sample'] or ''}{RESET}"
                if row["chapters"] is not None:
                    extra += f"  {DIM}ch={row['chapters']} pg={row['pages']}{RESET}"
            elif row["error"]:
                extra = f"{DIM}{row['error'][:70]}{RESET}"
            print(f"  {colour(row['status']):<18} {name:<26} "
                  f"{row['seconds']:>5.1f}s  {extra}")

    await asyncio.gather(*(run(n, s) for n, s in targets))

    by = {}
    for r in rows:
        by.setdefault(r["status"], []).append(r["source"])

    print("\n\033[1mSummary\033[0m")
    for st in (OK, EMPTY, TIMEOUT, BROKEN, BLOCKED):
        if st in by:
            print(f"  {colour(st):<18} {len(by[st]):>3}")

    if by.get(BROKEN):
        print(f"\n{RED}Broken (raised an exception — real bugs):{RESET}")
        for r in rows:
            if r["status"] == BROKEN:
                print(f"  · {r['source']}: {r['error']}")
    if by.get(EMPTY):
        print(f"\n{YELLOW}Empty (reachable but no results — likely selector "
              f"drift):{RESET}")
        for n in by[EMPTY]:
            print(f"  · {n}")
    if by.get(BLOCKED):
        print(f"\n{DIM}Blocked (network/DNS/TLS — environment, not the "
              f"scraper):{RESET}")
        print("  " + ", ".join(by[BLOCKED][:20])
              + (" …" if len(by[BLOCKED]) > 20 else ""))

    if args.json:
        pathlib.Path(args.json).write_text(
            json.dumps(
                {"generated": time.time(), "rows": sorted(rows, key=lambda r: r["source"])},
                indent=2,
            )
        )
        print(f"\nJSON report → {args.json}")

    # Only genuine scraper faults fail the run; a blocked network does not.
    return 1 if by.get(BROKEN) else 0


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    except KeyboardInterrupt:
        sys.exit(130)
