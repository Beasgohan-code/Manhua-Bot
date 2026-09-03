# Manhua-Bot - video download engine
#
# Engine logic ported/adapted from:
#   * zenin-373/Hstream-TG  — format fallback ladder, aria2c external
#     downloader, .ass subtitle resolution + MKV remux, live progress cards
#   * MatrixRobots/Hanime-Downloader — quality labelling, HLS handling
#   * hanime-plugin — yt-dlp extractor pack for hanime.tv / hstream / oppai
#
# Everything here is sync-safe: blocking yt-dlp work runs via to_thread.

from __future__ import annotations

import asyncio
import logging
import re
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional

log = logging.getLogger(__name__)

try:
    import yt_dlp  # noqa: F401

    HAS_YTDLP = True
except ImportError:
    HAS_YTDLP = False


# --------------------------------------------------------------- formatting
QUALITY_META = {
    "2160": ("⬛", "2160p 4K"),
    "1080": ("🔴", "1080p Full HD"),
    "720": ("🔵", "720p HD"),
    "480": ("🟡", "480p SD"),
    "360": ("🟠", "360p Low"),
    "best": ("✨", "Best available"),
}


def quality_label(height: str) -> str:
    emoji, name = QUALITY_META.get(str(height), ("📹", f"{height}p"))
    return f"{emoji} {name}"


def human_bytes(n: float) -> str:
    n = float(n or 0)
    for unit in ("B", "KB", "MB", "GB"):
        if abs(n) < 1024:
            return f"{n:.2f}{unit}"
        n /= 1024
    return f"{n:.2f}TB"


def human_time(seconds: Optional[float]) -> str:
    if not seconds:
        return "—"
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def progress_bar(pct: float, width: int = 12) -> str:
    pct = max(0.0, min(100.0, pct or 0.0))
    filled = min(width, max(0, int(round(width * pct / 100.0))))
    return "█" * filled + "░" * (width - filled)


def has_bin(name: str) -> bool:
    return shutil.which(name) is not None


# ------------------------------------------------------------------ engine
@dataclass
class DownloadResult:
    path: Path
    title: str = ""
    duration: Optional[float] = None
    width: Optional[int] = None
    height: Optional[int] = None
    thumbnail: str = ""
    ext: str = ""
    subtitled: bool = False
    formats: List[Dict] = field(default_factory=list)


def build_format_ladder(quality: str) -> List[str]:
    """Fallback ladder — first format that yields a file wins.

    Mirrors Hstream-TG's approach: never fail outright because one format
    string didn't match; degrade instead.
    """
    if quality in ("best", "max", ""):
        return ["bv*+ba/b", "best", "bv*[height<=1080]+ba/b[height<=1080]", "b"]
    try:
        h = int(re.sub(r"\D", "", str(quality)) or 720)
    except ValueError:
        h = 720
    return [
        f"bv*[height<={h}]+ba/b[height<={h}]",
        f"best[height<={h}]",
        f"bv*[height<={h}]+ba",
        "bv*+ba/b",
        "best",
        "b",
    ]


def _ydl_opts(fmt: str, outtmpl: str, headers: Dict[str, str], hook) -> dict:
    opts = {
        "format": fmt,
        "outtmpl": outtmpl,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "retries": 5,
        "fragment_retries": 10,
        "concurrent_fragment_downloads": 8,
        "progress_hooks": [hook] if hook else [],
        "http_headers": headers or {},
        "geo_bypass": True,
        "nocheckcertificate": True,
        "hls_prefer_native": True,
        "restrictfilenames": True,
    }
    if has_bin("ffmpeg"):
        opts["merge_output_format"] = "mp4"
    if has_bin("aria2c"):
        # Big speed win on segmented/HLS sources (from Hstream-TG).
        opts["external_downloader"] = "aria2c"
        opts["external_downloader_args"] = {
            "aria2c": ["-x", "16", "-s", "16", "-k", "1M", "--console-log-level=warn"]
        }
    return opts


def _pick_output(folder: Path) -> Optional[Path]:
    junk = {".ass", ".srt", ".vtt", ".part", ".ytdl", ".temp", ".jpg", ".png", ".webp"}
    files = [
        p for p in folder.glob("*")
        if p.is_file() and p.suffix.lower() not in junk and p.stat().st_size > 0
    ]
    return max(files, key=lambda p: p.stat().st_ctime) if files else None


# Container magic bytes -> correct extension.
def sniff_container(path: Path) -> Optional[str]:
    try:
        with path.open("rb") as fh:
            head = fh.read(16)
    except OSError:
        return None
    if len(head) < 12:
        return None
    if head[4:8] == b"ftyp":
        return "mp4"
    if head[:4] == b"\x1a\x45\xdf\xa3":
        return "mkv"
    if head[:4] == b"RIFF" and head[8:12] == b"AVI ":
        return "avi"
    if head[:3] == b"FLV":
        return "flv"
    # MPEG-TS: 188-byte packets starting with sync byte 0x47
    if head[:1] == b"G":
        return "ts"
    return None


