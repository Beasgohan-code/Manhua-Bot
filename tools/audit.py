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
               check_handlers, check_ui, check_engine):
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
