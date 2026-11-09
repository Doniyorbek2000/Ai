"""Fon vazifalari: eslatmalar va to'lanmagan onlayn buyurtmalarni bekor qilish."""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta

from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from .config import Settings
from .db import Database
from .texts import t

log = logging.getLogger(__name__)


async def send_safe(bot: Bot, db: Database, user_id: int, text: str, **kwargs) -> bool:
    """Xabar yuboradi; botni bloklagan foydalanuvchini belgilab qo'yadi."""
    for _ in range(2):
        try:
            await bot.send_message(user_id, text, **kwargs)
            return True
        except TelegramRetryAfter as e:
            await asyncio.sleep(e.retry_after)
        except TelegramForbiddenError:
            await db.mark_blocked(user_id)
            return False
        except Exception:
            log.exception("Xabar yuborilmadi: user %s", user_id)
            return False
    return False


async def run_once(bot: Bot, db: Database, settings: Settings) -> None:
    for user_id, kind in await db.pop_due_reminders():
        if kind != "skin":
            continue
        lang = await db.get_lang(user_id)
        if lang is None:  # foydalanuvchi ma'lumotlarini o'chirgan
            continue
        markup = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text=t("btn_reanalyze", lang), callback_data="remind:skin")
        ]])
        if await send_safe(bot, db, user_id, t("reminder_skin", lang, days=settings.reminder_days), reply_markup=markup):
            await db.log_event(user_id, "reminder_sent", kind)

    for order in await db.expire_unpaid(timedelta(hours=settings.payment_ttl_hours)):
        lang = await db.get_lang(order.user_id)
        await send_safe(bot, db, order.user_id, t("order_expired", lang, id=order.id))


async def scheduler_loop(bot: Bot, db: Database, settings: Settings, interval: float = 300) -> None:
    while True:
        try:
            await run_once(bot, db, settings)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("Fon vazifasida xato")
        await asyncio.sleep(interval)
