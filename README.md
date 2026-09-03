# Manhua-Bot

High-performance Telegram bot for automatic **Manhua / Manga / Manhwa** (and adult) chapter tracking, downloading and channel mirroring.

Forked & heavily enhanced from the original auto-manga-chapter-update-bot architecture.

## What's new in this build

- **PostgreSQL** backend (asyncpg) instead of MongoDB
- Extra adult sources: **nhentai**, **imhentai**
- **Direct download** (`/dl` + ⬇️ buttons on chapters)
- Richer chapter keyboards (Track + Download)
- Cleaner configuration via `DATABASE_URL`
- Same core features: multi-source search, auto chapter check, PDF/CBZ generation, branding, force-sub, broadcast, etc.
- Rich HTML captions / structured messages where used

## Features

- Auto-checks 50+ sources on a schedule
- Clean PDF / CBZ chapter files
- Watermarks, promo banners, custom captions
- Smart multi-source fallback
- Fast search + track
- Deploy on VPS / Docker / Heroku-style

## Setup

1. Clone / extract this repo
2. `pip install -r requirements.txt`
3. Copy `.env.example` → `.env` and fill:
   - `API_ID` / `API_HASH` (my.telegram.org)
   - `BOT_TOKEN` (@BotFather)
   - `DATABASE_URL` = `postgresql://user:pass@host:5432/dbname`
   - `OWNER_ID`
4. Create the PostgreSQL database (schema is auto-created on first run)
5. `python bot.py`

## Environment

```env
API_ID=
API_HASH=
BOT_TOKEN=
DATABASE_URL=postgresql://manhua:password@localhost:5432/manhua_bot
OWNER_ID=
LOG_GROUP=0
FSUB_CHANNELS=
```

## Notes

- Adult sources (nhentai) are included. Use responsibly and respect Telegram ToS / local laws.
- Core scraper + plugin architecture kept compatible with the original design.
- For production, put the bot behind a process manager (systemd / pm2 / docker).

## Credits

Original architecture inspired by the public auto-manga-chapter-update-bot project.  
This package is a rewritten PostgreSQL edition focused on Manhua tracking.


## Commands

| Command | Description |
|---------|-------------|
| `/start` | Welcome / status |
| `/search <name>` | Search across sources |
| `/dl <source> <id> [ch]` | Direct download (no track) |
| `/sources` | List loaded sites |
| `/list` | Your tracked series |
| `/settings` | Style, watermark, file type… |

**File types** (in settings): `pdf` · `cbz` · **`links`** (posts raw image URLs)

## Advanced feature ideas (roadmap)

1. **Multi-channel routing** – different series → different channels by tag  
2. **RSS / Webhook export** – push updates to Discord or custom webhook  
3. **OCR chapter titles** – fix messy numbering via light OCR  
4. **User quotas** – daily DL limits per non-owner user  
5. **ZIP mirror host** – auto-upload CBZ to Gofile / Catbox and post link only  
6. **Smart merge** – if two sources release same chapter, pick best scan quality  
7. **Telegram native albums** – optional media-group of pages (small chapters)  
8. **Poll “rate this chapter”** after post (Bot API polls)  
9. **Auto-translate titles** via optional API  
10. **Docker Compose** one-file deploy with Postgres  

## Health check notes

- All Python modules syntax-checked  
- Mongo collection calls removed from plugins (PSQL only)  
- `get_cfg` / `set_cfg` aliases present for original settings UI  
- Schema auto-migrates on first `db.connect()`


## Docker

```bash
cp .env.example .env   # fill API_ID, API_HASH, BOT_TOKEN, OWNER_ID
docker compose up -d --build
```

Postgres is started automatically; `DATABASE_URL` is injected for the bot service.

## Webhook / Discord

Set globally in `.env`:

```env
WEBHOOK_URL=https://discord.com/api/webhooks/...
```

Or per-owner in bot:

```text
/webhook https://discord.com/api/webhooks/...
/webhook clear
```

## Album mode & polls

```env
ALBUM_MAX_PAGES=10
ENABLE_RATE_POLL=0
```

Bot commands:

```text
/album 8          # chapters with ≤8 pages → media group
/album 0          # disable
/poll on          # rate poll after posts
/poll off
```

File type **Links** still available in settings (image URL list instead of PDF).


## Features
- `/queue` / `/clean_tasks` — download queue
- `/subs` / `/unsubs` — manage tracking
- `/merge N` — merge N chapters into one PDF
- `/pdfpass` — password-protect PDFs
- Premium: `/add` `/del` `/premium_users` `/del_expired`
- `/help` — full command list
# Manhua-Bot

## Anime / Hentai video downloader

Video support alongside manga, with a shared adult gate (`/adult on`).

### Commands

| Command | Description |
|---------|-------------|
| `/anime <name>` | Search SFW anime sources |
| `/hentai <name>` | Search adult sources (needs `/adult on`) |
| `/vsearch <name>` | Search **all** allowed video sources at once |
| `/vdl <src> <id> [1-5]` | Direct / range episode download |
| `/vsources` | Video site list |
| `/vengine` | Engine + hanime-plugin diagnostics |
| `/usettings` | Your upload settings (video/document, thumbnail, metadata) |

### Video sources

**Anime:** AllAnime · AnimePahe · GogoAnime · AnimeKai

