#!/usr/bin/env python3
"""Static health audit for Manhua-Bot.

Checks every scraper, plugin and service without touching the network, so it
runs anywhere:

  * all Python files compile
  * every plugin imports (this is how Pyrogram loads them)
  * each scraper exposes a usable interface (modern or legacy)
  * duplicate source codes / missing URLs
  * duplicate command names and callback-prefix collisions across plugins
  * UI helpers emit only Telegram-legal, balanced HTML

Usage:  python tools/audit.py [-v]
"""

from __future__ import annotations

import ast
import importlib
import pathlib
import re
import sys
import warnings
from collections import Counter, defaultdict

warnings.filterwarnings("ignore")
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

OK, WARN, FAIL = "\033[92m✓\033[0m", "\033[93m!\033[0m", "\033[91m✗\033[0m"
problems: list[str] = []
warnings_found: list[str] = []


def head(t: str) -> None:
    print(f"\n\033[1m── {t} ──\033[0m")


def check_compile() -> None:
    head("Syntax")
    bad = []
    files = [
        p for p in ROOT.rglob("*.py")
        if ".venv" not in p.parts and "__pycache__" not in p.parts
    ]
    for p in files:
        try:
            ast.parse(p.read_text(encoding="utf-8", errors="ignore"))
        except SyntaxError as e:
            bad.append(f"{p.relative_to(ROOT)}:{e.lineno} {e.msg}")
    if bad:
        problems.extend(bad)
        print(f"{FAIL} {len(bad)} file(s) failed to parse")
        for b in bad:
            print(f"    {b}")
    else:
        print(f"{OK} all {len(files)} python files parse")


def check_plugins() -> None:
    head("Plugin imports")
    import config

    config.Config.OWNER_ID = config.Config.OWNER_ID or [1]
    mods = sorted(
        str(p.relative_to(ROOT).with_suffix("")).replace("/", ".")
        for p in (ROOT / "plugins").rglob("*.py")
    )
    bad = []
    for m in mods:
        try:
            importlib.import_module(m)
        except Exception as e:
            bad.append(f"{m}: {type(e).__name__}: {e}")
    if bad:
        problems.extend(bad)
        print(f"{FAIL} {len(bad)}/{len(mods)} plugins failed to import")
        for b in bad:
            print(f"    {b}")
    else:
        print(f"{OK} all {len(mods)} plugins import")


def check_sources() -> None:
    head("Manga sources")
    from services.mgr import mgr
    from sources.compat import is_legacy

    total = len(mgr.srcs)
    modern = legacy = broken = 0
    for name, s in sorted(mgr.srcs.items()):
        has_search = callable(getattr(s, "search", None))
        if not has_search:
            problems.append(f"{name}: no search()")
            print(f"{FAIL} {name}: missing search()")
            broken += 1
            continue
        if callable(getattr(s, "get_manga", None)):
            modern += 1
        elif is_legacy(s):
            legacy += 1
        else:
            broken += 1
            problems.append(f"{name}: no usable chapter interface")
            print(f"{FAIL} {name}: no get_manga() and no get_chapters()")
    print(f"{OK} {total} sources: {modern} modern, {legacy} legacy, {broken} broken")

    codes = Counter(getattr(s, "sf", "?") for s in mgr.srcs.values())
    dups = {k: v for k, v in codes.items() if v > 1 and k != "?"}
    if dups:
        warnings_found.append(f"duplicate source codes: {dups}")
        owners = defaultdict(list)
        for n, s in mgr.srcs.items():
            if getattr(s, "sf", None) in dups:
                owners[s.sf].append(n)
        print(f"{WARN} duplicate source codes: {dict(owners)}")
    else:
        print(f"{OK} all source codes unique")

    nourl = [n for n, s in mgr.srcs.items() if not getattr(s, "url", None)]
    print(f"{OK} all sources define a url" if not nourl else f"{FAIL} no url: {nourl}")
    if nourl:
        problems.append(f"sources without url: {nourl}")


