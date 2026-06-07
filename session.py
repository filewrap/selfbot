from telethon.sessions import StringSession
from telethon.sync import TelegramClient
from telethon.types import MessageEntityCode

from config import config

with TelegramClient(
    StringSession(),
    config.api_id,
    config.api_hash,
    app_version=config.app_version,
    device_model=config.device_model,
    receive_updates=False,
) as client:
    session = client.session.save()
    if not client.is_bot():
        client.send_message(
            "me", session, formatting_entities=[MessageEntityCode(0, len(session))]
        )

    print(f"\n\n{session}\n\n")
