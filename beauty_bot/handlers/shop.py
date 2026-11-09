"""🛍 Do'kon: katalog, savat va buyurtma berish."""

from __future__ import annotations

import logging
import re
from html import escape

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from .. import keyboards as kb
from ..catalog import Catalog
from ..config import Settings
from ..db import Database, Order
from ..render import cart_lines, render_cart, render_product_card
from ..texts import fmt_price, t

log = logging.getLogger(__name__)
router = Router(name="shop")

PHONE_RE = re.compile(r"^\+?998\d{9}$")


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
    p = catalog.get(callback.data.split(":", 1)[1])
    if p is None or not p.in_stock:
        await callback.answer(t("out_of_stock", lang), show_alert=True)
        return
    await db.ensure_user(callback.from_user.id, callback.from_user.full_name)
    await db.cart_add(callback.from_user.id, p.id, 1)
    await callback.answer(f"{t('added', lang)}: {p.title(lang)}")


async def show_cart(message: Message, db: Database, catalog: Catalog, lang: str, user_id: int, edit: bool = False) -> None:
    lines = cart_lines(await db.cart_items(user_id), catalog)
    text, _ = render_cart(lines, lang)
    markup = kb.cart_kb(lines, lang) if lines else None
    if edit:
        try:
            await message.edit_text(text, reply_markup=markup)
            return
        except TelegramBadRequest:
            pass
    await message.answer(text, reply_markup=markup)


@router.callback_query(F.data == "cart")
async def cb_cart(callback: CallbackQuery, db: Database, catalog: Catalog, lang: str) -> None:
    await callback.answer()
    await show_cart(callback.message, db, catalog, lang, callback.from_user.id)


@router.callback_query(F.data.startswith("inc:") | F.data.startswith("dec:"))
async def cb_qty(callback: CallbackQuery, db: Database, catalog: Catalog, lang: str) -> None:
    op, pid = callback.data.split(":", 1)
    await db.cart_add(callback.from_user.id, pid, 1 if op == "inc" else -1)
    await callback.answer()
    await show_cart(callback.message, db, catalog, lang, callback.from_user.id, edit=True)


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


async def _after_comment(message: Message, state: FSMContext, db: Database, catalog: Catalog, lang: str, user_id: int) -> None:
    balance = await db.get_bonus(user_id)
    if balance > 0:
        await state.set_state(CheckoutStates.bonus)
        await message.answer("💎", reply_markup=kb.bonus_kb(balance, lang))
        return
    await state.update_data(use_bonus=False)
    await _show_confirm(message, state, db, catalog, lang, user_id)


@router.message(CheckoutStates.comment, F.text)
async def msg_comment(message: Message, state: FSMContext, db: Database, catalog: Catalog, lang: str) -> None:
    await state.update_data(comment=message.text.strip()[:500])
    await _after_comment(message, state, db, catalog, lang, message.from_user.id)


@router.callback_query(CheckoutStates.comment, F.data == "skip")
async def cb_skip_comment(callback: CallbackQuery, state: FSMContext, db: Database, catalog: Catalog, lang: str) -> None:
    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=None)
    await state.update_data(comment=None)
    await _after_comment(callback.message, state, db, catalog, lang, callback.from_user.id)


@router.callback_query(CheckoutStates.bonus, F.data.startswith("bonus:"))
async def cb_bonus(callback: CallbackQuery, state: FSMContext, db: Database, catalog: Catalog, lang: str) -> None:
    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=None)
    await state.update_data(use_bonus=callback.data == "bonus:yes")
    await _show_confirm(callback.message, state, db, catalog, lang, callback.from_user.id)


async def _show_confirm(message: Message, state: FSMContext, db: Database, catalog: Catalog, lang: str, user_id: int) -> None:
    data = await state.get_data()
    lines = cart_lines(await db.cart_items(user_id), catalog)
    if not lines:
        await state.clear()
        await message.answer(t("cart_empty", lang), reply_markup=kb.main_menu(lang))
        return
    cart_text, subtotal = render_cart(lines, lang)
    if data.get("use_bonus"):
        used = min(await db.get_bonus(user_id), subtotal)
        if used:
            cart_text += "\n" + t("use_bonus", lang, amount=f"{used:,}".replace(",", " "))
            cart_text += f"\n<b>{t('total', lang)}: {fmt_price(subtotal - used, lang)}</b>"
    await state.set_state(CheckoutStates.confirm)
    await message.answer(
        t("confirm_order", lang, cart=cart_text, phone=escape(data["phone"]),
          address=escape(data["address"]), comment=escape(data.get("comment") or "—")),
        reply_markup=kb.confirm_kb(lang),
    )


@router.callback_query(CheckoutStates.confirm, F.data == "order:confirm")
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
    items = [{"id": p.id, "name": p.name.get("uz", p.id), "price": p.price, "qty": q} for p, q in lines]
    subtotal = sum(p.price * q for p, q in lines)
    bonus_used = await db.get_bonus(user_id) if data.get("use_bonus") else 0
    order = await db.create_order(
        user_id=user_id,
        items=items,
        subtotal=subtotal,
        bonus_used=bonus_used,
        phone=data["phone"],
        address=data["address"],
        comment=data.get("comment"),
        bonus_percent=settings.bonus_percent,
    )
    await state.clear()
    await callback.message.answer(
        t("order_placed", lang, id=order.id, bonus=f"{order.bonus_earned:,}".replace(",", " ")),
        reply_markup=kb.main_menu(lang),
    )
    await notify_admin(bot, settings, order, callback.from_user.full_name, user_id)


def admin_order_text(order: Order, customer_name: str | None = None) -> str:
    lines = [f"🛒 <b>Buyurtma №{order.id}</b> ({order.status})"]
    if customer_name is not None:
        lines.append(f"👤 <a href=\"tg://user?id={order.user_id}\">{escape(customer_name)}</a>")
    lines += [f"📞 {escape(order.phone)}", f"📍 {escape(order.address)}"]
    if order.comment:
        lines.append(f"💬 {escape(order.comment)}")
    lines.append("")
    for it in order.items:
        lines.append(f"• {escape(it['name'])} × {it['qty']} = {it['price'] * it['qty']:,} so'm".replace(",", " "))
    lines.append("")
    if order.bonus_used:
        lines.append(f"Bonus: −{order.bonus_used:,} so'm".replace(",", " "))
    lines.append(f"<b>Jami: {order.total:,} so'm</b>".replace(",", " "))
    return "\n".join(lines)


async def notify_admin(bot: Bot, settings: Settings, order: Order, customer_name: str, user_id: int) -> None:
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
