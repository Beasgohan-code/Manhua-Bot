# Manhua-Bot - outbound webhook / Discord export

from __future__ import annotations
import logging
from typing import Optional

import aiohttp

log = logging.getLogger(__name__)


async def post_webhook(
    url: str,
    *,
    title: str,
    chapter: str,
    source: str = "",
    link: Optional[str] = None,
    cover: Optional[str] = None,
    extra: Optional[dict] = None,
) -> bool:
    """
    Send a chapter update to a Discord webhook or generic JSON webhook.
    Discord: expects discord.com/api/webhooks/...
    Generic: posts JSON {title, chapter, source, link, cover, ...}
    """
    if not url:
        return False
    try:
        is_discord = "discord.com/api/webhooks" in url or "discordapp.com/api/webhooks" in url
        async with aiohttp.ClientSession() as session:
            if is_discord:
                embed = {
                    "title": f"{title}",
                    "description": f"**Chapter:** {chapter}\n**Source:** {source or 'n/a'}",
                    "color": 0x5865F2,
                }
                if link:
                    embed["url"] = link
                if cover:
                    embed["thumbnail"] = {"url": cover}
                if extra:
                    embed["description"] += "\n" + "\n".join(f"**{k}:** {v}" for k, v in extra.items())
                payload = {
                    "content": f"📖 New chapter: **{title}** — {chapter}",
                    "embeds": [embed],
                }
            else:
                payload = {
                    "title": title,
                    "chapter": chapter,
                    "source": source,
                    "link": link,
                    "cover": cover,
                    **(extra or {}),
                }
            async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status >= 400:
                    body = await resp.text()
                    log.warning(f"[WEBHOOK] {resp.status}: {body[:200]}")
                    return False
                return True
    except Exception as e:
        log.error(f"[WEBHOOK] failed: {e}")
        return False
