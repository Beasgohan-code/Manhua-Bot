
import aiohttp
import aiofiles
import logging
from pathlib import Path
log = logging.getLogger(__name__)
class Catbox:
    @staticmethod
    async def upload(file_path, session=None):
        url = "https://catbox.moe/user/api.php"
        try:
            async with aiofiles.open(file_path, "rb") as f:
                file_content = await f.read()
            _close = False
            if session is None:
                session = aiohttp.ClientSession()
                _close = True
            try:
                data = aiohttp.FormData()
                data.add_field("reqtype", "fileupload")
                data.add_field(
                    "fileToUpload",
                    file_content,
                    filename=Path(file_path).name,
                    content_type="application/octet-stream"
                )
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                }
                async with session.post(url, data=data, headers=headers) as resp:
                    if resp.status == 200:
                        return await resp.text()
                    else:
                        log.error(f"Catbox error: {resp.status}")
                        return None
            finally:
                if _close:
                    await session.close()
        except Exception as e:
            log.error(f"Catbox upload failed: {e}")
            return None
    @staticmethod
    async def download(url, dest_path, session=None, max_retries=3):
        import asyncio
        for attempt in range(max_retries):
            try:
                _close = False
                if session is None:
                    session = aiohttp.ClientSession()
                    _close = True
                try:
                    headers = {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                    }
                    async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                        if resp.status == 200:
                            Path(dest_path).parent.mkdir(parents=True, exist_ok=True)
                            async with aiofiles.open(dest_path, 'wb') as f:
                                await f.write(await resp.read())
                            return True
                        log.warning(f"Catbox download HTTP {resp.status} (attempt {attempt+1})")
                finally:
                    if _close:
                        await session.close()
            except Exception as e:
                log.warning(f"Catbox download error (attempt {attempt+1}): {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(1 * (attempt + 1))
        log.error(f"Catbox download failed after {max_retries} retries: {url}")
        return False