def check_video_sources() -> None:
    head("Video sources")
    from services.vmgr import vmgr

    required = [
        "HAnime.tv", "Hentai City", "Hentai Ocean", "Hentai.sh",
        "Hentaverse", "My Hentai Movie", "OnlyHentaiStuff", "WatchHentai",
    ]
    names = {s.name for s in vmgr.srcs.values()}
    missing = [r for r in required if r not in names]
    if missing:
        problems.append(f"missing requested video sites: {missing}")
        print(f"{FAIL} missing: {missing}")
    else:
        print(f"{OK} all 8 requested sites present")

    bad = [
        n for n, s in vmgr.srcs.items()
        if not (callable(getattr(s, "search", None))
                and callable(getattr(s, "get_series", None))
                and callable(getattr(s, "get_episode", None)))
    ]
    if bad:
        problems.append(f"incomplete video sources: {bad}")
        print(f"{FAIL} incomplete interface: {bad}")
    else:
        sfw = sum(1 for s in vmgr.srcs.values() if not s.adult)
        print(f"{OK} {len(vmgr.srcs)} video sources ({sfw} sfw / "
              f"{len(vmgr.srcs) - sfw} adult) implement the full interface")

    leaked = [s.sf for s in vmgr.names(False) if s.adult]
    if leaked:
        problems.append(f"adult sources leaking into SFW list: {leaked}")
        print(f"{FAIL} adult leak: {leaked}")
    else:
        print(f"{OK} adult gate holds (no adult source in SFW list)")


def check_resilience() -> None:
    """Feed every scraper malformed responses; a live site can return any of
    these and a raised exception kills the whole aggregated search."""
    head("Source resilience (offline fuzz)")
    import asyncio

    from services.mgr import mgr
    from services.vmgr import vmgr
    from sources.base import scraper as SC

    try:
        from loguru import logger as _L

        _L.remove()
    except Exception:
        pass

    payloads = [
        ("garbage html", "<html><body><div class='x'>nope</div></body></html>"),
        ("truncated", "<html><body><div class="),
        ("error page", "<html><h1>403 Forbidden</h1></html>"),
        ("empty json", {}),
        ("wrong json", {"unexpected": [1, 2, 3]}),
        ("json list", []),
        ("json string", "not json at all"),
        ("list of junk", [1, "x", None]),
        ("nested nulls", {"result": None, "data": None, "cover": None}),
        ("null", None),
    ]

    orig_get, orig_post = SC.Scraper.get, SC.Scraper.post
    failures = []

    async def run():
        for label, payload in payloads:
            async def fg(self, *a, _p=payload, **k):
                return _p if k.get("rjson") else (_p if isinstance(_p, str) else "")

            SC.Scraper.get = fg
            SC.Scraper.post = fg
            for name, src in mgr.srcs.items():
                try:
                    r = await asyncio.wait_for(src.search("test"), timeout=8)
                    if r is not None and not isinstance(r, (list, tuple)):
                        failures.append(f"{name}.search returned {type(r).__name__} on {label}")
                except Exception as e:
                    failures.append(f"{name}.search raised {type(e).__name__} on {label}")
            for name, src in vmgr.srcs.items():
                for meth, args in (
                    ("search", ("t",)), ("get_series", ("x",)),
                    ("get_episode", ("https://x/y",)),
                ):
                    try:
                        await asyncio.wait_for(getattr(src, meth)(*args), timeout=8)
                    except Exception as e:
                        failures.append(
                            f"{src.sf}.{meth} raised {type(e).__name__} on {label}"
                        )

    try:
        asyncio.run(run())
    finally:
        SC.Scraper.get, SC.Scraper.post = orig_get, orig_post

    checks = len(payloads) * (len(mgr.srcs) + len(vmgr.srcs) * 3)
    if failures:
        problems.extend(failures[:20])
        print(f"{FAIL} {len(failures)} failure(s) across {checks} checks")
        for f in failures[:12]:
            print(f"    {f}")
    else:
        print(f"{OK} all {checks} malformed-response checks passed "
              f"({len(mgr.srcs)} manga + {len(vmgr.srcs)} video sources)")


