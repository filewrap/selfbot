import os
from dataclasses import dataclass


@dataclass
class Config:
    session: str = os.getenv("SESSION", "")
    bot_token: str = os.getenv("BOT_TOKEN", "")
    api_id: int = int(os.getenv("API_ID") or "2496")
    api_hash: str = os.getenv("API_HASH") or "8da85b0d5bfe62527e5b244c209159c3"
    app_version: str = os.getenv("APP_VERSION") or "2.2 K"
    device_model: str = os.getenv("DEVICE_MODEL") or "Chrome 148"
    channel_id: int = int(os.getenv("CHANNEL_ID") or "-1")


config = Config()
