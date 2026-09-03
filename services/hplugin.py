# Manhua-Bot - hanime-plugin (yt-dlp extractor pack) integration
#
# `hanime-plugin` ships yt-dlp extractor classes under the `yt_dlp_plugins`
# namespace: HanimeTV, Hstream, OppaiStream, HentaiHaven, Hentaimama,
# HanimeRed and Ohentai. yt-dlp discovers them automatically, but the
# discovery is silent — if the package (or its pycryptodomex dependency for
# HanimeTV's AES token) is missing, sites simply fall back to the generic
# extractor and produce confusing failures.
#
# This module makes that state explicit and queryable so the UI can report it.

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Dict, List, Optional

log = logging.getLogger(__name__)

# Extractor name -> friendly site label
PLUGIN_SITES = {
    "HanimeTV": "HAnime.tv",
    "Hstream": "HStream.moe",
    "OppaiStream": "Oppai.stream",
    "HentaiHaven": "HentaiHaven",
    "Hentaimama": "HentaiMama",
    "HanimeRed": "Hanime.red",
    "Ohentai": "OHentai",
}


@lru_cache(maxsize=1)
def plugin_status() -> Dict[str, object]:
    """Report which hanime-plugin extractors yt-dlp can actually see."""
    status: Dict[str, object] = {
        "installed": False,
        "crypto": False,
        "extractors": [],
        "missing": [],
        "error": None,
    }

    try:
        import Cryptodome  # noqa: F401

        status["crypto"] = True
    except ImportError:
        # HanimeTV needs AES-GCM for its token; without it that IE will fail.
        status["crypto"] = False

    try:
        import yt_dlp

        with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True}) as ydl:
            found = {ie.IE_NAME for ie in ydl._ies.values()}
    except Exception as exc:  # yt-dlp missing or broken
        status["error"] = str(exc)
        return status

    present = [n for n in PLUGIN_SITES if n in found]
    status["extractors"] = present
    status["missing"] = [n for n in PLUGIN_SITES if n not in found]
    status["installed"] = bool(present)
    if not present:
        status["error"] = "hanime-plugin extractors not registered"
    return status


def refresh() -> Dict[str, object]:
    plugin_status.cache_clear()
    return plugin_status()


def supports(url: str) -> Optional[str]:
    """Return the plugin extractor name that claims `url`, if any."""
    try:
        import yt_dlp

        with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True}) as ydl:
            for ie in ydl._ies.values():
                name = ie.IE_NAME
                if name in PLUGIN_SITES and ie.suitable(url):
                    return name
    except Exception:
        pass
    return None


def status_line() -> str:
    """Short human-readable status for settings / diagnostics screens."""
    st = plugin_status()
    if not st["installed"]:
        return "⚠️ hanime-plugin not active — <code>pip install hanime-plugin</code>"
    names = ", ".join(PLUGIN_SITES[n] for n in st["extractors"])  # type: ignore[index]
    line = f"✅ hanime-plugin active ({len(st['extractors'])}): {names}"  # type: ignore[arg-type]
    if not st["crypto"]:
        line += "\n⚠️ pycryptodomex missing — HAnime.tv token decryption will fail"
    return line


def log_status() -> None:
    st = plugin_status()
    if st["installed"]:
        log.info(f"[HPLUGIN] active extractors: {', '.join(st['extractors'])}")  # type: ignore[arg-type]
        if not st["crypto"]:
            log.warning("[HPLUGIN] pycryptodomex missing — HanimeTV will fail")
    else:
        log.warning(f"[HPLUGIN] inactive: {st.get('error')}")