def check_queue() -> None:
    """Queue lifecycle, retention and concurrency guarantees."""
    head("Download queue")
    import asyncio
    import time as _t

    from services.queue import DownloadQueue, RUNNING, DONE, FAILED

    fails = []

    async def run():
        q = DownloadQueue(max_items=5, terminal_ttl=1, max_per_user=2)
        a = await q.add(1, "A", "1")
        b = await q.add(1, "B", "2")
        if await q.position(a.id) != 1:
            fails.append("position() wrong for first pending item")

        await q.set_status(a.id, RUNNING)
        await q.progress(a.id, done=5, total=20)
        if (await q.get(a.id)).progress != 25.0:
            fails.append("progress() did not compute percentage")

        await q.set_status(b.id, RUNNING)
        if await q.reserve(1):
            fails.append("reserve() ignored the per-user concurrency limit")

        (await q.get(b.id)).updated_at = _t.time() - 99999
        if await q.fail_stale(older_than=60) != 1:
            fails.append("fail_stale() did not recover a dead running item")
        if (await q.get(b.id)).status != FAILED:
            fails.append("stale item was not marked failed")
        if not await q.reserve(1):
            fails.append("concurrency slot not released after stale failure")

        if await q.cancel(a.id, user_id=999):
            fails.append("cancel() ignored ownership")

        # retention: active work must never be evicted
        q2 = DownloadQueue(max_items=3, terminal_ttl=99999)
        act = [await q2.add(1, f"R{i}", "1") for i in range(4)]
        for it in act:
            await q2.set_status(it.id, RUNNING)
        for i in range(30):
            it = await q2.add(1, f"D{i}", "1")
            await q2.set_status(it.id, DONE)
        if sum(1 for i in q2._items.values() if i.status == RUNNING) != 4:
            fails.append("retention evicted active items")
        if len(q2._items) > 3 + 4 + 1:
            fails.append(f"retention cap exceeded: {len(q2._items)} items")

    asyncio.run(run())
    if fails:
        problems.extend(fails)
        print(f"{FAIL} {len(fails)} queue problem(s)")
        for f in fails:
            print(f"    {f}")
    else:
        print(f"{OK} lifecycle, retention, stale recovery and concurrency all correct")

    # failures must actually be recorded by the download path
    src = (ROOT / "services" / "dl.py").read_text(encoding="utf-8", errors="ignore")
    if '"failed"' not in src:
        problems.append("services/dl.py never marks a queue item failed")
        print(f"{FAIL} dl.py has no failure path — items would stick on 'running'")
    else:
        print(f"{OK} dl.py records failures")


def check_search() -> None:
    """Relevance scoring and cross-source de-duplication."""
    head("Search quality")
    from services.search_util import dedupe, score, normalize

    fails = []
    if not score("naruto", "Naruto") > score("naruto", "Naruto Shippuden"):
        fails.append("exact title does not outrank a longer partial match")
    if not score("naruto", "Naruto Shippuden") > score("naruto", "Bleach"):
        fails.append("related title does not outrank an unrelated one")
    if normalize("NARUTO -ナルト-") != "naruto ナルト":
        fails.append("normalize() mishandles accents/punctuation")

    merged = dedupe(
        [
            {"title": "Naruto", "src": "comick", "src_name": "Comick"},
            {"title": "naruto", "src": "batoto", "src_name": "Batoto",
             "cover": "http://c.jpg"},
            {"title": "NARUTO", "src": "asura", "src_name": "Asura"},
            {"title": "Bleach", "src": "x", "src_name": "X"},
        ],
        "naruto",
    )
    if len(merged) != 2:
        fails.append(f"dedupe kept {len(merged)} rows, expected 2")
    else:
        top = merged[0]
        if top["dupe_count"] != 3:
            fails.append("dedupe lost duplicate source attribution")
        if not top.get("cover"):
            fails.append("dedupe did not inherit a cover from a duplicate")

    if fails:
        problems.extend(fails)
        print(f"{FAIL} {len(fails)} search problem(s)")
        for f in fails:
            print(f"    {f}")
    else:
        print(f"{OK} scoring ranks correctly; dedupe merges across sources")


