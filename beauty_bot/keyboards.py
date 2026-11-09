"""Tugmalar."""

from __future__ import annotations

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

from .catalog import Catalog, Product
from .texts import fmt_price, options, t


def main_menu(lang: str) -> ReplyKeyboardMarkup:
    b = lambda key: KeyboardButton(text=t(key, lang))  # noqa: E731
    return ReplyKeyboardMarkup(
        keyboard=[
            [b("btn_skin"), b("btn_makeup")],
            [b("btn_look"), b("btn_perfume")],
            [b("btn_academy"), b("btn_shop")],
            [b("btn_cart"), b("btn_club")],
            [b("btn_settings")],
        ],
        resize_keyboard=True,
    )


def lang_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="O'zbekcha", callback_data="lang:uz"),
        InlineKeyboardButton(text="Ўзбекча", callback_data="lang:uz_cyrl"),
        InlineKeyboardButton(text="Русский", callback_data="lang:ru"),
    ]])


def choices_kb(group: str, prefix: str, lang: str, per_row: int = 2) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for code, label in options(group, lang):
        btn = InlineKeyboardButton(text=label, callback_data=f"{prefix}:{code}")
        if rows and len(rows[-1]) < per_row:
            rows[-1].append(btn)
        else:
            rows.append([btn])
    rows.append([InlineKeyboardButton(text=t("btn_cancel", lang), callback_data="cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def consent_kb(flow: str, lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=t("consent_yes", lang), callback_data=f"consent:yes:{flow}"),
        InlineKeyboardButton(text=t("consent_no", lang), callback_data="consent:no"),
    ]])


def skip_kb(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=t("btn_skip", lang), callback_data="skip"),
        InlineKeyboardButton(text=t("btn_cancel", lang), callback_data="cancel"),
    ]])


def cancel_kb(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=t("btn_cancel", lang), callback_data="cancel")
    ]])


def products_kb(products: list[Product], lang: str, with_cart: bool = True) -> InlineKeyboardMarkup:
    """Tavsiya qilingan mahsulotlar: har biri savatga qo'shish tugmasi bilan."""
    rows = [
        [InlineKeyboardButton(text=f"🧺 {p.title(lang)}"[:60], callback_data=f"add:{p.id}:ai")]
        for p in products
    ]
    if with_cart:
        rows.append([InlineKeyboardButton(text=t("btn_cart", lang), callback_data="cart")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def categories_kb(catalog: Catalog, lang: str) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=catalog.category_title(c, lang), callback_data=f"cat:{c}")]
        for c in catalog.categories
    ]
    rows.append([InlineKeyboardButton(text=t("btn_cart", lang), callback_data="cart")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def category_products_kb(products: list[Product], lang: str) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=f"{p.title(lang)} — {fmt_price(p.price, lang)}"[:64], callback_data=f"prod:{p.id}")]
        for p in products
    ]
    rows.append([InlineKeyboardButton(text=t("btn_back", lang), callback_data="shop")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def product_kb(p: Product, lang: str) -> InlineKeyboardMarkup:
    rows = []
    if p.in_stock:
        rows.append([InlineKeyboardButton(text=t("btn_add", lang), callback_data=f"add:{p.id}")])
    rows.append([
        InlineKeyboardButton(text=t("btn_back", lang), callback_data=f"cat:{p.category}"),
        InlineKeyboardButton(text=t("btn_cart", lang), callback_data="cart"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def cart_kb(lines: list[tuple[Product, int]], lang: str) -> InlineKeyboardMarkup:
    rows = []
    for p, q in lines:
        rows.append([
            InlineKeyboardButton(text="➖", callback_data=f"dec:{p.id}"),
            InlineKeyboardButton(text=f"{p.title(lang)[:24]} ({q})", callback_data=f"prod:{p.id}"),
            InlineKeyboardButton(text="➕", callback_data=f"inc:{p.id}"),
        ])
    rows.append([
        InlineKeyboardButton(text=t("btn_clear", lang), callback_data="clear"),
        InlineKeyboardButton(text=t("btn_checkout", lang), callback_data="checkout"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def phone_kb(lang: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=t("btn_share_phone", lang), request_contact=True)],
            [KeyboardButton(text=t("btn_cancel", lang))],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def location_kb(lang: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📍", request_location=True)],
            [KeyboardButton(text=t("btn_cancel", lang))],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def bonus_kb(amount: int, lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t("btn_use_bonus", lang, amount=f"{amount:,}".replace(",", " ")), callback_data="bonus:yes")],
        [InlineKeyboardButton(text=t("btn_skip", lang), callback_data="bonus:no")],
    ])


def confirm_kb(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=t("btn_confirm", lang), callback_data="order:confirm"),
        InlineKeyboardButton(text=t("btn_cancel", lang), callback_data="cancel"),
    ]])


def payment_kb(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t("btn_pay_online", lang), callback_data="order:online")],
        [InlineKeyboardButton(text=t("btn_pay_cash", lang), callback_data="order:confirm")],
        [InlineKeyboardButton(text=t("btn_cancel", lang), callback_data="cancel")],
    ])


def admin_order_kb(order_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"adm:{order_id}:confirmed"),
        InlineKeyboardButton(text="📦 Yetkazildi", callback_data=f"adm:{order_id}:delivered"),
        InlineKeyboardButton(text="❌ Bekor", callback_data=f"adm:{order_id}:cancelled"),
    ]])


def again_kb(callback: str, label_key: str, lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=t(label_key, lang), callback_data=callback)
    ]])
