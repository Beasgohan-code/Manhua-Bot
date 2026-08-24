
import sys
import traceback
import io
import asyncio
from pyrogram import Client, filters
from config import Config
from database.db import db
class OutputCapturer:
    def __init__(self):
        self.stdout = io.StringIO()
        self.stderr = io.StringIO()
    def __enter__(self):
        self._old_stdout = sys.stdout
        self._old_stderr = sys.stderr
        sys.stdout = self.stdout
        sys.stderr = self.stderr
        return self
    def __exit__(self, exc_type, exc_val, exc_tb):
        sys.stdout = self._old_stdout
        sys.stderr = self._old_stderr
@Client.on_message(filters.command("eval") & filters.user(Config.OWNER_ID))
async def eval_cmd(client, message):
    if len(message.command) < 2:
        return await message.reply_text("<b>Usage:</b> <code>/eval &lt;python_code&gt;</code>")
    status = await message.reply_text("<i>Evaluating...</i>")
    code = message.text.split(maxsplit=1)[1]
    env = {
        "client": client,
        "message": message,
        "db": db,
        "Config": Config,
        "asyncio": asyncio,
        "c": client,
        "m": message,
    }
    indented_code = "\n".join(f"    {line}" for line in code.splitlines())
    func_code = f"async def __ex():\n{indented_code}"
    try:
        with OutputCapturer() as capturer:
            exec(func_code, env)
            func = env["__ex"]
            result = await func()
        stdout = capturer.stdout.getvalue()
        stderr = capturer.stderr.getvalue()
    except Exception:
        result = traceback.format_exc()
        stdout = ""
        stderr = ""
    final_output = ""
    if stdout:
        final_output += f"<b>Stdout:</b>\n<code>{stdout}</code>\n\n"
    if stderr:
        final_output += f"<b>Stderr:</b>\n<code>{stderr}</code>\n\n"
    if result is not None:
        final_output += f"<b>Result:</b>\n<code>{result}</code>"
    if not final_output:
        final_output = "<b>Success (No output)</b>"
    if len(final_output) > 4096:
        with io.BytesIO(final_output.encode()) as doc:
            doc.name = "eval_output.txt"
            await message.reply_document(doc, caption="Evaluation Output")
            await status.delete()
    else:
        await status.edit(final_output)
@Client.on_message(filters.command("sh") & filters.user(Config.OWNER_ID))
async def sh_cmd(client, message):
    if len(message.command) < 2:
        return await message.reply_text("<b>Usage:</b> <code>/sh &lt;shell_command&gt;</code>")
    status = await message.reply_text("<i>Executing...</i>")
    cmd = message.text.split(maxsplit=1)[1]
    try:
        proc = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        output = (stdout.decode() + stderr.decode()).strip()
    except Exception as e:
        output = str(e)
    if not output:
        output = "Command executed with no output."
    if len(output) > 4096:
        with io.BytesIO(output.encode()) as doc:
            doc.name = "sh_output.txt"
            await message.reply_document(doc, caption="Shell Output")
            await status.delete()
    else:
        await status.edit(f"<code>{output}</code>")
