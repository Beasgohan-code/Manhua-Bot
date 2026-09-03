# Manhua-Bot - video download + Telegram upload
#
# Extraction is delegated to yt-dlp so that HLS / iframe / embed players are
# handled generically. Uploading honours the per-user /usettings preferences:
# video vs document, custom thumbnail, metadata (title / author) and quality.

from __future__ import annotations

import asyncio
import logging
import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, Optional

from config import Config
from database.db import db
from services.util import sanitize

log = logging.getLogger(__name__)

try:
    import yt_dlp  # noqa: F401

    HAS_YTDLP = True
except ImportError:  # pragma: no cover
    HAS_YTDLP = False

VIDEO_DIR = Path(getattr(Config, "DOWNLOAD_DIR", "downloads")) / "video"

# Telegram bot API upload ceiling (~2 GB for bots on most DCs)
MAX_UPLOAD = 2 * 1024 * 1024 * 1024


# ---------------------------------------------------------------- settings
DEFAULTS = {
    "v_upload": "video",          # video | document
    "v_quality": "720",           # 480 | 720 | 1080 | best
    "v_thumb": None,              # base64 jpeg
    "v_meta_title": "{title} - E{ep}",
    "v_meta_author": "",
    "v_caption": None,
    "v_split": True,              # split files above the upload limit
    "v_subs": False,              # burn/attach subtitles when available
}


async def vget(uid: int, key: str):
    try:
        val = await db.get_cfg(uid, key, DEFAULTS.get(key))
        return DEFAULTS.get(key) if val is None else val
    except Exception:
        return DEFAULTS.get(key)


async def vset(uid: int, key: str, value):
    await db.set_cfg(uid, key, value)


def has_ffmpeg() -> bool:
    return shutil.which("ffmpeg") is not None


def fmt_size(num: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if num < 1024:
            return f"{num:.1f}{unit}"
        num /= 1024
    return f"{num:.1f}TB"


def fmt_dur(seconds: Optional[float]) -> str:
    if not seconds:
        return "?"
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def _fmt_selector(quality: str) -> str:
    if quality in ("best", "max"):
        return "bv*+ba/b"
    try:
        height = int(re.sub(r"\D", "", quality) or 720)
    except ValueError:
        height = 720
    return f"bv*[height<={height}]+ba/b[height<={height}]/b"


# ---------------------------------------------------------------- download
def _blocking_download(
    page_url: str,
    out_base: Path,
    quality: str,
    headers: Dict[str, str],
    progress_cb=None,
) -> Dict[str, Any]:
    """Run yt-dlp synchronously; called via asyncio.to_thread."""
    import yt_dlp

    def hook(d):
        if progress_cb and d.get("status") == "downloading":
            try:
                progress_cb(
                    d.get("downloaded_bytes") or 0,
                    d.get("total_bytes") or d.get("total_bytes_estimate") or 0,
                    d.get("speed") or 0,
                    d.get("eta") or 0,
                )
            except Exception:
                pass

    opts = {
        "format": _fmt_selector(quality),
        "outtmpl": str(out_base) + ".%(ext)s",
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "noplaylist": True,
        "retries": 5,
        "fragment_retries": 10,
        "concurrent_fragment_downloads": 8,
        "http_headers": headers or {},
        "progress_hooks": [hook],
        "merge_output_format": "mp4",
        "geo_bypass": True,
        "nocheckcertificate": True,
    }
    if not has_ffmpeg():
        # Without ffmpeg we cannot merge separate A/V streams.
        opts["format"] = "b"
        opts.pop("merge_output_format", None)

    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(page_url, download=True)
        if info.get("entries"):
            info = info["entries"][0]
        path = ydl.prepare_filename(info)

    if not os.path.exists(path):
        stem = out_base.name
        for cand in out_base.parent.glob(stem + ".*"):
            path = str(cand)
            break

    return {
        "path": path,
        "title": info.get("title") or out_base.name,
        "duration": info.get("duration"),
        "width": info.get("width"),
        "height": info.get("height"),
        "thumbnail": info.get("thumbnail"),
    }


async def download_video(
    page_url: str,
    dest_dir: Path,
    name: str,
    quality: str = "720",
    headers: Optional[Dict[str, str]] = None,
    progress_cb=None,
) -> Optional[Dict[str, Any]]:
    if not HAS_YTDLP:
        raise RuntimeError(
            "yt-dlp is not installed. Run: pip install -r requirements.txt"
        )
    dest_dir.mkdir(parents=True, exist_ok=True)
    out_base = dest_dir / sanitize(name)[:80]
    return await asyncio.to_thread(
        _blocking_download, page_url, out_base, quality, headers or {}, progress_cb
    )


# ---------------------------------------------------------------- metadata
async def apply_metadata(path: str, title: str, author: str) -> str:
    """Remux with new container metadata (no re-encode). Returns final path."""
    if not has_ffmpeg() or not (title or author):
        return path
    src = Path(path)
    out = src.with_name(src.stem + ".meta" + src.suffix)
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error", "-i", str(src),
        "-c", "copy", "-map", "0",
        "-metadata", f"title={title}",
    ]
    if author:
        cmd += ["-metadata", f"artist={author}", "-metadata", f"author={author}"]
    cmd.append(str(out))
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        await proc.communicate()
        if out.exists() and out.stat().st_size > 0:
            src.unlink(missing_ok=True)
            return str(out)
    except Exception as exc:
        log.warning(f"[VDL] metadata failed: {exc}")
    return path


