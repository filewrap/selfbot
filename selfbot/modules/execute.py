import asyncio
import contextlib
import io

import telethon
from telethon import Button
from telethon.types import (
    InputBotInlineMessageID,
    InputBotInlineMessageID64,
    MessageEntityBlockquote,
    MessageEntityBold,
    MessageEntityCode,
    MessageEntityPre,
    UpdateBotGuestChatQuery,
    UpdateBotNewBusinessMessage,
)

from selfbot.util import aexec, shell, usecs

cached = {
    "asyncio": asyncio,
    "io": io,
    "tl": telethon,
    "Button": Button,
    "types": telethon.types,
    "utils": telethon.utils,
    "custom": telethon.custom,
    "events": telethon.events,
    "functions": telethon.functions,
    "shell": shell,
}


async def execute(
    update: UpdateBotGuestChatQuery | UpdateBotNewBusinessMessage,
    msg_id: int | InputBotInlineMessageID | InputBotInlineMessageID64,
) -> None:
    _client = update._client
    message = update.message

    if isinstance(update, UpdateBotGuestChatQuery):
        command = _client.username.sub("", message.message)
    else:
        command = message.message.rstrip("#").rstrip()

    if not command:
        args = (msg_id, "\u2060")
        if isinstance(update, UpdateBotGuestChatQuery):
            await _client.edit_message(
                *args, buttons=Button.switch_inline("Call", "\n", True)
            )
        else:
            await update.respond(*args)

        return

    if isinstance(update, UpdateBotNewBusinessMessage):
        replied = update.reply_to_message
        await update.respond(
            update.message.id, command, entities=[MessageEntityCode(0, len(command))]
        )
    else:
        replied = update.reference_messages[0] if update.reference_messages else None

    _kwargs = cached.copy()
    _kwargs.update(
        {
            "cached": cached,
            "bot": _client,
            "app": _client._client,
            "http": _client.http,
            "client": _client._client,
            "update": update,
            "msg_id": msg_id,
            "message": message,
            "replied": replied,
        }
    )

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        buttons = Button.inline("Raise", b"0", "danger")
        if isinstance(update, UpdateBotGuestChatQuery):
            name = msg_id.access_hash
            await _client.edit_message(msg_id, buttons=buttons)
        else:
            name = msg_id
            await update.respond(msg_id, buttons=buttons)

        fut = asyncio.create_task(aexec(command, _kwargs), name=f"Exec-{name}")
        now = _client.loop.time()
        try:
            out = await fut
        except (asyncio.CancelledError, Exception) as e:
            out = e.__class__.__name__
            if str(e):
                out += f": {e}"
        else:
            out = (buf.getvalue() or str(out)).rstrip()
        finally:
            end = _client.loop.time()

    if command.rstrip().endswith("return"):
        return

    await _respond(update, msg_id, command, now, out, end)


async def _respond(
    update: UpdateBotGuestChatQuery | UpdateBotNewBusinessMessage,
    msg_id: int | InputBotInlineMessageID | InputBotInlineMessageID64,
    cmd: str,
    now: float,
    out: str,
    end: float,
) -> None:
    _client = update._client

    buttons = [
        [Button.switch_inline("Call", f"\n{cmd}", True), Button.inline("Hide", b"0")]
    ]
    elapsed = usecs(end - now)
    if len(out) <= 2048:
        output, length = fmtout(out)

        entities = [
            MessageEntityPre(0, length, "python"),
            MessageEntityBold(length + 1, len(elapsed)),
            MessageEntityBlockquote(length + 1, len(elapsed)),
        ]
        if isinstance(update, UpdateBotGuestChatQuery):
            await _client.edit_message(
                msg_id,
                f"{output}\n{elapsed}",
                formatting_entities=entities,
                buttons=buttons,
            )
        else:
            await update.respond(msg_id, f"{output}\n{elapsed}", entities=entities)

        return

    data = out.encode()
    try:
        base = "https://paste.rs"
        resp = await _client.http.post(base, data=data)
        if resp.status != 201:
            raise

        text = await resp.text()
        if not text.startswith(base):
            raise
    except Exception:
        output, length = fmtout(out, 512)

        entities = [
            MessageEntityPre(0, length, "python"),
            MessageEntityBold(length + 1, len(elapsed)),
            MessageEntityBlockquote(length + 1, len(elapsed)),
        ]
        with io.BytesIO(data) as file:
            file.name = "Output.TXT"
            if isinstance(update, UpdateBotGuestChatQuery):
                await _client.edit_message(
                    msg_id,
                    f"{output}\n{elapsed}",
                    formatting_entities=entities,
                    file=file,
                    buttons=buttons,
                )
                return

            await update.respond(
                msg_id, f"{output}\n{elapsed}", entities=entities, media=file
            )
    else:
        buttons.insert(0, [Button.url("Output", text.strip())])
        output, length = fmtout(out, 1024)

        entities = [
            MessageEntityPre(0, length, "python"),
            MessageEntityBold(length + 1, len(elapsed)),
            MessageEntityBlockquote(length + 1, len(elapsed)),
        ]
        if isinstance(update, UpdateBotGuestChatQuery):
            await _client.edit_message(
                msg_id,
                f"{output}\n{elapsed}",
                formatting_entities=entities,
                buttons=buttons,
            )
            return

        await update.respond(
            msg_id, f"{output}\n{elapsed}", entities=entities, buttons=buttons[0]
        )


def fmtout(output: str, length: int = None) -> int:
    if length:
        output = f"{output[:length]}..."

    return output, len(output.encode("utf-16-le")) // 2
