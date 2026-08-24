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