def fix_extension(path: Path) -> Path:
    """Rename when the real container disagrees with the extension.

    yt-dlp names the output from the requested merge format, but if the
    ffmpeg postprocessor fails (missing/broken ffmpeg) the bytes can still
    be raw TS. Uploading that as ".mp4" gives players a file they refuse to
    open, so trust the magic bytes instead.
    """
    real = sniff_container(path)
    if not real:
        return path
    if path.suffix.lower().lstrip(".") == real:
        return path
    target = path.with_suffix("." + real)
    try:
        path.rename(target)
        log.info(f"[VENGINE] container was {real}, renamed {path.name} -> {target.name}")
        return target
    except OSError:
        return path


async def to_mp4(path: Path) -> Path:
    """Remux a non-MP4/MKV container into MP4 so Telegram can stream it."""
    if path.suffix.lower() in (".mp4", ".mkv") or not has_bin("ffmpeg"):
        return path
    out = path.with_suffix(".mp4")
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error", "-i", str(path),
        "-c", "copy", "-bsf:a", "aac_adtstoasc", "-movflags", "+faststart",
        str(out),
    ]
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE
        )
        _, err = await proc.communicate()
        if proc.returncode == 0 and out.exists() and out.stat().st_size > 0:
            path.unlink(missing_ok=True)
            return out
        log.warning(f"[VENGINE] to_mp4 failed: {err.decode()[:200]}")
    except Exception as exc:
        log.warning(f"[VENGINE] to_mp4 error: {exc}")
    return path


def _blocking_download(
    url: str,
    folder: Path,
    quality: str,
    headers: Dict[str, str],
    hook,
) -> DownloadResult:
    import yt_dlp

    folder.mkdir(parents=True, exist_ok=True)
    outtmpl = str(folder / "%(title).80s.%(ext)s")
    info = None
    last_err: Optional[Exception] = None

    for fmt in build_format_ladder(quality):
        try:
            with yt_dlp.YoutubeDL(_ydl_opts(fmt, outtmpl, headers, hook)) as ydl:
                info = ydl.extract_info(url, download=True)
            last_err = None
            break
        except Exception as exc:
            last_err = exc
            log.debug(f"[VENGINE] format {fmt} failed: {exc}")
            continue

    path = _pick_output(folder)
    if path is not None:
        path = fix_extension(path)
    if path is None:
        raise RuntimeError(
            f"Download produced no file"
            + (f" — {str(last_err)[:200]}" if last_err else "")
        )

    if info and info.get("entries"):
        info = info["entries"][0]
    info = info or {}
    return DownloadResult(
        path=path,
        title=info.get("title") or path.stem,
        duration=info.get("duration"),
        width=info.get("width"),
        height=info.get("height"),
        thumbnail=info.get("thumbnail") or "",
        ext=path.suffix.lstrip("."),
    )


async def download(
    url: str,
    folder: Path,
    quality: str = "720",
    headers: Optional[Dict[str, str]] = None,
    on_progress: Optional[Callable[[dict], None]] = None,
) -> DownloadResult:
    """Download `url` into `folder`, reporting live progress."""
    if not HAS_YTDLP:
        raise RuntimeError("yt-dlp is not installed — pip install -r requirements.txt")

    loop = asyncio.get_running_loop()
    last = [0.0]

    def hook(d: dict) -> None:
        if not on_progress:
            return
        status = d.get("status")
        now = time.time()
        if status == "downloading" and now - last[0] < 4:
            return
        last[0] = now
        total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
        done = d.get("downloaded_bytes") or 0
        payload = {
            "status": status,
            "done": done,
            "total": total,
            "pct": (100.0 * done / total) if total else 0.0,
            "speed": d.get("speed") or 0,
            "eta": d.get("eta") or 0,
            "filename": d.get("filename") or "",
        }
        # hook runs in a worker thread; bounce back to the loop
        loop.call_soon_threadsafe(lambda: asyncio.ensure_future(_maybe(on_progress, payload)))

    return await asyncio.to_thread(
        _blocking_download, url, folder, quality, headers or {}, hook
    )


async def _maybe(fn, payload):
    try:
        res = fn(payload)
        if asyncio.iscoroutine(res):
            await res
    except Exception as exc:
        log.debug(f"[VENGINE] progress callback: {exc}")


