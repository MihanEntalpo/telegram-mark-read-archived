#!/usr/bin/env python3
"""
Service "auto-read-archive" v2.5

Goal — reset unread counters for every archived chat, including forums with
topics.

Changes in v2.5
---------------
* Removed topic pagination — Telegram often returns a single page and extra
  attributes may be missing.
* Fetch **only the first page** of topics (up to 100).
* Call `ReadDiscussion` with `read_max_id=0` for every topic to reliably clear
  the counter.

If you have more than 100 topics in a single forum you can raise `TOPIC_LIMIT`,
though that situation should be rare.
"""
from __future__ import annotations

import asyncio
import getpass
import logging
import os
from pathlib import Path
from typing import Any, List

import yaml
from telethon import TelegramClient, errors, functions, types

CONFIG_FILE = Path(__file__).with_name("config.yaml")
TOPIC_LIMIT = int(os.getenv("TOPIC_LIMIT") or 100)  # maximum number of topics per request

# ---------------------------------------------------------------------------
# Configuration loading
# ---------------------------------------------------------------------------

def load_config() -> dict[str, Any]:
    with CONFIG_FILE.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)

# ---------------------------------------------------------------------------
# Authorization
# ---------------------------------------------------------------------------

async def ensure_authorized(client: TelegramClient, phone: str) -> None:
    if await client.is_user_authorized():
        return
    print("→ Session inactive, sending code…")
    await client.send_code_request(phone)
    code = input("Code from Telegram: ").strip()
    try:
        await client.sign_in(phone, code)
    except errors.SessionPasswordNeededError:
        pwd = getpass.getpass("2FA password: ")
        await client.sign_in(password=pwd)

# ---------------------------------------------------------------------------
# Retrieving the topic list
# ---------------------------------------------------------------------------

async def iter_topics(client: TelegramClient, channel: types.Channel) -> List[types.ForumTopic]:
    """Return up to TOPIC_LIMIT forum topics without pagination."""
    try:
        resp = await client(
            functions.channels.GetForumTopicsRequest(
                channel=channel,
                offset_date=None,
                offset_id=0,
                offset_topic=0,
                limit=TOPIC_LIMIT,
                q=None,
            )
        )
        return list(resp.topics)
    except Exception as exc:
        logging.debug("%s: failed to fetch topics (%s)", channel, exc)
        return []

# ---------------------------------------------------------------------------
# Marking topics as read
# ---------------------------------------------------------------------------

async def mark_forum_topics_read(client: TelegramClient, channel: types.Channel, chat_name: str) -> None:
    """Clear unread counters for every topic in the forum."""
    topics = await iter_topics(client, channel)
    for topic in topics:
        try:
            await client(
                functions.messages.ReadDiscussionRequest(
                    peer=channel,
                    msg_id=topic.top_message,
                    read_max_id=0,
                )
            )
            logging.debug("%s • topic '%s' marked as read", chat_name, topic.title)
        except errors.BadRequestError as exc:
            logging.debug("%s • topic '%s' → %s", chat_name, topic.title, exc)

# ---------------------------------------------------------------------------
# Marking dialogs as read
# ---------------------------------------------------------------------------

async def mark_dialog_read(client: TelegramClient, dialog: types.Dialog) -> None:
    if dialog.unread_count:
        try:
            await client.send_read_acknowledge(dialog.entity)
            logging.info("'%s' marked as read (%d)", dialog.name, dialog.unread_count)
        except Exception as exc:
            logging.debug("Failed to mark %s as read: %s", dialog.name, exc)

    entity = dialog.entity
    if isinstance(entity, types.Channel) and getattr(entity, "forum", False):
        await mark_forum_topics_read(client, entity, dialog.name)

# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

async def run_service(cfg: dict[str, Any]) -> None:
    tg = cfg["telegram"]
    interval = int(cfg["service"]["check_interval"])

    client = TelegramClient(
        session=tg["session"],  
        api_id=tg["api_id"],
        api_hash=tg["api_hash"],
        system_version="LittleBrother 2.5",
    )

    async with client:
        await ensure_authorized(client, tg["phone"])
        logging.info("✅ Authorized. Interval %d s", interval)

        while True:
            try:
                archived = await client.get_dialogs(folder=1)
                for dlg in archived:
                    await mark_dialog_read(client, dlg)
            except Exception as exc:
                logging.exception("Error while iterating through archive: %s", exc)
            await asyncio.sleep(interval)

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    cfg = load_config()
    logging.basicConfig(
        level=getattr(logging, cfg["service"]["log_level"].upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    try:
        asyncio.run(run_service(cfg))
    except KeyboardInterrupt:
        print("\n⏹️  Stopped by user.")


if __name__ == "__main__":
    main()