def check_handlers() -> None:
    head("Handler collisions")
    cmds = defaultdict(list)
    cbs = defaultdict(list)
    for p in (ROOT / "plugins").rglob("*.py"):
        src = p.read_text(encoding="utf-8", errors="ignore")
        rel = str(p.relative_to(ROOT))
        for m in re.finditer(r"filters\.command\(\s*(\[[^\]]*\]|\"[^\"]*\"|'[^']*')", src):
            for c in re.findall(r"[\"']([^\"']+)[\"']", m.group(1)):
                cmds[c].append(rel)
        for m in re.finditer(r"filters\.regex\(\s*r?[\"']\^([A-Za-z0-9_]+)(\$?)", src):
            # "$"-anchored patterns cannot shadow a longer prefix.
            if m.group(2) != "$":
                cbs[m.group(1)].append(rel)

    # Known and intentional: the first-registered handler wins by design.
    #   /help    -> help_cmd.py (richer menu) shadows start.py
    #   /stats   -> stats_cmd.py public dashboard; start.py copy is owner-gated
    #   /usettings -> split by argument count (bare = self, <id> = owner)
    KNOWN_OK = {"help", "stats", "usettings"}
    dup_cmd = {
        c: f for c, f in cmds.items()
        if len(set(f)) > 1 and c not in KNOWN_OK
    }
    if dup_cmd:
        warnings_found.append(f"commands registered in multiple files: {dup_cmd}")
        print(f"{WARN} same command in multiple files:")
        for c, f in dup_cmd.items():
            print(f"    /{c}: {sorted(set(f))}")
    else:
        print(f"{OK} no command registered twice ({len(cmds)} commands)")

    # A shorter prefix swallowing a longer one is the classic callback bug.
    keys = sorted(cbs)
    # ^vep_ carries a negative lookahead guard for ^vep_pg_ (verified).
    KNOWN_GUARDED = {("vep_", "vep_pg_")}
    real = [
        (a, b) for a in keys for b in keys
        if a != b and b.startswith(a) and (a, b) not in KNOWN_GUARDED
    ]
    if real:
        uniq = sorted(set(real))[:10]
        warnings_found.append(f"callback prefix overlaps: {uniq}")
        print(f"{WARN} {len(uniq)} callback prefix overlap(s) — verify guards:")
        for a, b in uniq:
            print(f"    ^{a} may shadow ^{b}")
    else:
        print(f"{OK} no callback prefix shadowing ({len(cbs)} prefixes)")


def check_ui() -> None:
    head("UI / HTML safety")
    from utils import tgui

    allowed = {
        "b", "strong", "i", "em", "u", "ins", "s", "strike", "del", "span",
        "tg-spoiler", "a", "tg-emoji", "code", "pre", "blockquote",
    }
    samples = [
        tgui.Card("T & <x>", "🔥").field("A", tgui.code("v"))
        .section("S", "body").section("E", "x", expandable=True)
        .table(["a", "b"], [[1, "<script>"]]).progress(50).note("n").build(),
        tgui.table(["h"], [["<script>alert(1)</script>"]]),
        tgui.spoiler("a<b>"), tgui.emoji("1", "x"),
        tgui.pre("a<b>", "python"), tgui.heading("H&Q", 1, "⭐"),
    ]
    bad = []
    for s in samples:
        for tag in re.findall(r"</?([A-Za-z0-9-]+)", s):
            if tag.lower() not in allowed:
                bad.append(f"illegal tag <{tag}>")
        if re.search(r"&(?:AMP|LT|GT|QUOT);", s):
            bad.append("double-escaped entity")
        stack = []
        for m in re.finditer(r"<(/?)([A-Za-z0-9-]+)[^>]*>", s):
            close, tag = m.group(1), m.group(2).lower()
            if close:
                if not stack or stack.pop() != tag:
                    bad.append(f"unbalanced </{tag}>")
            else:
                stack.append(tag)
        if stack:
            bad.append(f"unclosed {stack}")
    if bad:
        problems.extend(bad)
        print(f"{FAIL} {bad}")
    else:
        print(f"{OK} HTML is legal, balanced and escaped")

    rep = tgui.backend_report()
    print(f"{OK} backends: kurigram={rep['kurigram']} styles={rep['kurigram_styles']} "
          f"aiogram={rep['aiogram']} (Bot API {rep['aiogram_bot_api']}) "
          f"native_disabled={rep['native_disabled']}")

    # every button must carry an action or Telegram rejects the row
    kb = tgui.Keyboard().row(
        tgui.Btn("a", "x", style=tgui.PRIMARY),
        tgui.Btn("b", disabled=True),
        tgui.Btn("c", copy="v"),
        tgui.Btn("d", url="https://t.me"),
    )
    dead = [
        b.text for row in kb.render().inline_keyboard for b in row
        if not (getattr(b, "callback_data", None) or getattr(b, "url", None)
                or getattr(b, "copy_text", None))
    ]
    if dead:
        problems.append(f"buttons without action: {dead}")
        print(f"{FAIL} buttons with no action: {dead}")
    else:
        print(f"{OK} all rendered buttons carry an action")


