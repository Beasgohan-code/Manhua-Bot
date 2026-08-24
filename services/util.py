
import re
import logging
from typing import List, Tuple
log = logging.getLogger(__name__)
MAX_DISP = 50
MAX_PDF = 40
MAX_CHAN = 50
INVALID_CHARS = r'[<>:"/\\|?*]'
def sanitize(name):
    return re.sub(INVALID_CHARS, '', name).strip()
def trunc(txt, max_len=40):
    if len(txt) <= max_len:
        return txt
    cut = txt[:max_len]
    pos = max(cut.rfind(" "), cut.rfind("-"), cut.rfind("_"))
    return cut[:pos] if pos != -1 else cut
def extract_chap_no(chap_title):
    if not chap_title:
        return "000"
    text = str(chap_title).lower()
    patterns = [
        r'chapter\s*(\d+(?:\.\d+)?)',
        r'Chapter\s*(\d+(?:\.\d+)?)',
        r'ch\.?\s*(\d+(?:\.\d+)?)',
        r'episode\s*(\d+(?:\.\d+)?)',
        r'ep\.?\s*(\d+(?:\.\d+)?)',
        r'chapter\s*(\d+(?:\.\d+)?)\s*\(',
        r'chapter\s*(\d+(?:\.\d+)?)\s*\[',
        r'chapter\s*(\d+(?:\.\d+)?)\s*-',
        r'chapter\s*(\d+(?:\.\d+)?)\s*\(.*?\)',
        r'chapter\s*(\d+(?:\.\d+)?)\s*\|.*',
        r'#\s*(\d+(?:\.\d+)?)',
        r'-\s*(\d+(?:\.\d+)?)\s*(?:\(|\[|$)',
        r'(\d+(?:\.\d+)?)\s*$',
        r'(\d+(?:\.\d+)?)\s*[-–—]\s*.*$',
        r'\((\d+(?:\.\d+)?)\)',
        r'\[(\d+(?:\.\d+)?)\]',
        r'^(\d+(?:\.\d+)?)$',
    ]
    for pattern in patterns:
        m = re.search(pattern, text)
        if m:
            num = m.group(1)
            if '.' in num:
                parts = num.split('.')
                return f"{int(parts[0]):03d}.{parts[1]}"
            else:
                return f"{int(num):03d}"
    nums = re.findall(r'\d+', text)
    if nums:
        largest = max(nums, key=lambda x: int(x))
        return f"{int(largest):03d}"
    return "000"

def clean_chap(chap_title):
    if not chap_title:
        return ""
    # Remove parenthetical site names e.g. (Lagoon Scans)
    text = re.sub(r'\s*\([^)]*\)\s*$', '', str(chap_title))
    # Remove redundant "Chapter" or "Ch." if the template adds it anyway
    text = re.sub(r'^(?:Chapter|Ch\.|Episode|Ep\.)\s*', '', text, flags=re.IGNORECASE)
    return text.strip()

def extract_title(title: str) -> str:
    if not title:
        return "Unknown"
    title = title.strip()
    m = re.match(r'^([^(]+)', title)
    if m:
        main = m.group(1).strip()
        if main and len(main) > 3:
            title = main
    for sep in [' / ', '/ ', ' /', ' | ', '| ', ' |', ' || ']:
        if sep in title:
            parts = title.split(sep)
            if parts and len(parts[0].strip()) > 3:
                title = parts[0].strip()
                break
    title = re.sub(r'\s*\([^)]*\)\s*$', '', title)
    title = re.sub(r'\s*\((RESET|ASURA|REAPER|FLAME|ALPHA)\)\s*', '', title, flags=re.IGNORECASE)
    return re.sub(r'\s+', ' ', title).strip() or "Unknown"
def clean_title(title: str, max_len: int = MAX_DISP) -> str:
    return trunc(extract_title(title), max_len)
def safe_fname(title, max_len=MAX_PDF):
    try:
        primary = extract_title(title)
        safe = re.sub(INVALID_CHARS, '', primary).strip()
        return trunc(safe, max_len)
    except:
        return "manga"
def clean_chan(name: str) -> Tuple[List[str], str]:
    name = re.sub(r'\s*\[[^\]]*CAMPUS[^\]]*\]\s*', '', name, flags=re.IGNORECASE)
    sep = "||" if "||" in name else "|"
    parts = [p.strip() for p in name.split(sep)] if sep in name else [name.strip()]
    return parts, (parts[0] if parts else name.strip())
def fmt_opts(opts: List[str]) -> str:
    return opts[0] if len(opts) == 1 else "\n".join(f"{i+1}. {v}" for i, v in enumerate(opts))
def format_filename(template, title, chapter, chap_no):
    try:
        return template.format(
            title=sanitize(title)[:50],
            chapter=sanitize(chapter)[:30],
            chap_no=chap_no,
            chapter_no=chap_no,
            num=chap_no
        )
    except KeyError as e:
        log.warning(f"[UTIL] Format error: {e}, using default")
        return f"[BOT] {sanitize(title)[:50]} - {chap_no}"
    except Exception as e:
        log.warning(f"[UTIL] Format fail: {e}")
        return f"{sanitize(title)[:50]} - {chap_no}"
DEF_FNAME = "[BOT] {title} - {chap_no}"
