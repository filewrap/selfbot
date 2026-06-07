from telethon import TelegramClient
from telethon.custom import InlineBuilder
from telethon.functions import InvokeWithBusinessConnectionRequest, messages
from telethon.types import (
    InputBotInlineMessageID,
    InputBotInlineMessageID64,
    InputMediaDocumentExternal,
    InputMediaPhotoExternal,
    InputMediaUploadedDocument,
    InputMediaUploadedPhoto,
    InputPeerUser,
    InputReplyToMessage,
    UpdateBotGuestChatQuery,
    UpdateBotNewBusinessMessage,
    UpdateBusinessBotCallbackQuery,
    Updates,
)
from telethon.utils import get_input_media

from selfbot.util import patch


@patch(TelegramClient)
async def _invoke(
    self: TelegramClient, query: object, connection_id: str = None
) -> Updates:
    return await self(
        InvokeWithBusinessConnectionRequest(
            connection_id if connection_id else self.connection_id, query
        )
    )


@patch(UpdateBotGuestChatQuery)
async def _answer(
    self: UpdateBotGuestChatQuery, value: str, *args, **kwargs
) -> InputBotInlineMessageID | InputBotInlineMessageID64:
    builder = InlineBuilder(self._client)
    match value:
        case "article":
            result = await builder.article(*args, **kwargs)
        case "photo":
            result = await builder.photo(*args, **kwargs)
        case "document":
            result = await builder.document(*args, **kwargs)
        case "game":
            result = await builder.game(*args, **kwargs)
        case _:
            raise ValueError(value)

    return await self._client(
        messages.SetBotGuestChatResultRequest(self.query_id, result)
    )


@patch(UpdateBotNewBusinessMessage)
@patch(UpdateBusinessBotCallbackQuery)
async def _respond(self: UpdateBotNewBusinessMessage, *args, **kwargs) -> Updates:
    entity = await self._client.get_input_entity(self.message.peer_id)
    kwargs = await _kwargs(self._client, kwargs, entity)

    if args and isinstance(args[0], int):
        match args:
            case (_, bool(), bool(), str()):
                pass
            case (_, bool(), str()):
                args = args[0], args[1], None, args[2]
            case (_, str()):
                args = args[0], None, None, args[1]
            case (_,):
                args = args[0], None, None, None
            case _:
                raise TypeError(str(args))

        return await self._client.invoke(
            messages.EditMessageRequest(entity, *args, **kwargs)
        )

    if "media" in kwargs:
        args = kwargs.pop("media"), "" if not args else args[0]
        return await self._client.invoke(
            messages.SendMediaRequest(entity, *args, **kwargs)
        )

    return await self._client.invoke(
        messages.SendMessageRequest(entity, *args, **kwargs)
    )


@patch(UpdateBotNewBusinessMessage)
@patch(UpdateBusinessBotCallbackQuery)
async def _delete(
    self: UpdateBotNewBusinessMessage | UpdateBusinessBotCallbackQuery,
    message_id: list = None,
    revoke: bool = True,
) -> list:
    return await self._client.invoke(
        messages.DeleteMessagesRequest(
            message_id if message_id else [self.message.id], revoke
        )
    )


async def _kwargs(client: TelegramClient, kwargs: dict, entity: InputPeerUser) -> dict:
    if "buttons" in kwargs:
        kwargs["reply_markup"] = client.build_reply_markup(kwargs.pop("buttons"))

    if "file" in kwargs:
        _, media, __ = await client._file_to_media(kwargs.pop("file"))
        upload_media = await client(messages.UploadMediaRequest(entity, media=media))
        if isinstance(media, (InputMediaPhotoExternal, InputMediaUploadedPhoto)):
            kwargs["media"] = get_input_media(upload_media.photo)
        elif isinstance(
            media, (InputMediaUploadedDocument, InputMediaDocumentExternal)
        ):
            kwargs["media"] = get_input_media(
                upload_media.document,
                supports_streaming=kwargs.get("supports_streaming"),
            )

    if "reply_to" in kwargs:
        kwargs["reply_to"] = InputReplyToMessage(kwargs["reply_to"])

    return kwargs
