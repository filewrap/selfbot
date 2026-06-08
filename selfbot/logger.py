import logging
import asyncio
from telethon import TelegramClient

class AsyncTelegramHandler(logging.Handler):
    def __init__(self, client: TelegramClient, chat_id: str | int):
        super().__init__()
        self.client = client
        self.chat_id = chat_id

    def emit(self, record):
        try:
            msg = self.format(record)
            # Create a task to send the message asynchronously
            if self.client.loop.is_running():
                asyncio.create_task(self.send_message(msg))
        except Exception:
            self.handleError(record)

    async def send_message(self, text):
        try:
            await self.client.send_message(self.chat_id, f"**Log:**\n`{text}`")
        except Exception as e:
            # We don't want to cause recursive logging loops
            print(f"Failed to send log to telegram: {e}")

def setup_async_logger(client: TelegramClient, chat_id: str | int):
    logger = logging.getLogger()
    handler = AsyncTelegramHandler(client, chat_id)
    formatter = logging.Formatter("[ %(levelname).1s ] %(name)s: %(message)s")
    handler.setFormatter(formatter)

    # We only want to log INFO and above to Telegram so it doesn't spam too much
    handler.setLevel(logging.INFO)
    logger.addHandler(handler)
    return handler
