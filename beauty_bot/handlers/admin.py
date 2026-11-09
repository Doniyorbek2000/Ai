"""Admin panel (faqat ADMIN_IDS uchun).

Buyruqlar:
  /admin                     — yordam
  /orders [holat]            — buyurtmalar ro'yxati
  /stats [kunlar]            — statistika (standart 7 kun)
  /products [kategoriya]     — mahsulotlar, narx va mavjudlik
  /price <id> <summa>        — narxni o'zgartirish
  /stock <id> on|off         — sotuvga qo'yish / olib tashlash
  /reload                    — data/products.json ni qayta o'qish
  /broadcast                 — xabarga javob (reply) qilib yozilsa, hammaga yuboradi
"""

from __future__ import annotations

import asyncio
import logging
from html import escape

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter
from aiogram.filters import Command, CommandObject
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from .. import keyboards as kb
from ..catalog import Catalog
from ..config import Settings
from ..db import FINAL_STATUSES, ORDER_STATUSES, Database
from ..render import split_message
from ..scheduler import send_safe
from ..texts import t
from .shop import admin_order_text

log = logging.getLogger(__name__)
router = Router(name="admin")

HELP = __doc__.split("Buyruqlar:", 1)[1]


def is_admin(user_id: int, settings: Settings) -> bool:
    return user_id in settings.admin_ids


def _money(amount: int) -> str:
    return f"{amount:,}".replace(",", " ")


@router.message(Command("admin"))
async def cmd_admin(message: Message, settings: Settings) -> None:
    if is_admin(message.from_user.id, settings):
        await message.answer("<b>Admin buyruqlari</b>\n<pre>" + escape(HELP.strip("\n")) + "</pre>")


# --- Buyurtmalar ---------------------------------------------------------------

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
    finished = order.status in FINAL_STATUSES
    await callback.message.edit_text(
        admin_order_text(order) + f"\n\n✍️ {escape(callback.from_user.full_name)}",
        reply_markup=None if finished else kb.admin_order_kb(order.id),
    )
    lang = await db.get_lang(order.user_id)
    await send_safe(bot, db, order.user_id,
                    t("order_status_changed", lang, id=order.id, status=t(f"status_{order.status}", lang)))

    if order.status == "delivered":
        await db.log_event(order.user_id, "delivered", str(order.id))
        referrer = await db.reward_referrer(order.user_id, settings.referral_bonus)
        if referrer:
            ref_lang = await db.get_lang(referrer)
            await send_safe(bot, db, referrer,
                            t("referral_reward", ref_lang, bonus=_money(settings.referral_bonus)))


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
        finished = order.status in FINAL_STATUSES or order.status == "awaiting_payment"
        await message.answer(
            admin_order_text(order),
            reply_markup=None if finished else kb.admin_order_kb(order.id),
        )


# --- Statistika ----------------------------------------------------------------

EVENT_NAMES = {
    "start": "Yangi start",
    "skin": "Teri tahlili",
    "look": "Ideal obraz",
    "makeup": "AI makiyaj",
    "perfume": "Atir tanlash",
    "academy": "Academy savollari",
    "add_ai": "Savatga (AI tavsiyasidan)",
    "add_shop": "Savatga (katalogdan)",
    "order": "Buyurtma",
    "paid": "Onlayn to'lov",
    "delivered": "Yetkazildi",
    "reminder_sent": "Eslatma yuborildi",
}


def render_stats(s: dict, days: int, catalog: Catalog) -> str:
    conv = f"{s['buyers_after_ai'] * 100 // s['ai_users']}%" if s["ai_users"] else "—"
    lines = [
        f"📊 <b>Statistika: oxirgi {days} kun</b>",
        "",
        f"👥 Foydalanuvchilar: {s['users_total']} (yangi: {s['users_new']}, botni bloklagan: {s['users_blocked']})",
        f"🛒 Buyurtmalar: {s['orders']} (yetkazilgan: {s['orders_delivered']}, onlayn to'langan: {s['paid_online']})",
        f"💰 Tushum (yetkazilgan): {_money(s['revenue_delivered'])} so'm",
        f"⏳ Jarayondagi buyurtmalar: {_money(s['revenue_open'])} so'm",
        f"🎯 AI dan foydalanib xarid qilganlar: {s['buyers_after_ai']} / {s['ai_users']} ({conv})",
        "",
        "<b>Harakatlar</b> (soni / odam):",
    ]
    for kind, (n, users) in s["events"].items():
        lines.append(f"• {EVENT_NAMES.get(kind, kind)}: {n} / {users}")
    if s["sources"]:
        lines += ["", "<b>Yangi foydalanuvchilar manbai</b> (bloger/havola):"]
        lines += [f"• {escape(str(src))}: {n}" for src, n in s["sources"]]
    if s["top_ai_products"]:
        lines += ["", "<b>AI tavsiyasidan eng ko'p savatga qo'shilganlar:</b>"]
        for pid, n in s["top_ai_products"]:
            p = catalog.get(pid)
            lines.append(f"• {escape(p.title('uz') if p else pid)}: {n}")
    return "\n".join(lines)


@router.message(Command("stats"))
async def cmd_stats(message: Message, command: CommandObject, db: Database, catalog: Catalog, settings: Settings) -> None:
    if not is_admin(message.from_user.id, settings):
        return
    arg = (command.args or "7").strip()
    days = int(arg) if arg.isdigit() and 0 < int(arg) <= 3650 else 7
    await message.answer(render_stats(await db.stats(days), days, catalog))


# --- Katalog boshqaruvi ---------------------------------------------------------

