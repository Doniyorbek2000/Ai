"""💎 Beauty Club: bonus balansi, buyurtmalar tarixi va dugonani taklif qilish."""

from __future__ import annotations

from aiogram import Bot
from aiogram.types import Message

from ..config import Settings
from ..db import Database
from ..texts import fmt_price, t


async def show(message: Message, bot: Bot, db: Database, settings: Settings, lang: str, user_id: int) -> None:
    balance = await db.get_bonus(user_id)
    orders = await db.user_orders(user_id)
    if orders:
        rows = [
            f"№{o.id} — {fmt_price(o.total, lang)} — {t('status_' + o.status, lang)}"
            for o in orders
        ]
        orders_text = "\n".join(rows)
    else:
        orders_text = t("no_orders", lang)
    text = t("club", lang, balance=f"{balance:,}".replace(",", " "), percent=settings.bonus_percent, orders=orders_text)
    if settings.referral_bonus > 0:
        me = await bot.me()
        link = f"https://t.me/{me.username}?start=ref_{user_id}"
        text += "\n\n" + t(
            "invite", lang, link=link, bonus=f"{settings.referral_bonus:,}".replace(",", " "),
            count=await db.referral_count(user_id),
        )
    await message.answer(text, disable_web_page_preview=True)
