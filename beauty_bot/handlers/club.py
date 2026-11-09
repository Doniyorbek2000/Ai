"""💎 Beauty Club: bonus balansi va buyurtmalar tarixi."""

from __future__ import annotations

from aiogram.types import Message

from ..config import Settings
from ..db import Database
from ..texts import fmt_price, t


async def show(message: Message, db: Database, settings: Settings, lang: str, user_id: int) -> None:
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
    await message.answer(
        t("club", lang, balance=f"{balance:,}".replace(",", " "), percent=settings.bonus_percent, orders=orders_text)
    )
