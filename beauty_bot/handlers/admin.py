"""Admin: buyurtma holatini o'zgartirish va ro'yxatlar."""

from __future__ import annotations

import logging

from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import CallbackQuery, Message

from .. import keyboards as kb
from ..config import Settings
from ..db import ORDER_STATUSES, Database
from ..texts import t
from .shop import admin_order_text

log = logging.getLogger(__name__)
router = Router(name="admin")


def is_admin(user_id: int, settings: Settings) -> bool:
    return user_id in settings.admin_ids


@router.callback_query(F.data.startswith("adm:"))
async def cb_status(callback: CallbackQuery, bot: Bot, db: Database, settings: Settings) -> None:
    if not is_admin(callback.from_user.id, settings):
        await callback.answer("Ruxsat yo'q", show_alert=True)
        return
    _, order_id, status = callback.data.split(":")
    try:
        order = await db.set_order_status(int(order_id), status)
    except ValueError as e:
        await callback.answer(str(e), show_alert=True)
        return
    if order is None:
        await callback.answer("Buyurtma topilmadi", show_alert=True)
        return
    await callback.answer(f"№{order.id}: {status}")
    finished = order.status in ("delivered", "cancelled")
    await callback.message.edit_text(
        admin_order_text(order) + f"\n\n✍️ {callback.from_user.full_name}",
        reply_markup=None if finished else kb.admin_order_kb(order.id),
    )
    lang = await db.get_lang(order.user_id)
    try:
        await bot.send_message(
            order.user_id,
            t("order_status_changed", lang, id=order.id, status=t(f"status_{order.status}", lang)),
        )
    except Exception:
        log.warning("Mijozga holat haqida xabar yuborilmadi (user %s)", order.user_id)


@router.message(Command("orders"))
async def cmd_orders(message: Message, command: CommandObject, db: Database, settings: Settings) -> None:
    if not is_admin(message.from_user.id, settings):
        return
    status = (command.args or "new").strip()
    if status not in ORDER_STATUSES:
        await message.answer("Holat: " + ", ".join(ORDER_STATUSES))
        return
    orders = await db.orders_by_status(status)
    if not orders:
        await message.answer(f"«{status}» holatida buyurtma yo'q.")
        return
    for order in orders:
        finished = order.status in ("delivered", "cancelled")
        await message.answer(
            admin_order_text(order),
            reply_markup=None if finished else kb.admin_order_kb(order.id),
        )
