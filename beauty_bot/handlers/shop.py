"""🛍 Do'kon: katalog, savat, buyurtma berish va to'lov (kuryerga yoki Click/Payme orqali)."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from html import escape

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, LabeledPrice, Message, PreCheckoutQuery

from .. import keyboards as kb
from ..catalog import Catalog, Product
from ..config import Settings
from ..db import Database, Order, calc_delivery
from ..render import cart_lines, render_cart, render_product_card
from ..texts import fmt_price, t

log = logging.getLogger(__name__)
router = Router(name="shop")

PHONE_RE = re.compile(r"^\+?998\d{9}$")
CURRENCY = "UZS"
CURRENCY_EXP = 100  # Telegram UZS summasini tiyinda kutadi (2 xona)


class CheckoutStates(StatesGroup):
    phone = State()
    address = State()
    comment = State()
    bonus = State()
    confirm = State()


def normalize_phone(raw: str) -> str | None:
    digits = re.sub(r"[^\d+]", "", raw)
    if digits.startswith("+"):
        digits = digits[1:]
    if len(digits) == 9:  # 901234567
        digits = "998" + digits
    return "+" + digits if PHONE_RE.match(digits) else None


def _money(amount: int) -> str:
    return f"{amount:,}".replace(",", " ")


@dataclass(frozen=True)
class Totals:
    subtotal: int
    bonus_used: int
    delivery: int

    @property
    def total(self) -> int:
        return self.subtotal - self.bonus_used + self.delivery


def checkout_totals(lines: list[tuple[Product, int]], bonus_balance: int, use_bonus: bool, settings: Settings) -> Totals:
    subtotal = sum(p.price * q for p, q in lines)
    bonus_used = min(bonus_balance, subtotal) if use_bonus else 0
    delivery = calc_delivery(subtotal, settings.delivery_fee, settings.free_delivery_from)
    return Totals(subtotal, bonus_used, delivery)


def render_totals(cart_text: str, totals: Totals, lang: str) -> str:
    parts = [cart_text]
    if totals.bonus_used:
        parts.append(t("use_bonus", lang, amount=_money(totals.bonus_used)))
    delivery = fmt_price(totals.delivery, lang) if totals.delivery else t("delivery_free", lang)
    parts.append(f"{t('delivery', lang)}: {delivery}")
    parts.append(f"<b>{t('total', lang)}: {fmt_price(totals.total, lang)}</b>")
    return "\n".join(parts)


def online_payment_enabled(settings: Settings) -> bool:
    return bool(settings.payment_provider_token)


# --- Katalog -------------------------------------------------------------

async def show_categories(message: Message, catalog: Catalog, lang: str) -> None:
    await message.answer(t("shop_title", lang), reply_markup=kb.categories_kb(catalog, lang))


@router.callback_query(F.data == "shop")
async def cb_shop(callback: CallbackQuery, catalog: Catalog, lang: str) -> None:
    await callback.answer()
    await _edit_or_send(callback, t("shop_title", lang), kb.categories_kb(catalog, lang))


@router.callback_query(F.data.startswith("cat:"))
async def cb_category(callback: CallbackQuery, catalog: Catalog, lang: str) -> None:
    category = callback.data.split(":", 1)[1]
    products = catalog.available(category)
    await callback.answer()
    if not products:
        await callback.message.answer(t("category_empty", lang))
        return
    title = f"<b>{escape(catalog.category_title(category, lang))}</b>"
    await _edit_or_send(callback, title, kb.category_products_kb(products, lang))


@router.callback_query(F.data.startswith("prod:"))
async def cb_product(callback: CallbackQuery, catalog: Catalog, lang: str) -> None:
    p = catalog.get(callback.data.split(":", 1)[1])
    await callback.answer()
    if p is None:
        await callback.message.answer(t("not_found", lang))
        return
    text = render_product_card(p, catalog, lang)
    if p.image_url:
        try:
            await callback.message.answer_photo(p.image_url, caption=text, reply_markup=kb.product_kb(p, lang))
            return
        except TelegramBadRequest:
            log.warning("Mahsulot rasmi yuklanmadi: %s", p.image_url)
    await callback.message.answer(text, reply_markup=kb.product_kb(p, lang))


async def _edit_or_send(callback: CallbackQuery, text: str, markup) -> None:
    try:
        await callback.message.edit_text(text, reply_markup=markup)
    except TelegramBadRequest:
        # Rasmli xabarni matnga tahrirlab bo'lmaydi
        await callback.message.answer(text, reply_markup=markup)


# --- Savat ---------------------------------------------------------------

@router.callback_query(F.data.startswith("add:"))
async def cb_add(callback: CallbackQuery, db: Database, catalog: Catalog, lang: str) -> None:
    parts = callback.data.split(":")
    p = catalog.get(parts[1])
    if p is None or not p.in_stock:
        await callback.answer(t("out_of_stock", lang), show_alert=True)
        return
    await db.ensure_user(callback.from_user.id, callback.from_user.full_name)
    await db.cart_add(callback.from_user.id, p.id, 1)
    # AI tavsiyasidan qo'shilganmi yoki katalogdanmi: konversiyani o'lchash uchun
    from_ai = len(parts) > 2 and parts[2] == "ai"
    await db.log_event(callback.from_user.id, "add_ai" if from_ai else "add_shop", p.id)
    await callback.answer(f"{t('added', lang)}: {p.title(lang)}")


async def show_cart(
    message: Message,
    db: Database,
    catalog: Catalog,
    lang: str,
    user_id: int,
    edit: bool = False,
    settings: Settings | None = None,
) -> None:
    lines = cart_lines(await db.cart_items(user_id), catalog)
    text, subtotal = render_cart(lines, lang)
    if lines and settings and settings.free_delivery_from and subtotal < settings.free_delivery_from:
        text += "\n\n" + t("free_delivery_hint", lang, amount=fmt_price(settings.free_delivery_from, lang))
    markup = kb.cart_kb(lines, lang) if lines else None
    if edit:
        try:
            await message.edit_text(text, reply_markup=markup)
            return
        except TelegramBadRequest:
            pass
    await message.answer(text, reply_markup=markup)


@router.callback_query(F.data == "cart")
async def cb_cart(callback: CallbackQuery, db: Database, catalog: Catalog, settings: Settings, lang: str) -> None:
    await callback.answer()
    await show_cart(callback.message, db, catalog, lang, callback.from_user.id, settings=settings)


@router.callback_query(F.data.startswith("inc:") | F.data.startswith("dec:"))
async def cb_qty(callback: CallbackQuery, db: Database, catalog: Catalog, settings: Settings, lang: str) -> None:
    op, pid = callback.data.split(":", 1)
    await db.cart_add(callback.from_user.id, pid, 1 if op == "inc" else -1)
    await callback.answer()
    await show_cart(callback.message, db, catalog, lang, callback.from_user.id, edit=True, settings=settings)


@router.callback_query(F.data == "clear")
async def cb_clear(callback: CallbackQuery, db: Database, catalog: Catalog, lang: str) -> None:
    await db.cart_clear(callback.from_user.id)
    await callback.answer()
    await show_cart(callback.message, db, catalog, lang, callback.from_user.id, edit=True)


# --- Buyurtma berish ----------------------------------------------------------

@router.callback_query(F.data == "checkout")
async def cb_checkout(callback: CallbackQuery, state: FSMContext, db: Database, catalog: Catalog, lang: str) -> None:
    await callback.answer()
    if not cart_lines(await db.cart_items(callback.from_user.id), catalog):
        await callback.message.answer(t("cart_empty", lang))
        return
    await state.set_state(CheckoutStates.phone)
    await callback.message.answer(t("ask_phone", lang), reply_markup=kb.phone_kb(lang))


@router.message(CheckoutStates.phone, F.contact | F.text)
async def msg_phone(message: Message, state: FSMContext, lang: str) -> None:
    raw = message.contact.phone_number if message.contact else (message.text or "")
    phone = normalize_phone(raw)
    if phone is None:
        await message.answer(t("bad_phone", lang), reply_markup=kb.phone_kb(lang))
        return
    await state.update_data(phone=phone)
    await state.set_state(CheckoutStates.address)
    await message.answer(t("ask_address", lang), reply_markup=kb.location_kb(lang))


@router.message(CheckoutStates.address, F.location | F.text)
async def msg_address(message: Message, state: FSMContext, lang: str) -> None:
    if message.location:
        loc = message.location
        address = f"https://maps.google.com/?q={loc.latitude},{loc.longitude}"
    else:
        address = (message.text or "").strip()[:300]
        if len(address) < 5:
            await message.answer(t("ask_address", lang), reply_markup=kb.location_kb(lang))
            return
    await state.update_data(address=address)
    await state.set_state(CheckoutStates.comment)
    await message.answer(t("ask_comment", lang), reply_markup=kb.main_menu(lang))
    await message.answer("👇", reply_markup=kb.skip_kb(lang))


async def _after_comment(message: Message, state: FSMContext, db: Database, catalog: Catalog,
                         settings: Settings, lang: str, user_id: int) -> None:
    balance = await db.get_bonus(user_id)
    if balance > 0:
        await state.set_state(CheckoutStates.bonus)
        await message.answer("💎", reply_markup=kb.bonus_kb(balance, lang))
        return
    await state.update_data(use_bonus=False)
    await _show_confirm(message, state, db, catalog, settings, lang, user_id)


@router.message(CheckoutStates.comment, F.text)
async def msg_comment(message: Message, state: FSMContext, db: Database, catalog: Catalog,
                      settings: Settings, lang: str) -> None:
    await state.update_data(comment=message.text.strip()[:500])
    await _after_comment(message, state, db, catalog, settings, lang, message.from_user.id)


@router.callback_query(CheckoutStates.comment, F.data == "skip")
async def cb_skip_comment(callback: CallbackQuery, state: FSMContext, db: Database, catalog: Catalog,
                          settings: Settings, lang: str) -> None:
    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=None)
    await state.update_data(comment=None)
    await _after_comment(callback.message, state, db, catalog, settings, lang, callback.from_user.id)


@router.callback_query(CheckoutStates.bonus, F.data.startswith("bonus:"))
async def cb_bonus(callback: CallbackQuery, state: FSMContext, db: Database, catalog: Catalog,
                   settings: Settings, lang: str) -> None:
    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=None)
    await state.update_data(use_bonus=callback.data == "bonus:yes")
    await _show_confirm(callback.message, state, db, catalog, settings, lang, callback.from_user.id)


async def _show_confirm(message: Message, state: FSMContext, db: Database, catalog: Catalog,
                        settings: Settings, lang: str, user_id: int) -> None:
    data = await state.get_data()
    lines = cart_lines(await db.cart_items(user_id), catalog)
    if not lines:
        await state.clear()
        await message.answer(t("cart_empty", lang), reply_markup=kb.main_menu(lang))
        return
    cart_text, _ = render_cart(lines, lang)
    totals = checkout_totals(lines, await db.get_bonus(user_id), bool(data.get("use_bonus")), settings)
    online = online_payment_enabled(settings) and totals.total > 0
    await state.set_state(CheckoutStates.confirm)
    await message.answer(
        t("confirm_order", lang,
          cart=render_totals(cart_text, totals, lang),
          phone=escape(data["phone"]),
          address=escape(data["address"]),
          comment=escape(data.get("comment") or "—"),
          payment=t("choose_payment", lang) if online else t("payment_cash_note", lang)),
        reply_markup=kb.payment_kb(lang) if online else kb.confirm_kb(lang),
    )


@router.callback_query(CheckoutStates.confirm, F.data.in_({"order:confirm", "order:online"}))
async def cb_confirm(
    callback: CallbackQuery,
    state: FSMContext,
    bot: Bot,
    db: Database,
    catalog: Catalog,
    settings: Settings,
    lang: str,
) -> None:
    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=None)
    user_id = callback.from_user.id
    data = await state.get_data()
    lines = cart_lines(await db.cart_items(user_id), catalog)
    if not lines:
        await state.clear()
        await callback.message.answer(t("cart_empty", lang), reply_markup=kb.main_menu(lang))
        return
    totals = checkout_totals(lines, await db.get_bonus(user_id), bool(data.get("use_bonus")), settings)
    online = callback.data == "order:online" and online_payment_enabled(settings) and totals.total > 0
    items = [{"id": p.id, "name": p.name.get("uz", p.id), "price": p.price, "qty": q} for p, q in lines]
    order = await db.create_order(
        user_id=user_id,
        items=items,
        subtotal=totals.subtotal,
        bonus_used=totals.bonus_used,
        phone=data["phone"],
        address=data["address"],
        comment=data.get("comment"),
        bonus_percent=settings.bonus_percent,
        delivery_fee=totals.delivery,
        payment_method="online" if online else "cash",
    )
    await state.clear()

    if online:
        await send_invoice(callback.message, bot, settings, order, lang)
        return
    await db.log_event(user_id, "order", str(order.id))
    await callback.message.answer(
        t("order_placed", lang, id=order.id, bonus=_money(order.bonus_earned)),
        reply_markup=kb.main_menu(lang),
    )
    await notify_admin(bot, settings, order, callback.from_user.full_name)


# --- Onlayn to'lov (Telegram Payments: Click / Payme) ---------------------------

async def send_invoice(message: Message, bot: Bot, settings: Settings, order: Order, lang: str) -> None:
    count = sum(int(it["qty"]) for it in order.items)
    await message.answer(t("invoice_sent", lang, hours=settings.payment_ttl_hours), reply_markup=kb.main_menu(lang))
    await bot.send_invoice(
        chat_id=message.chat.id,
        title=t("invoice_title", lang, id=order.id)[:32],
        description=t("invoice_description", lang, count=count)[:255],
        payload=f"order:{order.id}",
        provider_token=settings.payment_provider_token,
        currency=CURRENCY,
        prices=[LabeledPrice(label=t("invoice_title", lang, id=order.id)[:32], amount=order.total * CURRENCY_EXP)],
    )


def _order_id_from_payload(payload: str) -> int | None:
    prefix, _, raw = payload.partition(":")
    return int(raw) if prefix == "order" and raw.isdigit() else None


@router.pre_checkout_query()
async def pre_checkout(query: PreCheckoutQuery, db: Database, lang: str) -> None:
    """Telegram to'lovdan oldin so'raydi: buyurtma hali ham to'lanishi mumkinmi."""
    order_id = _order_id_from_payload(query.invoice_payload)
    order = await db.get_order(order_id) if order_id else None
    ok = (
        order is not None
        and order.user_id == query.from_user.id
        and order.status == "awaiting_payment"
        and not order.paid
        and query.currency == CURRENCY
        and query.total_amount == order.total * CURRENCY_EXP
    )
    if ok:
        await query.answer(ok=True)
    else:
        log.warning("Pre-checkout rad etildi: payload=%s user=%s", query.invoice_payload, query.from_user.id)
        await query.answer(ok=False, error_message=t("payment_problem", lang))


