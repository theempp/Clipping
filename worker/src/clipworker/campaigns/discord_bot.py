"""Discord watcher (D024): our own bot in Zo's own server reads the channel that
Reach's announcement channel is Followed into. No user token, no self-bot.

Needs: DISCORD_BOT_TOKEN, DISCORD_CAMPAIGN_CHANNEL_ID; Message Content intent
enabled for the bot (self-toggle under 10k users). Followed posts arrive as
webhook messages, so `message.webhook_id` is set; we accept those and Zo's own
manual pastes in that channel.
"""
from __future__ import annotations

import logging

from ..remote.supabase import Supabase
from .scout import parse_brief, score, to_campaign_row

log = logging.getLogger(__name__)


def handle_post(sb: Supabase, msg_id: str, channel_id: str, author: str, content: str,
                posted_at_iso: str, attachments: list[str], roster: list[str],
                familiar: set[str]) -> dict | None:
    rows = sb.insert("campaign_posts", {"discord_message_id": msg_id, "discord_channel_id": channel_id,
                                        "author": author, "content": content,
                                        "attachments": attachments, "posted_at": posted_at_iso},
                     on_conflict="discord_message_id", ignore_duplicates=True)
    if not rows:
        return None  # already seen
    post = rows[0]
    b = parse_brief(content, roster)
    total, verdict, why = score(b, familiar)
    title = content.strip().splitlines()[0][:120] if content.strip() else f"Discord post {msg_id}"
    camp = sb.insert("campaigns", to_campaign_row(b, title, post["id"], total, verdict, why))
    sb.update("campaign_posts", {"id": post["id"]}, {"parsed_at": posted_at_iso})
    return camp[0] if camp else None


def run_bot(sb: Supabase, token: str, channel_id: int, roster: list[str], familiar: set[str]) -> None:
    import discord  # optional extra: pip install .[discord]

    intents = discord.Intents.default()
    intents.message_content = True
    client = discord.Client(intents=intents)

    @client.event
    async def on_ready():
        log.info("discord bot ready as %s, watching channel %s", client.user, channel_id)

    @client.event
    async def on_message(message):
        if message.channel.id != channel_id or message.author == client.user:
            return
        camp = handle_post(sb, str(message.id), str(channel_id), str(message.author),
                           message.content or "", message.created_at.isoformat(),
                           [a.url for a in message.attachments], roster, familiar)
        if camp:
            log.info("campaign draft %s: %s", camp["id"], camp["recommendation"])

    client.run(token, log_handler=None)
