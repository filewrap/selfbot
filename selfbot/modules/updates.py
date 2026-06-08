import asyncio
import contextlib
import struct
import logging

from telethon import Button
from telethon.events import Raw, register
from telethon.functions import channels
from telethon.types import (
    ChannelParticipant,
    ChatBannedRights,
    InputBotInlineMessageID,
    Message,
    MessageEntityPre,
    MessageMediaDocument,
    MessageMediaPhoto,
    PeerUser,
    UpdateBotBusinessConnect,
    UpdateBotGuestChatQuery,
    UpdateBotNewBusinessMessage,
    UpdateBusinessBotCallbackQuery,
    UpdateBotInlineQuery,
    UpdateChannelParticipant,
    UpdateInlineBotCallbackQuery,
)

from config import config

from .execute import execute
from .commands import process_command


@register(
    Raw(
        (
            UpdateBotBusinessConnect,
    UpdateBotGuestChatQuery,
            UpdateBotNewBusinessMessage,
            UpdateBusinessBotCallbackQuery,
            UpdateChannelParticipant,
            UpdateInlineBotCallbackQuery,
        )
    )
)
async def updates(
    update: (
        UpdateBotBusinessConnect
        | UpdateBotGuestChatQuery
        | UpdateBotNewBusinessMessage
        | UpdateBusinessBotCallbackQuery
        | UpdateChannelParticipant
        | UpdateInlineBotCallbackQuery
    ),
) -> None:
    _client = update._client
    me = await _client.get_me()
    logging.info(
        f"Info:\n"
        f"Is bot: {await _client.is_bot()}\n"
        f"id: {me.id} | {me.first_name}\n"
        f"fixed user_id: {_client.user_id}\n")

    match update:
        # Secretary bot notification
        case UpdateBotBusinessConnect(
            connection=connection
        ):
            logging.info(f"Bot was added as a secretary bot! Connection ID: {connection.connection_id}")
        # Guest Chat Query - works in ANY chat type (PMs, groups, channels)
        case UpdateBotGuestChatQuery() as query if (
            getattr(getattr(query.message, "from_id", None), "user_id", None) == _client._client.user_id
            or getattr(query.message, "from_id", None) is None
        ):
            msg_id = await update.answer(
                "article",
                "Guest Chat Result",
                text="<pre><code class='language-'python''>...</code></pre>",
                parse_mode="html",
            )
            await execute(update, msg_id)

        # Business: Save self-destructing media from replies
        case UpdateBotNewBusinessMessage(
            message=Message(from_id=PeerUser(user_id=_client._client.user_id), message="\U0001f440"),
            reply_to_message=Message(
                id=reply_to_message_id,
                peer_id=PeerUser(user_id=user_id),
                media=MessageMediaPhoto(ttl_seconds=ttl_seconds)
                | MessageMediaDocument(ttl_seconds=ttl_seconds) as media,
            ),
        ) if ttl_seconds:
            file = await _client.download_media(media)
            await _client.send_file(
                _client._client.user_id,
                file,
                buttons=Button.url(
                    "Open Message",
                    f"tg://openmessage?user_id={user_id}&message_id={reply_to_message_id}",
                ),
            )

        # Business: Handle custom commands
        case UpdateBotNewBusinessMessage(
            message=Message(
                id=message_id,
                message=str(message),
                from_id=PeerUser(user_id=_client._client.user_id),
            ),
            reply_to_message=reply_to_message
        ) if message and message.startswith("?"):
            res = await process_command(update, message, reply_to_message)
            await update.respond(res, reply_to=message_id)

        # Business: Execute command ending with #
        case UpdateBotNewBusinessMessage(
            message=Message(
                id=message_id,
                message=str(message),
                from_id=PeerUser(user_id=_client._client.user_id),
            )
        ) if message and message.endswith("#"):
            respond = await update.respond(
                "...", entities=[MessageEntityPre(0, 3, "python")], reply_to=message_id
            )
            await execute(update, respond.updates[0].message.id)

        # Business callback: "Raise" (cancel running task) or "Hide" (delete message)
        case UpdateBusinessBotCallbackQuery(
            user_id=_client._client.user_id,
            connection_id=_client.connection_id,
            message=Message(id=message_id),
            data=b"0",
        ):
            for task in asyncio.all_tasks():
                if task.get_name() == f"Exec-{message_id}":
                    task.cancel()
                    return

            await update.delete()

        # Channel participant: ban new joiners
        case UpdateChannelParticipant(
            channel_id=config.channel_id as channel_id,
            new_participant=ChannelParticipant(user_id=user_id),
        ) if (user_id != _client._client.user_id):
            args = await asyncio.gather(
                _client.get_input_entity(channel_id), _client.get_input_entity(user_id)
            )
            await _client(
                channels.EditBannedRequest(
                    *args, ChatBannedRights(until_date=None, view_messages=True)
                )
            )
            await _client(
                channels.EditBannedRequest(*args, ChatBannedRights(until_date=None))
            )

        # Inline callback: "Raise" (cancel running task) or "Hide" (delete message)
        case UpdateInlineBotCallbackQuery(
            msg_id=msg_id, user_id=_client._client.user_id, data=b"0"
        ):
            for task in asyncio.all_tasks():
                if isinstance(msg_id, InputBotInlineMessageID):
                    match_name = f"Exec-{msg_id.access_hash}"
                else:
                    match_name = f"Exec-{msg_id.id}"
                if task.get_name() == match_name:
                    task.cancel()
                    return

            if isinstance(msg_id, InputBotInlineMessageID):
                message_id, chat_id = struct.unpack("<ii", struct.pack("<q", msg_id.id))
            else:
                message_id, chat_id = msg_id.id, msg_id.owner_id

            pts = 0
            with contextlib.suppress(Exception):
                peer_id = await _client.get_input_entity(chat_id)
                affects = await _client.delete_messages(peer_id, message_id)
                if affects:
                    pts += affects[0].pts_count

            if not pts:
                await _client.edit_message(
                    msg_id, "\u2060", buttons=Button.switch_inline("Call", "\n", True)
                )

        case UpdateBotInlineQuery(query=str(q)) if q == "info":
            from telethon.tl.types import InputBotInlineResult, InputBotInlineMessageText, ReplyInlineMarkup, KeyboardButtonCallback, KeyboardButtonRow
            from telethon.functions.messages import SetInlineBotResultsRequest
            import random

            # send back a result
            result = InputBotInlineResult(
                id=str(random.randint(0, 1000000)),
                type="article",
                title="Info",
                send_message=InputBotInlineMessageText(
                    message="Information about the bot/user...",
                    no_webpage=True,
                    reply_markup=ReplyInlineMarkup(
                        rows=[
                            KeyboardButtonRow(
                                buttons=[
                                    KeyboardButtonCallback(text="Delete", data=b"0"),
                                    KeyboardButtonCallback(text="Hide", data=b"0")
                                ]
                            )
                        ]
                    )
                )
            )
            await _client(SetInlineBotResultsRequest(
                query_id=update.query_id,
                results=[result],
                cache_time=0
            ))

        case _:
            logging.info(f"Unhandled update: {update.__class__.__name__}")
            return