**Adult:** HAnime.tv · Hentai City · Hentai Ocean · Hentai.sh · Hentaverse ·
My Hentai Movie · OnlyHentaiStuff · WatchHentai · HStream.moe · Oppai.stream

### Engine

Logic adapted from [Hstream-TG](https://github.com/zenin-373/Hstream-TG),
[Hanime-Downloader](https://github.com/MatrixRobots/Hanime-Downloader) and the
[auto-manga-chapter-update-bot](https://github.com/KunalG932/auto-manga-chapter-update-bot)
search architecture:

- **Format fallback ladder** — never fails because one format string missed
- **aria2c** external downloader (16 connections) when installed
- **hanime-plugin** yt-dlp extractor pack: HAnime.tv, HStream, Oppai.stream,
  HentaiHaven, HentaiMama, Hanime.red, OHentai
- **Subtitle support** — English `.ass` discovery + soft-mux into MKV
- **Container sniffing** — magic-byte detection so raw TS is never uploaded
  mislabelled as `.mp4`
- **Live progress** — search shows `sources 7/14` with a bar; downloads show
  percent, size, speed and ETA
- **Parallel "search all sources"** with per-source timeout isolation

### Extra system dependencies

```bash
apt install ffmpeg aria2      # ffmpeg required for merge/metadata/subtitles
pip install -r requirements.txt
```

Run `/vengine` in the bot to confirm what is active.

## Modern Bot API UI (Kurigram + aiogram hybrid)

`utils/tgui.py` builds keyboards declaratively and renders them to either
backend, because neither one alone covers the whole Bot API surface:

| Feature | Kurigram | aiogram 3.31 |
|---------|----------|--------------|
| `style="primary"` / `danger` / `success` | ✅ native MTProto | ✅ |
| `copy_text` (tap to copy) | ✅ | ✅ |
| `icon_custom_emoji_id` | ✅ | ✅ |
| **`disabled` buttons** | ❌ emulated | ✅ native |

```python
from utils.tgui import Btn, Keyboard, Card, PRIMARY, DANGER, SUCCESS

kb = (Keyboard()
      .row(Btn("Download", "dl_1", style=PRIMARY),
           Btn("Delete", "rm_1", style=DANGER))
      .row(Btn("◂ Prev", "p_0", disabled=True),      # inert on MTProto
           Btn("Copy ID", copy="abc123")))
await m.reply(card.build(), reply_markup=kb.render())
```

On Kurigram a `disabled` button routes to an inert no-op callback (MTProto has
no disabled flag), so it behaves correctly either way.

### Rich formatting helpers

- `heading(text, level)` — visual H1/H2/H3
- `table(headers, rows, align=[...])` — box-drawn tables, emoji-width aware
- `quote(text, expandable=True)` — collapsible blockquotes (Bot API 7.4)
- `spoiler()`, `emoji(id)` (premium custom emoji), `pre(code, "python")`
- `Card()` builder for consistent message layout

## Health check

```bash
python tools/audit.py     # full static audit
```

Or `/audit` in the bot. Verifies syntax, plugin imports, every scraper
interface, duplicate commands, callback shadowing, HTML legality and engine
availability.

### Scraper compatibility

`sources/compat.py` normalises the two scraper generations. 34 sources use
`get_manga()/get_chapter()`; 35 older ones use `get_chapters()/get_pictures()`.
`/dl` previously only called `get_manga()`, so **direct download silently
failed on those 35 sources** (Comick, Asura, Batoto, FlameComics, MangaPark,
WeebCentral and more) — now fixed.

## RichMessage: tables, headings, columns

`utils.ui.RichMessage` is the shared message builder and now renders real
tables, headings and multi-column layouts. It delegates to the
display-width-aware engine in `utils/tgui.py`, so emoji and CJK cells no
longer break column alignment.

```python
from utils.ui import RichMessage

msg = (RichMessage("Health Dashboard", "📊")
       .heading("Runtime", "⚙")
       .table(["Metric", "Value"],
              [["Uptime", "3h 12m"], ["Python", "3.11.2"]])
       .heading("Chapters", "📚")
       .columns([f"Ch {i}" for i in range(1, 13)], cols=4)
       .progress(72, "downloading")
       .field("Quality", "1080p")
       .tip("Use /audit for details"))
await m.reply(msg.build())
```

| Method | Purpose |
|--------|---------|
| `.table(headers, rows, align=["l","r","c"])` | bordered table, emoji-safe |
| `.columns(items, cols=3)` | flat list in aligned columns |
| `.heading(text, emoji, level)` | section heading |
| `.progress(pct, label)` | progress bar |
| `.field(label, value)` | single key/value line |
| `.divider()` | horizontal rule |

Applied to `/sources`, `/stats`, `/subs`, `/queue`, `/vsources`, `/vengine`
and `/audit`. Pass `borders=False` for a lightweight variant.

## Verification

`tools/audit.py` (or `/audit`) runs ~1100 automated checks:

- syntax, plugin imports, scraper interfaces, duplicate codes
- **offline fuzzing**: every source is fed 10 malformed responses
  (garbage HTML, truncated markup, 403 pages, wrong JSON shapes, nulls)
  to prove a bad upstream reply cannot crash the aggregated search
- duplicate commands, callback-prefix shadowing
- HTML legality/balance/escaping and double-escape detection
- engine + hanime-plugin availability