def check_rich() -> None:
    """Validate native Rich Message HTML (Bot API 10.1+) grammar."""
    head("Rich messages (Bot API 10.x)")
    from utils.richmsg import RichDoc, rich_available, codespan, i as _i

    RICH_OK = {
        "b", "strong", "i", "em", "u", "ins", "s", "strike", "del", "span",
        "tg-spoiler", "a", "tg-emoji", "code", "pre", "blockquote", "cite",
        "aside", "details", "summary", "table", "caption", "tr", "th", "td",
        "ul", "ol", "li", "input", "p", "h1", "h2", "h3", "h4", "h5", "h6",
        "hr", "footer", "mark", "sub", "sup", "tg-math", "tg-math-block",
        "tg-time", "br", "figure",
    }
    VOID = {"hr", "br", "input"}

    doc = (
        RichDoc()
        .heading("Report", 1, "📊")
        .field_row("Source", codespan("allanime"))
        .table(["Ep", "Q"], [[1, "1080p"]], align=["r", "c"], caption="Batch")
        .bullets(["one", "two"])
        .numbered(["a"], start=3)
        .checklist([("done", True), ("todo", False)])
        .quote("<p>q</p>", credit="CEO", expandable=True)
        .pull_quote("<p>p</p>", "Author")
        .details("Log", "<p>ok</p>")
        .code_block("x=1", "python")
        .progress(50, "up")
        .divider()
        .footer(_i("bot"))
    )
    variants = {
        "full doc": doc.html(),
        "empty doc": RichDoc().html(),
        "empty table": RichDoc().table([], []).html(),
        "empty lists": RichDoc().bullets([]).numbered([]).checklist([]).html(),
        "level clamp": RichDoc().heading("t", 99).html(),
        "injection": RichDoc().heading("<script>alert(1)</script>", 1)
        .table(["<x>"], [["<img onerror=1>"]]).html(),
    }
    bad = []
    for label, html in variants.items():
        tags = {t.lower() for t in re.findall(r"</?([A-Za-z0-9-]+)", html)}
        for t in tags - RICH_OK:
            bad.append(f"{label}: illegal <{t}>")
        stack = []
        for m in re.finditer(r"<(/?)([A-Za-z0-9-]+)([^>]*)>", html):
            close, tag, attrs = m.group(1), m.group(2).lower(), m.group(3)
            if tag in VOID or attrs.rstrip().endswith("/"):
                continue
            if close:
                if not stack or stack.pop() != tag:
                    bad.append(f"{label}: unbalanced </{tag}>")
            else:
                stack.append(tag)
        if stack:
            bad.append(f"{label}: unclosed {stack}")
    if "<script>" in variants["injection"]:
        bad.append("injection: raw <script> survived escaping")

    if bad:
        problems.extend(bad)
        print(f"{FAIL} {len(bad)} rich-HTML problem(s)")
        for x in bad[:10]:
            print(f"    {x}")
    else:
        print(f"{OK} rich HTML valid across {len(variants)} variants "
              "(tags, balance, escaping)")

    # the classic fallback must also be legal Telegram HTML
    fb = doc.fallback()
    CLASSIC = {
        "b", "strong", "i", "em", "u", "ins", "s", "strike", "del", "span",
        "tg-spoiler", "a", "tg-emoji", "code", "pre", "blockquote",
    }
    illegal = {t.lower() for t in re.findall(r"</?([A-Za-z0-9-]+)", fb)} - CLASSIC
    if illegal:
        problems.append(f"fallback uses non-classic tags: {sorted(illegal)}")
        print(f"{FAIL} fallback emits {sorted(illegal)}")
    else:
        print(f"{OK} classic fallback uses only legacy-safe tags")

    st = rich_available()
    print(f"{OK if st['ok'] else WARN} native send: {st['reason']}")
    if not st["ok"]:
        warnings_found.append(f"rich messages unavailable: {st['reason']}")


