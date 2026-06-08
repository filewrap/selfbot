import asyncio
import logging
import re

from aiohttp import ClientSession, TCPConnector
#from pytgcalls import PyTgCalls
from telethon import TelegramClient
from telethon.errors import FloodWaitError
from telethon.events import Raw, StopPropagation
from telethon.functions import account
from telethon.sessions import StringSession
from telethon.types import (
    BusinessBotRights,
    Channel,
    Chat,
    InputBusinessBotRecipients,
    UpdateBotBusinessConnect,
    UpdateBotGuestChatQuery
)

from config import config
from .logger import setup_async_logger

from .modules import modules

logging.basicConfig(
    format="[ %(levelname).1s ] %(name)s: %(message)s", level=logging.INFO
)


async def _handshake(bot: TelegramClient, app: TelegramClient, username: str) -> None:
    async with bot.conversation(app.user_id) as conversation:
        await app(
            account.UpdateConnectedBotRequest(
                bot=username,
                recipients=InputBusinessBotRecipients(
                    existing_chats=True,
                    new_chats=True,
                    contacts=True,
                    non_contacts=True,
                    exclude_selected=False,
                ),
                deleted=False,
                rights=BusinessBotRights(
                    reply=True,
                    read_messages=True,
                    delete_sent_messages=True,
                    delete_received_messages=True,
                    edit_name=True,
                    edit_bio=True,
                    edit_profile_photo=True,
                    edit_username=True,
                    manage_stories=True,
                ),
            )
        )
        update = await conversation.wait_event(Raw)
        if isinstance(update, UpdateBotBusinessConnect):
            bot.connection_id = update.connection.connection_id
            logging.info(f"{update.__class__.__name__}: ID# {bot.connection_id}")

        logging.info(f"{update.__class__.__name__}: {update.stringify()}")


async def _main() -> None:
    bot = TelegramClient("bot", config.api_id, config.api_hash)
    bot.parse_mode = None

    for module in modules:
        for attr in dir(module):
            obj = getattr(module, attr)
            if hasattr(obj, "__tl.handlers"):
                bot.add_event_handler(obj)
            elif hasattr(obj, "_patch"):
                for cls in obj._patch:
                    setattr(cls, obj.__name__.removeprefix("_"), obj)

                delattr(obj, "_patch")


    bot.http = ClientSession(connector=TCPConnector(ssl=False))
    async with bot.http:
        app = TelegramClient(
            StringSession(config.session),
            config.api_id,
            config.api_hash,
            app_version=config.app_version,
            device_model=config.device_model,
            receive_updates=False
        )
        await app.start()
        app_me = await app.get_me()
        app.user_id = app_me.id
        bot._client = app

        await bot.start(bot_token=config.bot_token)

        me = await bot.get_me()
        bot.user_id = me.id
        setup_async_logger(app, config.log_channel)
        bot.username = re.compile(rf"(?i)^@{me.username}\s*")
        bot._bot = bot
        logging.info("Signed in as @%s (id=%s)", me.username, me.id)
        logging.info("client: %s (id=%s)", app_me.first_name, app_me.id)
        logging.info(
            "bot.user_id %s\n"
            "_client.user_id %s\n",
            bot.user_id, bot._client.user_id
        )

        await _handshake(bot, app, me.username)

        await bot.run_until_disconnected()


def run() -> None:
    try:
        asyncio.run(_main())
    except BaseException as e:
        logging.critical(f"{e.__class__.__name__}: {e}")