@router.message(F.successful_payment)
async def successful_payment(message: Message, bot: Bot, db: Database, settings: Settings, lang: str) -> None:
    payment = message.successful_payment
    order_id = _order_id_from_payload(payment.invoice_payload)
    if order_id is None:
        log.error("Noma'lum to'lov payload: %s", payment.invoice_payload)
        return
    order = await db.mark_paid(order_id, payment.telegram_payment_charge_id)
    if order is None:
        log.error("To'langan buyurtma topilmadi: %s", order_id)
        return
    await db.log_event(message.from_user.id, "order", str(order.id))
    await db.log_event(message.from_user.id, "paid", str(order.id))
    await message.answer(
        t("payment_received", lang, id=order.id, bonus=_money(order.bonus_earned)),
        reply_markup=kb.main_menu(lang),
    )
    await notify_admin(bot, settings, order, message.from_user.full_name)


# --- Admin xabarlari ---------------------------------------------------------

def admin_order_text(order: Order, customer_name: str | None = None) -> str:
    lines = [f"🛒 <b>Buyurtma №{order.id}</b> ({order.status})"]
    if customer_name is not None:
        lines.append(f"👤 <a href=\"tg://user?id={order.user_id}\">{escape(customer_name)}</a>")
    lines += [f"📞 {escape(order.phone)}", f"📍 {escape(order.address)}"]
    if order.comment:
        lines.append(f"💬 {escape(order.comment)}")
    lines.append("")
    for it in order.items:
        lines.append(f"• {escape(it['name'])} × {it['qty']} = {_money(it['price'] * it['qty'])} so'm")
    lines.append("")
    if order.bonus_used:
        lines.append(f"Bonus: −{_money(order.bonus_used)} so'm")
    lines.append(f"Yetkazib berish: {_money(order.delivery_fee)} so'm" if order.delivery_fee else "Yetkazib berish: bepul")
    lines.append(f"<b>Jami: {_money(order.total)} so'm</b>")
    if order.payment_method == "online":
        lines.append("💳 Onlayn: " + ("✅ TO'LANGAN" if order.paid else "⏳ to'lanmagan"))
    else:
        lines.append("💵 Kuryerga to'lov")
    return "\n".join(lines)


async def notify_admin(bot: Bot, settings: Settings, order: Order, customer_name: str) -> None:
    if settings.admin_chat_id is None:
        log.warning("ADMIN_CHAT_ID o'rnatilmagan: buyurtma №%s haqida xabar yuborilmadi", order.id)
        return
    try:
        await bot.send_message(
            settings.admin_chat_id,
            admin_order_text(order, customer_name),
            reply_markup=kb.admin_order_kb(order.id),
        )
    except Exception:
        log.exception("Admin chatga buyurtma yuborilmadi")