def check_escaping() -> None:
    """Catch pre-escaped entities passed into helpers that escape again."""
    head("Double-escaping")
    hits = []
    # tip()/error()/warn()/success()/heading() all run html.escape internally.
    escaping_calls = re.compile(
        r"\.(?:tip|success|error|warn)\(\s*[\"'][^\"']*&(?:lt|gt|amp|quot);"
    )
    for p in ROOT.rglob("*.py"):
        if ".venv" in p.parts or "__pycache__" in p.parts:
            continue
        src = p.read_text(encoding="utf-8", errors="ignore")
        for m in escaping_calls.finditer(src):
            line = src[: m.start()].count("\n") + 1
            hits.append(f"{p.relative_to(ROOT)}:{line} pre-escaped text into an escaping helper")
    if hits:
        problems.extend(hits)
        print(f"{FAIL} {len(hits)} double-escape risk(s)")
        for x in hits:
            print(f"    {x}")
    else:
        print(f"{OK} no pre-escaped text passed to escaping helpers")

    # And verify rendered screens carry no broken entities.
    import config

    config.Config.OWNER_ID = config.Config.OWNER_ID or [1]
    from utils.ui import START_TEXT, HELP_TEXT

    bad = []
    for name, t in (("START_TEXT", START_TEXT), ("HELP_TEXT", HELP_TEXT)):
        if re.search(r"&amp;(?:amp|lt|gt|quot);", t):
            bad.append(name)
    if bad:
        problems.append(f"double-escaped entities in {bad}")
        print(f"{FAIL} double-escaped entities in {bad}")
    else:
        print(f"{OK} rendered screens have clean entities")


def check_engine() -> None:
    head("Video engine")
    from services import vengine
    from services.hplugin import plugin_status

    st = vengine.engine_status()
    print(f"{OK if st['yt_dlp'] else FAIL} yt-dlp {st['yt_dlp']}")
    if not st["yt_dlp"]:
        problems.append("yt-dlp missing")
    for opt in ("ffmpeg", "aria2c"):
        print(f"{OK if st[opt] else WARN} {opt} {st[opt]}"
              + ("" if st[opt] else "  (optional but recommended)"))
        if not st[opt]:
            warnings_found.append(f"{opt} not installed")

    ps = plugin_status()
    if ps["installed"]:
        print(f"{OK} hanime-plugin: {len(ps['extractors'])} extractors, "
              f"crypto={ps['crypto']}")
        if not ps["crypto"]:
            warnings_found.append("pycryptodomex missing (HAnime.tv will fail)")
    else:
        warnings_found.append("hanime-plugin inactive")
        print(f"{WARN} hanime-plugin inactive: {ps.get('error')}")

    for q in ("480", "720", "1080", "best", "junk"):
        if not vengine.build_format_ladder(q):
            problems.append(f"empty format ladder for {q}")
    print(f"{OK} format ladders build for all quality inputs")


def main() -> int:
    print("\033[1mManhua-Bot health audit\033[0m")
    for fn in (check_compile, check_plugins, check_sources, check_video_sources,
               check_resilience, check_queue, check_search, check_handlers,
               check_ui, check_rich,
               check_escaping, check_engine):
        try:
            fn()
        except Exception as e:
            problems.append(f"{fn.__name__} crashed: {type(e).__name__}: {e}")
            print(f"{FAIL} {fn.__name__} crashed: {type(e).__name__}: {e}")

    head("Summary")
    if problems:
        print(f"{FAIL} {len(problems)} problem(s):")
        for p in problems:
            print(f"    - {p}")
    else:
        print(f"{OK} no problems found")
    if warnings_found:
        print(f"{WARN} {len(warnings_found)} warning(s):")
        for w in warnings_found:
            print(f"    - {w}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