async def probe(url: str, headers: Optional[Dict[str, str]] = None) -> Optional[dict]:
    """Resolve metadata + available heights without downloading."""
    if not HAS_YTDLP:
        return None

    def _run():
        import yt_dlp

        opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "http_headers": headers or {},
            "nocheckcertificate": True,
            "geo_bypass": True,
        }
        with yt_dlp.YoutubeDL(opts) as ydl:
            return ydl.extract_info(url, download=False)

    try:
        info = await asyncio.to_thread(_run)
    except Exception as exc:
        log.debug(f"[VENGINE] probe failed: {exc}")
        return None
    if not info:
        return None
    if info.get("entries"):
        info = info["entries"][0]

    heights = sorted(
        {
            int(f["height"])
            for f in (info.get("formats") or [])
            if f.get("height") and f.get("vcodec") != "none"
        },
        reverse=True,
    )
    return {
        "title": info.get("title") or "",
        "duration": info.get("duration"),
        "thumbnail": info.get("thumbnail") or "",
        "heights": heights,
        "extractor": info.get("extractor_key") or info.get("extractor") or "",
        "webpage_url": info.get("webpage_url") or url,
    }


# -------------------------------------------------------------- subtitles
SUB_HOSTS = [
    "https://oppai-str.shoujo-h.org",
    "https://imoto-str.ane-h.xyz",
    "https://shinobu-str.rorikon-h.xyz",
]
_PARTICLES = {"no", "wa", "wo", "ga", "ni", "de", "to", "na", "o", "yo", "kun", "chan", "san"}


def _sub_slug_candidates(slug: str) -> List[str]:
    """Slug spellings used by the known .ass hosts (from Hstream-TG)."""
    parts = slug.split("-")
    out = [
        ".".join(parts),
        ".".join(w if w in _PARTICLES else w.capitalize() for w in parts),
    ]
    glued, i = [], 0
    while i < len(parts):
        w = parts[i]
        if i + 1 < len(parts) and parts[i + 1] in {"kun", "chan", "san"} and w not in _PARTICLES:
            glued.append(w.capitalize() + parts[i + 1])
            i += 2
        else:
            glued.append(w if w in _PARTICLES else w.capitalize())
            i += 1
    out.append(".".join(glued))
    out.append(slug)
    seen: set = set()
    return [c for c in out if not (c in seen or seen.add(c))]


async def fetch_subtitle(page_url: str, dest: Path, headers: Dict[str, str]) -> Optional[Path]:
    """Best-effort English .ass lookup: page scrape, then known hosts."""
    import aiohttp

    async def grab(session, url: str) -> bool:
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=25)) as r:
                if r.status != 200:
                    return False
                data = await r.read()
                if len(data) < 64:
                    return False
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(data)
                return True
        except Exception:
            return False

    try:
        async with aiohttp.ClientSession(headers=headers or {}) as session:
            html = ""
            try:
                async with session.get(page_url, timeout=aiohttp.ClientTimeout(total=25)) as r:
                    if r.status == 200:
                        html = await r.text()
            except Exception:
                pass

            found: List[str] = []
            for pat in (r'href=["\'](https?://[^"\']+?/eng\.ass)["\']',
                        r'href=["\'](https?://[^"\']+?\.ass)["\']'):
                for m in re.finditer(pat, html, re.I):
                    if m.group(1) not in found:
                        found.append(m.group(1))
            found.sort(key=lambda u: 0 if "eng.ass" in u.lower() else 1)
            for u in found:
                if await grab(session, u):
                    return dest

            # Fallback: guess against the known subtitle CDNs
            m = re.search(r"-(\d+)/?$", page_url.rstrip("/"))
            if not m:
                return None
            ep = int(m.group(1))
            slug = re.sub(r"-\d+$", "", page_url.rstrip("/").split("/")[-1])
            years = ["2026", "2025", "2024", "2023", "2022", "2021"]
            for host in SUB_HOSTS:
                for year in years:
                    for cand in _sub_slug_candidates(slug):
                        url = f"{host}/{year}/{cand}/E{ep:02d}/eng.ass"
                        if await grab(session, url):
                            return dest
    except Exception as exc:
        log.debug(f"[VENGINE] subtitle lookup: {exc}")
    return None


async def remux_with_subs(video: Path, sub: Path, out: Path) -> Optional[Path]:
    """Mux the .ass into an MKV as a soft subtitle track."""
    if not has_bin("ffmpeg"):
        return None
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-i", str(video), "-i", str(sub),
        "-map", "0", "-map", "1", "-c", "copy",
        "-metadata:s:s:0", "language=eng",
        str(out),
    ]
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE
        )
        _, err = await proc.communicate()
        if proc.returncode == 0 and out.exists() and out.stat().st_size > 0:
            return out
        log.warning(f"[VENGINE] remux failed: {err.decode()[:200]}")
    except Exception as exc:
        log.warning(f"[VENGINE] remux error: {exc}")
    return None


def engine_status() -> Dict[str, bool]:
    return {
        "yt_dlp": HAS_YTDLP,
        "ffmpeg": has_bin("ffmpeg"),
        "aria2c": has_bin("aria2c"),
    }
