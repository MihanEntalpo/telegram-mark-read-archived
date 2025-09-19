#!/usr/bin/env python3
"""
Service «auto-read-archive» v2.5

Цель — очистить счётчики непрочитанного у всех архивных чатов,
включая форумы (группы с темами).

Что исправлено в v2.5
---------------------
* Убрана постраничная навигация тем — Telegram часто возвращает только одну
  страницу, а дополнительные атрибуты могут отсутствовать.
* Теперь берём **только первую страницу** тем (до 100).
* Для каждой темы вызываем `ReadDiscussion` с `read_max_id=0` — гарантированно
  очищает счётчик.

Если у вас >100 тем в одном форуме, можно увеличить `TOPIC_LIMIT`, но
чаще такая ситуация маловероятна.
"""
from __future__ import annotations

import asyncio
import getpass
import logging
from pathlib import Path
from typing import Any, List

import yaml
from telethon import TelegramClient, errors, functions, types

CONFIG_FILE = Path(__file__).with_name("config.yaml")
TOPIC_LIMIT = 100  # максимальное число тем за раз

# ---------------------------------------------------------------------------
# Загрузка конфига
# ---------------------------------------------------------------------------

def load_config() -> dict[str, Any]:
    with CONFIG_FILE.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)

# ---------------------------------------------------------------------------
# Авторизация
# ---------------------------------------------------------------------------

async def ensure_authorized(client: TelegramClient, phone: str) -> None:
    if await client.is_user_authorized():
        return
    print("→ Сессия неактивна, шлем код…")
    await client.send_code_request(phone)
    code = input("Код из Telegram: ").strip()
    try:
        await client.sign_in(phone, code)
    except errors.SessionPasswordNeededError:
        pwd = getpass.getpass("Пароль 2FA: ")
        await client.sign_in(password=pwd)

# ---------------------------------------------------------------------------
# Получение списка тем
# ---------------------------------------------------------------------------

async def iter_topics(client: TelegramClient, channel: types.Channel) -> List[types.ForumTopic]:
    """Получить до TOPIC_LIMIT тем форума (без постраничной навигации)."""
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
        logging.debug("%s: не удалось получить темы (%s)", channel, exc)
        return []

# ---------------------------------------------------------------------------
# Пометка тем прочитанными
# ---------------------------------------------------------------------------

async def mark_forum_topics_read(client: TelegramClient, channel: types.Channel, chat_name: str) -> None:
    """Снимает счётчики непрочитанного во всех темах форума."""
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
            logging.debug("%s • тема '%s' прочитана", chat_name, topic.title)
        except errors.BadRequestError as exc:
            logging.debug("%s • тема '%s' → %s", chat_name, topic.title, exc)

# ---------------------------------------------------------------------------
# Пометка диалогов прочитанными
# ---------------------------------------------------------------------------

async def mark_dialog_read(client: TelegramClient, dialog: types.Dialog) -> None:
    if dialog.unread_count:
        try:
            await client.send_read_acknowledge(dialog.entity)
            logging.info("'%s' помечен как прочитанный (%d)", dialog.name, dialog.unread_count)
        except Exception as exc:
            logging.debug("Не удалось прочитать %s: %s", dialog.name, exc)

    entity = dialog.entity
    if isinstance(entity, types.Channel) and getattr(entity, "forum", False):
        await mark_forum_topics_read(client, entity, dialog.name)

# ---------------------------------------------------------------------------
# Основной цикл
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
        logging.info("✅ Авторизован. Интервал %d с", interval)

        while True:
            try:
                archived = await client.get_dialogs(folder=1)
                for dlg in archived:
                    await mark_dialog_read(client, dlg)
            except Exception as exc:
                logging.exception("Ошибка при обходе архива: %s", exc)
            await asyncio.sleep(interval)

# ---------------------------------------------------------------------------
# Точка входа
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
        print("\n⏹️  Остановлено пользователем.")


if __name__ == "__main__":
    main()
