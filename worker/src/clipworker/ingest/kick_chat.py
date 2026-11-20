"""Kick live chat. Two paths, one normalized ChatMessage.

pusher (default): Kick's public chat WebSocket, read-only. UNOFFICIAL: may
  break; needs the per-channel chatroom_id in channels.toml and KICK_PUSHER_KEY
  in .env (the public key Kick's own web client uses).
webhook: official `chat.message.sent` events. Needs a public HTTPS endpoint
  reaching the PC (e.g. a Cloudflare Tunnel). Signature verified with Kick's
  public key: RSA-SHA256 over "<message-id>.<timestamp>.<body>". Event names
  and payload fields are UNVERIFIED against KickDevDocs; confirm before use.
"""
from __future__ import annotations

import asyncio
import base64
import json
import logging
from typing import Callable

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

from .twitch_irc import ChatMessage

log = logging.getLogger(__name__)
PUSHER_URL = "wss://ws-us2.pusher.com/app/{key}?protocol=7&client=js&version=8.4.0&flash=false"
CHAT_EVENT = "App\\Events\\ChatMessageEvent"


def parse_pusher_frame(frame: str, channel_by_room: dict[str, str]) -> ChatMessage | str | None:
    j = json.loads(frame)
    ev = j.get("event", "")
    if ev == "pusher:ping":
        return "PING"
    if ev != CHAT_EVENT:
        return None
    room = j.get("channel", "").split(".")[1] if "." in j.get("channel", "") else ""
    data = j.get("data")
    data = json.loads(data) if isinstance(data, str) else (data or {})
    user = ((data.get("sender") or {}).get("username") or "?").lower()
    return ChatMessage(channel_by_room.get(room, room), user, data.get("content", ""), {})


def verify_webhook(public_key_pem: bytes, message_id: str, timestamp: str, body: bytes,
                   signature_b64: str) -> bool:
    key = serialization.load_pem_public_key(public_key_pem)
    signed = f"{message_id}.{timestamp}.".encode() + body
    try:
        key.verify(base64.b64decode(signature_b64), signed, padding.PKCS1v15(), hashes.SHA256())
        return True
    except (InvalidSignature, ValueError):
        return False


def parse_webhook_chat(event_type: str, body: bytes) -> ChatMessage | None:
    if event_type != "chat.message.sent":
        return None
    j = json.loads(body)
    bc = (j.get("broadcaster") or {}).get("channel_slug") or ""
    user = ((j.get("sender") or {}).get("username") or "?").lower()
    return ChatMessage(bc.lower(), user, j.get("content", ""), {})


async def run_kick_pusher(key: str, rooms: dict[str, str], on_message: Callable,
                          now: Callable[[], float], on_gap: Callable | None = None,
                          stop: asyncio.Event | None = None) -> None:
    """rooms: chatroom_id -> channel login."""
    import websockets

    stop = stop or asyncio.Event()
    backoff, down_since = 1.0, None
    while not stop.is_set():
        try:
            async with websockets.connect(PUSHER_URL.format(key=key)) as ws:
                for room in rooms:
                    await ws.send(json.dumps({"event": "pusher:subscribe",
                                              "data": {"auth": "", "channel": f"chatrooms.{room}.v2"}}))
                if down_since is not None and on_gap:
                    for login in rooms.values():
                        on_gap(login, down_since, now(), "kick pusher reconnect")
                down_since, backoff = None, 1.0
                async for frame in ws:
                    msg = parse_pusher_frame(str(frame), rooms)
                    if msg == "PING":
                        await ws.send(json.dumps({"event": "pusher:pong", "data": {}}))
                    elif msg is not None:
                        r = on_message(now(), msg)
                        if asyncio.iscoroutine(r):
                            await r
                    if stop.is_set():
                        return
        except Exception as e:  # noqa: BLE001
            if down_since is None:
                down_since = now()
            log.warning("kick chat dropped (%s); retry in %.0fs", e, backoff)
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 60.0)