@router.message(Command("products"))
async def cmd_products(message: Message, command: CommandObject, catalog: Catalog, settings: Settings) -> None:
    if not is_admin(message.from_user.id, settings):
        return
    category = (command.args or "").strip() or None
    lines = []
    for p in catalog.products:
        if category and p.category != category:
            continue
        mark = "✅" if p.in_stock else "⛔️"
        lines.append(f"{mark} <code>{p.id}</code> — {_money(p.price)} — {escape(p.title('uz'))}")
    text = "\n".join(lines) or "Mahsulot topilmadi. Kategoriyalar: " + ", ".join(catalog.categories)
    for chunk in split_message(text):
        await message.answer(chunk)


@router.message(Command("price"))
async def cmd_price(message: Message, command: CommandObject, db: Database, catalog: Catalog, settings: Settings) -> None:
    if not is_admin(message.from_user.id, settings):
        return
    args = (command.args or "").split()
    if len(args) != 2 or not args[1].replace(" ", "").isdigit() or int(args[1]) <= 0:
        await message.answer("Foydalanish: <code>/price sk-spf50 145000</code>")
        return
    product_id, price = args[0], int(args[1])
    if catalog.get(product_id) is None:
        await message.answer(f"«{escape(product_id)}» topilmadi. /products")
        return
    await db.set_override(product_id, price=price)
    p = catalog.update(product_id, price=price)
    await message.answer(f"✅ {escape(p.title('uz'))}: yangi narx {_money(price)} so'm")


@router.message(Command("stock"))
async def cmd_stock(message: Message, command: CommandObject, db: Database, catalog: Catalog, settings: Settings) -> None:
    if not is_admin(message.from_user.id, settings):
        return
    args = (command.args or "").split()
    if len(args) != 2 or args[1] not in ("on", "off"):
        await message.answer("Foydalanish: <code>/stock sk-spf50 off</code> yoki <code>on</code>")
        return
    product_id, in_stock = args[0], args[1] == "on"
    if catalog.get(product_id) is None:
        await message.answer(f"«{escape(product_id)}» topilmadi. /products")
        return
    await db.set_override(product_id, in_stock=in_stock)
    p = catalog.update(product_id, in_stock=in_stock)
    state = "sotuvda ✅" if in_stock else "sotuvdan olindi ⛔️ (AI ham tavsiya qilmaydi)"
    await message.answer(f"{escape(p.title('uz'))}: {state}")


@router.message(Command("reload"))
async def cmd_reload(message: Message, db: Database, catalog: Catalog, settings: Settings) -> None:
    if not is_admin(message.from_user.id, settings):
        return
    try:
        fresh = Catalog.load(settings.catalog_path)
    except Exception as e:
        await message.answer(f"❌ Katalogni o'qib bo'lmadi: {escape(str(e))}")
        return
    fresh.apply_overrides(await db.overrides())
    catalog.reload_from(fresh)
    await message.answer(f"✅ Katalog yangilandi: {len(catalog.products)} ta mahsulot.")


# --- Ommaviy xabar ----------------------------------------------------------------

@router.message(Command("broadcast"))
async def cmd_broadcast(message: Message, db: Database, settings: Settings) -> None:
    if not is_admin(message.from_user.id, settings):
        return
    source = message.reply_to_message
    if source is None:
        await message.answer(
            "Avval yubormoqchi bo'lgan xabarni (matn, rasm, video) shu chatga yozing, "
            "keyin unga <b>javob (reply)</b> qilib /broadcast yozing."
        )
        return
    count = len(await db.active_user_ids())
    await message.answer(
        f"Bu xabar {count} ta foydalanuvchiga yuboriladi. Tasdiqlaysizmi?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="✅ Yuborish", callback_data=f"bc:{source.chat.id}:{source.message_id}"),
            InlineKeyboardButton(text="❌ Bekor", callback_data="bc:no"),
        ]]),
    )


@router.callback_query(F.data.startswith("bc:"))
async def cb_broadcast(callback: CallbackQuery, bot: Bot, db: Database, settings: Settings) -> None:
    if not is_admin(callback.from_user.id, settings):
        await callback.answer("Ruxsat yo'q", show_alert=True)
        return
    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=None)
    if callback.data == "bc:no":
        await callback.message.answer("Bekor qilindi.")
        return
    _, chat_id, message_id = callback.data.split(":")
    asyncio.create_task(_broadcast(bot, db, callback.message.chat.id, int(chat_id), int(message_id)))
    await callback.message.answer("📤 Yuborish boshlandi. Tugagach hisobot keladi.")


async def _broadcast(bot: Bot, db: Database, report_chat: int, from_chat: int, message_id: int,
                     delay: float = 0.05) -> tuple[int, int]:
    ok = failed = 0
    for user_id in await db.active_user_ids():
        for _ in range(2):
            try:
                await bot.copy_message(user_id, from_chat, message_id)
                ok += 1
                break
            except TelegramRetryAfter as e:
                await asyncio.sleep(e.retry_after)
            except TelegramForbiddenError:
                await db.mark_blocked(user_id)
                failed += 1
                break
            except Exception:
                log.warning("Broadcast: %s ga yuborilmadi", user_id)
                failed += 1
                break
        await asyncio.sleep(delay)  # Telegram limiti: sekundiga ~30 xabar
    try:
        await bot.send_message(report_chat, f"✅ Yuborildi: {ok}\n❌ Yetmadi: {failed}")
    except Exception:
        log.exception("Broadcast hisobotini yuborib bo'lmadi")
    return ok, failed
