import base64
import json

import httpx
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from clipworker.clock import Clock
from clipworker.ingest import status
from clipworker.ingest.kick_chat import parse_pusher_frame, parse_webhook_chat, verify_webhook
from clipworker.ingest.twitch_irc import ChatMessage, parse_line
from clipworker.store import Store


def test_irc_privmsg_with_tags():
    line = ("@badge-info=;display-name=CoolGuy;emotes= :coolguy!coolguy@coolguy.tmi.twitch.tv "
            "PRIVMSG #Lacy :KEKW no way\r\n")
    m = parse_line(line)
    assert isinstance(m, ChatMessage)
    assert (m.channel, m.user, m.text) == ("lacy", "coolguy", "KEKW no way")


def test_irc_control_lines():
    assert parse_line("PING :tmi.twitch.tv") == "PING :tmi.twitch.tv"
    assert parse_line(":tmi.twitch.tv RECONNECT") == "RECONNECT"
    assert parse_line(":tmi.twitch.tv 001 justinfan1 :Welcome") is None
    m = parse_line(":a!a@a PRIVMSG #x :\x01ACTION dances\x01")
    assert m.text == "dances"


def test_pusher_chat_frame():
    frame = json.dumps({"event": "App\\Events\\ChatMessageEvent", "channel": "chatrooms.42.v2",
                        "data": json.dumps({"content": "W", "sender": {"username": "Bob"}})})
    m = parse_pusher_frame(frame, {"42": "silky"})
    assert (m.channel, m.user, m.text) == ("silky", "bob", "W")
    assert parse_pusher_frame(json.dumps({"event": "pusher:ping"}), {}) == "PING"


def test_kick_webhook_signature_roundtrip():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.public_key().public_bytes(serialization.Encoding.PEM,
                                        serialization.PublicFormat.SubjectPublicKeyInfo)
    body = json.dumps({"broadcaster": {"channel_slug": "Silky"}, "sender": {"username": "x"},
                       "content": "LUL"}).encode()
    sig = base64.b64encode(key.sign(b"id1.1700000000." + body, padding.PKCS1v15(), hashes.SHA256()))
    assert verify_webhook(pem, "id1", "1700000000", body, sig.decode())
    assert not verify_webhook(pem, "id1", "1700000001", body, sig.decode())
    m = parse_webhook_chat("chat.message.sent", body)
    assert (m.channel, m.text) == ("silky", "LUL")


def test_twitch_status_poll():
    def handler(req: httpx.Request):
        if req.url.path == "/oauth2/token":
            return httpx.Response(200, json={"access_token": "t", "expires_in": 5000})
        assert req.headers["Client-Id"] == "cid"
        return httpx.Response(200, json={"data": [{"user_login": "Lacy", "type": "live"}]})
    http = httpx.Client(transport=httpx.MockTransport(handler))
    tok = status.AppToken(status.TWITCH_TOKEN_URL, "cid", "sec", http)
    assert status.twitch_live(http, tok, ["lacy", "clix"]) == {"lacy": True, "clix": False}


def test_kick_status_parser_tolerant():
    p = {"data": [{"slug": "silky", "stream": {"is_live": True}}, {"slug": "other", "stream": None}]}
    assert status.parse_kick_channels(p) == {"silky": True, "other": False}


def test_clock_monotonic_anchor():
    wall = iter([1000.0, 5000.0])
    mono = iter([10.0, 12.5, 13.0])
    c = Clock(wall=lambda: next(wall), mono=lambda: next(mono))
    assert c.now() == 1002.5          # wall jump does not move our clock
    assert c.drift() == 5000.0 - 1003.0


def test_store_gaps_and_prune():
    s = Store(":memory:")
    s.add_messages([("twitch:a", 1.0, "u", "hi"), ("twitch:a", 50.0, "u", "yo")])
    g = s.open_gap("twitch:a", "chat", 10.0, "drop")
    s.close_gap(g, 20.0)
    assert s.gaps("twitch:a") == [("chat", 10.0, 20.0, "drop")]
    s.prune(25.0)
    assert [m[0] for m in s.messages("twitch:a", 0, 100)] == [50.0]
