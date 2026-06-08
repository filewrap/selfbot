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
    UpdateBotGuestChatQuery,
    UpdateBotNewBusinessMessage,
    UpdateBusinessBotCallbackQuery,
    UpdateBotInlineQuery,
    UpdateChannelParticipant,
    UpdateInlineBotCallbackQuery,
)

from config import config

from .execute import execute


@register(
    Raw(
        (
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
        UpdateBotGuestChatQuery
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


        # Commands: ?info, ?updatepfp, ?help
        case UpdateBotNewBusinessMessage(
            message=Message(
                id=message_id,
                message=str(message),
                from_id=PeerUser(user_id=_client._client.user_id),
            )
        ) if message and message.startswith("?"):
            cmd_parts = message.split(maxsplit=1)
            cmd = cmd_parts[0][1:].lower()

            if cmd == "info":
                await _client.delete_messages(update.message.peer_id, [message_id])
                try:
                    bot_entity = await _client._client.get_input_entity(_client.user_id)
                    results = await _client._client.inline_query(bot_entity, "info")
                    if results:
                        await results[0].click(update.message.peer_id)
                except Exception:
                    await _client.send_message(
                        update.message.peer_id,
                        "Info:",
                        buttons=[Button.inline("Hide", b"0")]
                    )

            elif cmd == "updatepfp":
                if update.reply_to_message and update.reply_to_message.media:
                    try:
                        file = await _client.download_media(update.reply_to_message.media, file=bytes)
                        if file:
                            from telethon.functions.photos import UploadProfilePhotoRequest
                            uploaded = await _client._client.upload_file(file, file_name="photo.jpg")
                            await _client._client(UploadProfilePhotoRequest(file=uploaded))
                    except Exception as e:
                        await update.respond(f"Error executing updatepfp: {e}")
                await _client.delete_messages(update.message.peer_id, [message_id])

            elif cmd == "help":
                await _client.delete_messages(update.message.peer_id, [message_id])
                entities = [MessageEntityPre(0, 10, "python")]
                text = "Help Menu\n\n- ?info: Gets info via inline query.\n- ?updatepfp: Updates profile photo from replied media.\n- ?help: Shows this menu."
                buttons = [[Button.inline("Delete", b"0"), Button.inline("Hide", b"0")]]
                await update.respond(text, formatting_entities=entities, buttons=buttons)


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

        case _:
            logging.info(f"Unhandled update: {update.__class__.__name__}")
            return
