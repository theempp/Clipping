"""Twitch live chat: anonymous read-only IRC over WebSocket (justinfan nick).

No account token needed for reading. Reconnect with backoff; every outage is
written as an explicit gap row (stream-ingest rule 3).
"""
from __future__ import annotations

import asyncio
import logging
import random
from dataclasses import dataclass
from typing import Awaitable, Callable

log = logging.getLogger(__name__)
TWITCH_IRC_WS = "wss://irc-ws.chat.twitch.tv:443"


@dataclass
class ChatMessage:
    channel: str
    user: str
    text: str
    tags: dict[str, str]


def parse_tags(raw: str) -> dict[str, str]:
    out = {}
    for part in raw.split(";"):
        k, _, v = part.partition("=")
        out[k] = v.replace("\\s", " ").replace("\\:", ";").replace("\\\\", "\\")
    return out


def parse_line(line: str) -> ChatMessage | str | None:
    """Return ChatMessage for PRIVMSG, 'PING <x>' / 'RECONNECT' for control, else None."""
    line = line.rstrip("\r\n")
    if not line:
        return None
    if line.startswith("PING"):
        return line
    tags: dict[str, str] = {}
    if line.startswith("@"):
        raw, _, line = line.partition(" ")
        tags = parse_tags(raw[1:])
    prefix = ""
    if line.startswith(":"):
        prefix, _, line = line.partition(" ")
    cmd, _, rest = line.partition(" ")
    if cmd == "RECONNECT":
        return "RECONNECT"
    if cmd != "PRIVMSG":
        return None
    target, _, text = rest.partition(" :")
    user = tags.get("display-name") or prefix[1:].split("!")[0]
    if text.startswith("\x01ACTION ") and text.endswith("\x01"):
        text = text[8:-1]
    return ChatMessage(target.lstrip("#").lower(), user.lower(), text, tags)


OnMessage = Callable[[float, ChatMessage], Awaitable[None] | None]


async def run_twitch_chat(channels: list[str], on_message: OnMessage, now: Callable[[], float],
                          on_gap: Callable[[str, float, float | None, str], None] | None = None,
                          stop: asyncio.Event | None = None) -> None:
    import websockets  # imported lazily so tests don't need a network stack

    stop = stop or asyncio.Event()
    backoff = 1.0
    down_since: float | None = None
    while not stop.is_set():
        try:
            async with websockets.connect(TWITCH_IRC_WS, ping_interval=None) as ws:
                await ws.send("CAP REQ :twitch.tv/tags")
                await ws.send("PASS SCHMOOPIIE")
                await ws.send(f"NICK justinfan{random.randint(10000, 99999)}")
                for ch in channels:
                    await ws.send(f"JOIN #{ch.lower()}")
                if down_since is not None and on_gap:
                    for ch in channels:
                        on_gap(ch, down_since, now(), "twitch irc reconnect")
                down_since, backoff = None, 1.0
                async for frame in ws:
                    for line in str(frame).split("\r\n"):
                        msg = parse_line(line)
                        if msg is None:
                            continue
                        if isinstance(msg, str):
                            if msg.startswith("PING"):
                                await ws.send("PONG" + msg[4:])
                                continue
                            raise ConnectionError("server asked to reconnect")
                        r = on_message(now(), msg)
                        if asyncio.iscoroutine(r):
                            await r
                    if stop.is_set():
                        return
        except Exception as e:  # noqa: BLE001 - any drop = gap + backoff
            if down_since is None:
                down_since = now()
            log.warning("twitch chat dropped (%s); retry in %.0fs", e, backoff)
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 60.0)
