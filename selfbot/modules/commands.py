import aiohttp
from telethon import TelegramClient, functions
from telethon.types import Message, ChatBannedRights

COMMANDS = {}

def register_command(name):
    def decorator(func):
        COMMANDS[name] = func
        return func
    return decorator

@register_command("help")
async def cmd_help(_app: TelegramClient, _bot: TelegramClient, _update, _args: str, _replied: Message):
    commands = ", ".join(f"?{k}" for k in COMMANDS.keys())
    return f"**Available commands:**\n{commands}"

@register_command("updatepfp")
async def cmd_updatepfp(app: TelegramClient, bot: TelegramClient, _update, args: str, replied: Message):
    """?updatepfp <reply or url>"""
    if replied and replied.media:
        # We need to use app to download the media if bot can't, but let's try with bot first since it might be a business message
        try:
            file = await app.download_media(replied.media, file=bytes)
        except Exception:
            file = await bot.download_media(replied.media, file=bytes)

        if file:
            uploaded = await app.upload_file(file)
            await app(functions.photos.UploadProfilePhotoRequest(file=uploaded))
            return "Profile picture updated from reply."
        return "Failed to download media from reply."
    elif args:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(args) as resp:
                    if resp.status == 200:
                        file_data = await resp.read()
                        uploaded = await app.upload_file(file_data)
                        await app(functions.photos.UploadProfilePhotoRequest(file=uploaded))
                        return "Profile picture updated from URL."
                    else:
                        return f"Failed to download image from URL. Status: {resp.status}"
        except Exception as e:
            return f"Error downloading from URL: {e}"
    else:
        return "Please reply to an image or provide a URL."

@register_command("block")
async def cmd_block(app: TelegramClient, _bot: TelegramClient, update, _args: str, replied: Message):
    user_id = None
    if replied:
        user_id = replied.sender_id
    else:
        user_id = update.message.peer_id

    if user_id:
        await app(functions.contacts.BlockRequest(id=user_id))
        return f"Blocked user."
    return "Could not determine user to block."

@register_command("ban")
async def cmd_ban(app: TelegramClient, _bot: TelegramClient, update, _args: str, replied: Message):
    if not replied:
        return "Reply to a user to ban."
    chat_id = update.message.peer_id
    try:
        await app(functions.channels.EditBannedRequest(
            channel=chat_id,
            participant=replied.sender_id,
            banned_rights=ChatBannedRights(until_date=None, view_messages=True)
        ))
        return "Banned user."
    except Exception as e:
        return f"Failed to ban user: {e}"

@register_command("clear")
async def cmd_clear(app: TelegramClient, _bot: TelegramClient, update, _args: str, _replied: Message):
    chat_id = update.message.peer_id
    try:
        await app(functions.messages.DeleteHistoryRequest(
            peer=chat_id,
            max_id=0,
            just_clear=True,
            revoke=True
        ))
        return "Cleared history."
    except Exception as e:
        return f"Failed to clear history: {e}"

@register_command("report")
async def cmd_report(app: TelegramClient, _bot: TelegramClient, update, _args: str, replied: Message):
    if not replied:
        return "Reply to a message to report."
    chat_id = update.message.peer_id
    try:
        await app(functions.messages.ReportRequest(
            peer=chat_id,
            id=[replied.id],
            option=b'spam',
            message="Spam"
        ))
        return "Reported message as Spam."
    except Exception as e:
        return f"Failed to report message: {e}"

async def process_command(update, text: str, replied: Message = None):
    text = text.lstrip("?").strip()
    parts = text.split(" ", 1)
    cmd_name = parts[0].lower()
    args = parts[1] if len(parts) > 1 else ""

    if cmd_name in COMMANDS:
        app = update._client._client
        bot = update._client
        try:
            res = await COMMANDS[cmd_name](app, bot, update, args, replied)
            return str(res)
        except Exception as e:
            return f"Error executing {cmd_name}: {e}"
    else:
        return f"Unknown command: {cmd_name}"
