
from pyrogram import Client, filters
from plugins.settings.shared import user_states, temp_data
@Client.on_callback_query(filters.regex(r"^st_th_"))
async def ask_sub_thumb(c, q):
    uid = q.from_user.id
    sid = q.data.replace("st_th_", "")
    user_states[uid] = "await_sub_thumb"
    temp_data[uid] = sid
    await q.message.edit(
        f"<b>⊕ Set Custom Thumbnail</b>\n"
        f"<b>ID:</b> <code>{sid}</code>\n\n"
        "<blockquote>Send an image to use as a custom thumbnail for this manga.</blockquote>\n\n"
        "<i>Or /cancel</i>"
    )
