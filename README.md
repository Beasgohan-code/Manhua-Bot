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

## Native Rich Messages (Bot API 10.1+)

Telegram introduced **Rich Messages** in Bot API 10.1 (June 2026), extended
through 10.3. These are not the classic five inline tags — they are real
structural blocks, so tables and headings no longer have to be faked inside
`<pre>`:

| Rich block | HTML | Classic equivalent |
|-----------|------|--------------------|
| Headings | `<h1>`…`<h6>` | bold text |
| **Real tables** | `<table bordered striped compact>` + `align` + `<caption>` | monospaced box-drawing |
| Lists / checkboxes | `<ul> <ol> <li> <input type=checkbox>` | `•` / `1.` / `☑` |
| Collapsible | `<details open><summary>` | expandable blockquote |
| Quote with credit | `<blockquote expandable><cite>` | blockquote |
| Pull quote | `<aside>` | italic |
| Divider / footer | `<hr/>` `<footer>` | `━━━` |
| Marked / sub / sup | `<mark> <sub> <sup>` | — |
| LaTeX | `<tg-math> <tg-math-block>` | — |
| Locale date/time | `<tg-time unix= format=>` | plain text |

`utils/richmsg.py` builds both representations at once:

```python
from utils.richmsg import RichDoc, send_rich

doc = (RichDoc()
       .heading("Download Complete", 1, "✅")
       .table(["Episode", "Quality", "Size"],
              [[1, "1080p", "412 MB"]],
              align=["r", "c", "r"], caption="Batch summary")
       .checklist([("Fetch", True), ("Upload", False)])
       .details("Engine log", "<p>yt-dlp: ok</p>")
       .quote("Best quarter ever.", credit="CEO", expandable=True))

await send_rich(chat_id, doc, reply_markup=kb, fallback_client=client)
```

`send_rich()` uses `sendRichMessage` through aiogram when available and
silently falls back to `doc.fallback()` — classic HTML with monospaced
tables — otherwise. Rich-only tags are stripped from the fallback, since
Telegram rejects a whole message containing `<p>` or `<table>` in normal
HTML mode.

Note: in rich HTML a bare newline is insignificant whitespace, so logical
breaks must be explicit `<br/>` — the builder handles this.

## Bot API 10.3 reply-markup features

| Feature | Support |
|---------|---------|
| `disabled` buttons | native via aiogram; inert no-op callback on MTProto |
| `style="primary"/"danger"/"success"` | native on both backends |
| `style="link"` (borderless, 10.3) | Bot API path; falls back to default on MTProto |
| `copy_text` | native on both |
| `force_reply` on inline keyboards (10.3) | `Keyboard(force_reply=True)` |
| `icon_custom_emoji_id` | native on both |

## Download queue

`services/queue.py` was a dict that only grew. Two real bugs:
**nothing ever set `failed`**, so a crashed download stayed `running`
forever and held the user's concurrency slot; and finished items were
never pruned, an unbounded memory leak.

Now:

- Lifecycle `pending → running → done | failed | cancelled`
- **Retention**: cap + TTL, and active work is never evicted
- **Stale recovery**: a `running` item with no progress for 30 min is
  failed automatically (swept every 5 min by the scheduler)
- **Per-user concurrency** via `reserve()` / `release()`
- Live `progress` + `eta`, `position()` in queue, `stats()`
- `/queue` shows a live table with progress, ETA, per-task **Cancel**
  buttons, a status summary and a collapsible error section

## Search quality

`services/search_util.py`:

- **Relevance scoring** — token overlap + sequence similarity + source
  trust, replacing the old 4-level bucket sort
- **Cross-source de-duplication** — the same title from six sites becomes
  one row labelled "Naruto · 6 sources", inheriting any cover art the
  winning entry lacked
- **Search history** — `/vhistory` lists recent queries with hit counts
  and one-tap repeat

## Bot API transport (services/tgapi.py)

Kurigram stays the runtime (handlers, MTProto uploads). One shared aiogram
`Bot` acts as a transport for the calls MTProto cannot make:

| Call | Why aiogram |
|------|-------------|
| `sendRichMessage` | not in MTProto |
| `DisabledButton` | not in MTProto |
| `force_reply` on inline keyboards | Bot API 10.3 |
| `EphemeralMessageParameters` | per-user messages in groups |
| `message_effect_id` | animated effects |

Safety properties, all covered by the audit:

- **Single shared session** — no per-call `Bot()` (the old code leaked an
  aiohttp connector on every send)
- **Circuit breaker** — after 3 consecutive transport errors the Bot API
  path is disabled and sends go straight to Kurigram, instead of paying a
  full connection timeout every time. It re-enables on the next success.
- **Startup probe** — `getMe` at boot logs whether rich messages are live
- **Clean shutdown** — the session is closed in `bot.py`'s `finally`

## Testing

```bash
python tools/audit.py         # 14 stages
python tools/extract_test.py  # per-source extraction
```

`tools/extract_test.py` complements the fuzzer. Fuzzing proves malformed
input cannot crash a source — but a scraper with *broken selectors* also
passes that, since `[]` is the correct answer for garbage. The extraction
harness feeds each scraper a realistic, well-formed response and requires
it not to raise. That distinction found three real crashes:

- `DemonicScans` — assumed every `<a>` had `href`, an `<img>` and nested
  `<div>`s; also scraped nav/footer links into bogus results
- `Manhuaplus` — `pop("name")` on entries lacking it; `urljoin()` with a
  non-string cover
- `AllAnime` — GraphQL `data` can be a list, not a dict
