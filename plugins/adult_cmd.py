from pyrogram import Client, filters
from database.db import db
from plugins.fsub import force_sub
from utils.ui import RichMessage, code, block

ADULT_KEYS = (
    "nhentai", "imhentai", "hentai", "h2r", "nh", "ih",
    "NHentai", "ImHentai", "Hentai2Read",
    "hiperdex", "hdx", "manga18", "m18", "allporn", "apc",
    "manhwa18", "district", "mdist", "manhwahub", "mhub",
    "asmhentai", "asmh", "manhwasusu", "msusu", "hentalk", "htalk",
    "doujin", "douj", "hotcomic", "hotc", "manhwahentai", "mhent",
    "pornhwa", "phwaz", "mangadass", "mdass", "manhwabuddy", "mbuddy",
    "HiperDex", "Manga18", "AllPorn", "Manhwa18", "MangaDistrict",
    "ManhwaHub", "AsmHentai", "ManhwaSusu", "Hentalk", "Doujins",
    "HotComics", "ManhwaHentai", "Pornhwaz", "MangaDass", "ManhwaBuddy",
    "ManhwaRead", "mread", "toonily",
)

def is_adult_source(name: str) -> bool:
    n = (name or "").lower()
    return any(k.lower() in n for k in ADULT_KEYS)

async def user_allows_adult(uid: int) -> bool:
    try:
        return bool(await db.get_cfg(uid, "adult", False))
    except Exception:
        return False

@Client.on_message(filters.command(["adult", "nsfw"]))
@force_sub
async def adult_cmd(c, m):
    uid = m.from_user.id
    args = m.command[1:] if len(m.command) > 1 else []
    if not args:
        on = await user_allows_adult(uid)
        return await m.reply(
            RichMessage("Adult sources", "🔞")
            .kv([("Status", code("ON" if on else "OFF"))])
            .section(
                "Usage",
                f"{code('/adult on')} — show nhentai / hiperdex / …\n"
                f"{code('/adult off')} — hide adult sources",
            )
            .tip("Must enable before adult sites appear in search.")
            .build()
        )
    arg = args[0].lower()
    if arg in ("on", "1", "true", "yes", "enable"):
        await db.set_cfg(uid, "adult", True)
        await m.reply(RichMessage("Adult sources", "🔞").success("Enabled. Visible in /search and /sources.").build())
    elif arg in ("off", "0", "false", "no", "disable"):
        await db.set_cfg(uid, "adult", False)
        await m.reply(RichMessage("Adult sources", "🔒").success("Disabled.").build())
    else:
        await m.reply(RichMessage("Adult sources", "🔞").warn(f"Use {code('/adult on')} or {code('/adult off')}").build())
