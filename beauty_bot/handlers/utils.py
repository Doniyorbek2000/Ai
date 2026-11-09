"""Handlerlar uchun umumiy yordamchilar."""

from __future__ import annotations

import io
import logging
from collections.abc import Awaitable, Callable
from typing import TypeVar

from aiogram import Bot
from aiogram.types import Message

from ..ai.claude import AIError, AIRefused
from ..config import Settings
from ..db import Database
from ..render import split_message
from ..texts import t

log = logging.getLogger(__name__)
T = TypeVar("T")

MAX_IMAGE_BYTES = 5 * 1024 * 1024  # Claude API rasm chegarasi
IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}


async def download_photo(message: Message, bot: Bot) -> tuple[bytes, str] | None:
    """Xabardagi rasmni yuklab oladi. Rasm bo'lmasa yoki juda katta bo'lsa None."""
    if message.photo:
        target = message.photo[-1]  # eng katta o'lcham
        media_type = "image/jpeg"
        size = target.file_size or 0
    elif message.document and message.document.mime_type in IMAGE_TYPES:
        target = message.document
        media_type = message.document.mime_type
        size = target.file_size or 0
    else:
        return None
    if size > MAX_IMAGE_BYTES:
        return None
    buf = io.BytesIO()
    await bot.download(target, destination=buf)
    data = buf.getvalue()
    if not data or len(data) > MAX_IMAGE_BYTES:
        return None
    return data, media_type


async def send_long(message: Message, text: str, **kwargs) -> None:
    chunks = split_message(text)
    for i, chunk in enumerate(chunks):
        # Tugmalar faqat oxirgi bo'lakka qo'yiladi
        extra = kwargs if i == len(chunks) - 1 else {}
        await message.answer(chunk, **extra)


async def run_ai(
    message: Message,
    db: Database,
    settings: Settings,
    lang: str,
    user_id: int,
    call: Callable[[], Awaitable[T]],
) -> T | None:
    """Kunlik limitni tekshiradi, AI ni chaqiradi va xatolarni foydalanuvchiga tushunarli qiladi."""
    if user_id not in settings.admin_ids:
        if not await db.try_consume_ai(user_id, settings.daily_ai_limit):
            await message.answer(t("limit_reached", lang, limit=settings.daily_ai_limit))
            return None
    try:
        return await call()
    except AIRefused:
        await db.refund_ai(user_id)
        await message.answer(t("ai_refused", lang))
    except AIError:
        await db.refund_ai(user_id)
        await message.answer(t("ai_error", lang))
    except Exception:
        log.exception("AI chaqiruvida kutilmagan xato")
        await db.refund_ai(user_id)
        await message.answer(t("ai_error", lang))
    return None