async def gen_thumb(path: str, dest: Path) -> Optional[str]:
    """Grab a frame at ~10% for the Telegram thumbnail."""
    if not has_ffmpeg():
        return None
    out = dest / (Path(path).stem + ".thumb.jpg")
    try:
        proc = await asyncio.create_subprocess_exec(
            "ffmpeg", "-y", "-loglevel", "error", "-ss", "20", "-i", path,
            "-vframes", "1", "-vf", "scale=320:-1", str(out),
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        await proc.communicate()
        return str(out) if out.exists() else None
    except Exception:
        return None


async def user_thumb(uid: int, dest: Path) -> Optional[str]:
    """Materialise the user's custom thumbnail from settings, if set."""
    import base64

    b64 = await vget(uid, "v_thumb")
    if not b64:
        return None
    try:
        out = dest / f"custom_thumb_{uid}.jpg"
        dest.mkdir(parents=True, exist_ok=True)
        out.write_bytes(base64.b64decode(b64))
        return str(out)
    except Exception as exc:
        log.warning(f"[VDL] custom thumb decode failed: {exc}")
        return None


async def split_file(path: str, part_size: int = MAX_UPLOAD - (50 * 1024 * 1024)):
    """Split an oversized file into uploadable parts."""
    src = Path(path)
    total = src.stat().st_size
    if total <= part_size:
        return [str(src)]
    parts = []
    with src.open("rb") as fh:
        idx = 1
        while True:
            chunk = fh.read(part_size)
            if not chunk:
                break
            part = src.with_name(f"{src.stem}.part{idx:02d}{src.suffix}")
            part.write_bytes(chunk)
            parts.append(str(part))
            idx += 1
    src.unlink(missing_ok=True)
    return parts


# ---------------------------------------------------------------- upload
def render(template: str, ctx: Dict[str, Any]) -> str:
    out = template or ""
    for key, val in ctx.items():
        out = out.replace("{" + key + "}", str(val if val is not None else ""))
    return out


async def send_video(
    client,
    chat_id: int,
    uid: int,
    file_info: Dict[str, Any],
    ctx: Dict[str, Any],
    status_msg=None,
):
    """Upload a downloaded file honouring the user's /usettings."""
    path = file_info["path"]
    tmp = Path(path).parent

    mode = await vget(uid, "v_upload")
    meta_title = render(await vget(uid, "v_meta_title"), ctx)
    meta_author = render(await vget(uid, "v_meta_author") or "", ctx)
    cap_tpl = await vget(uid, "v_caption")

    path = await apply_metadata(path, meta_title, meta_author)

    thumb = await user_thumb(uid, tmp) or await gen_thumb(path, tmp)

    size = os.path.getsize(path)
    duration = int(file_info.get("duration") or 0)

    if cap_tpl:
        caption = render(cap_tpl, {**ctx, "size": fmt_size(size), "dur": fmt_dur(duration)})
    else:
        caption = (
            f"<b>{ctx.get('title', '')}</b>\n"
            f"<blockquote>"
            f"Episode: <code>{ctx.get('ep', '?')}</code>\n"
            f"Source: <code>{ctx.get('source', '?')}</code>\n"
            f"Quality: <code>{ctx.get('quality', '?')}p</code> · "
            f"{fmt_size(size)} · {fmt_dur(duration)}"
            f"</blockquote>"
        )

    files = [path]
    if size > MAX_UPLOAD and await vget(uid, "v_split"):
        if status_msg:
            try:
                await status_msg.edit(
                    f"<blockquote>✂️ Splitting {fmt_size(size)} into parts…</blockquote>"
                )
            except Exception:
                pass
        files = await split_file(path)

    sent = []
    for i, fp in enumerate(files, 1):
        label = caption if len(files) == 1 else f"{caption}\n<i>Part {i}/{len(files)}</i>"
        fname = sanitize(meta_title or Path(fp).stem) + Path(fp).suffix
        try:
            if mode == "document":
                msg = await client.send_document(
                    chat_id,
                    fp,
                    caption=label,
                    thumb=thumb,
                    file_name=fname,
                    force_document=True,
                )
            else:
                msg = await client.send_video(
                    chat_id,
                    fp,
                    caption=label,
                    thumb=thumb,
                    duration=duration,
                    width=file_info.get("width") or 0,
                    height=file_info.get("height") or 0,
                    supports_streaming=True,
                    file_name=fname,
                )
            sent.append(msg)
        finally:
            try:
                os.remove(fp)
            except OSError:
                pass

    if thumb:
        try:
            os.remove(thumb)
        except OSError:
            pass
    return sent


async def download_and_send_video(
    client,
    chat_id: int,
    uid: int,
    series: Dict[str, Any],
    episode: Dict[str, Any],
    status_msg=None,
):
    """End-to-end: resolve → download → metadata → upload."""
    quality = await vget(uid, "v_quality")
    title = series.get("title") or "Video"
    ep_num = episode.get("num") or episode.get("id") or "1"
    page_url = episode.get("url") or series.get("url")

    from services.vmgr import vmgr

    src_obj = vmgr.get(series.get("src") or "")
    headers = getattr(src_obj, "headers", {}) if src_obj else {}

    resolved = await vmgr.get_episode(series.get("src") or "", page_url) if src_obj else None
    if resolved:
        page_url = resolved.get("stream_url") or resolved.get("page_url") or page_url
        headers = resolved.get("headers") or headers

    tmp = VIDEO_DIR / str(uid) / str(int(time.time()))
    name = f"{sanitize(title)[:60]} - E{ep_num}"

    last = [0.0]

    def progress(done, total, speed, eta):
        now = time.time()
        if now - last[0] < 6 or not status_msg:
            return
        last[0] = now
        pct = (done / total * 100) if total else 0
        bar = "█" * int(pct / 10) + "░" * (10 - int(pct / 10))
        text = (
            f"<b>⬇️ Downloading</b>\n<blockquote>"
            f"{title} — E{ep_num}\n"
            f"<code>{bar}</code> {pct:.1f}%\n"
            f"{fmt_size(done)} / {fmt_size(total) if total else '?'} · "
            f"{fmt_size(speed)}/s · ETA {int(eta or 0)}s"
            f"</blockquote>"
        )
        asyncio.get_event_loop().create_task(_safe_edit(status_msg, text))

    info = await download_video(
        page_url, tmp, name, quality=quality, headers=headers, progress_cb=progress
    )
    if not info or not info.get("path") or not os.path.exists(info["path"]):
        raise RuntimeError("Download produced no file")

    if status_msg:
        await _safe_edit(status_msg, "<blockquote>📤 Uploading to Telegram…</blockquote>")

    ctx = {
        "title": title,
        "ep": ep_num,
        "episode": ep_num,
        "source": series.get("src_name") or series.get("src") or "",
        "quality": quality,
    }
    try:
        return await send_video(client, chat_id, uid, info, ctx, status_msg)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


async def _safe_edit(msg, text):
    try:
        await msg.edit(text)
    except Exception:
        pass
