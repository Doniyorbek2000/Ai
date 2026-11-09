"""Start, til, maxfiylik, bekor qilish va asosiy menyu tugmalari.

Bu router birinchi ulanadi: menyu tugmalari istalgan holatda (FSM state) ishlaydi.
"""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    ReplyKeyboardRemove,
)

from .. import keyboards as kb
from ..catalog import Catalog
from ..config import Settings
from ..db import Database
from ..texts import LANGS, all_variants, t
from . import academy, club, look, makeup, perfume, shop, skin

router = Router(name="menu")

# Rasm talab qiladigan bo'limlar: avval rozilik so'raladi
PHOTO_FLOWS = {
    "skin": skin.start,
    "makeup": makeup.start,
    "look": look.start,
    "academy": academy.start,
}


async def show_menu(message: Message, lang: str, text_key: str = "menu", **fmt) -> None:
    await message.answer(t(text_key, lang, **fmt), reply_markup=kb.main_menu(lang))


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, db: Database, lang: str, lang_set: bool) -> None:
    await state.clear()
    user = message.from_user
    await db.ensure_user(user.id, user.full_name)
    if not lang_set:
        await message.answer(t("choose_lang", lang), reply_markup=kb.lang_kb())
        return
    await show_menu(message, lang, "welcome", name=user.first_name or "")


@router.callback_query(F.data.startswith("lang:"))
async def cb_lang(callback: CallbackQuery, db: Database) -> None:
    lang = callback.data.split(":", 1)[1]
    if lang not in LANGS:
        await callback.answer()
        return
    await db.set_lang(callback.from_user.id, lang)
    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=None)
    await show_menu(callback.message, lang, "welcome", name=callback.from_user.first_name or "")


@router.message(F.text.in_(all_variants("btn_settings")))
@router.message(Command("privacy"))
async def cmd_privacy(message: Message, lang: str) -> None:
    await message.answer(
        t("privacy", lang),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text=t("btn_change_lang", lang), callback_data="chlang")
        ]]),
    )


@router.callback_query(F.data == "chlang")
async def cb_change_lang(callback: CallbackQuery, lang: str) -> None:
    await callback.answer()
    await callback.message.answer(t("choose_lang", lang), reply_markup=kb.lang_kb())


@router.message(Command("delete_me"))
async def cmd_delete_me(message: Message, state: FSMContext, db: Database, lang: str) -> None:
    await state.clear()
    await db.delete_user(message.from_user.id)
    await message.answer(t("deleted", lang), reply_markup=ReplyKeyboardRemove())


@router.message(Command("menu"))
@router.message(F.text.in_(all_variants("btn_cancel") | all_variants("btn_menu")))
async def cmd_cancel(message: Message, state: FSMContext, lang: str) -> None:
    await state.clear()
    await show_menu(message, lang, "cancelled")


@router.callback_query(F.data == "cancel")
async def cb_cancel(callback: CallbackQuery, state: FSMContext, lang: str) -> None:
    await state.clear()
    await callback.answer(t("cancelled", lang))
    await callback.message.edit_reply_markup(reply_markup=None)
    await show_menu(callback.message, lang)


# --- Rasm bilan ishlaydigan bo'limlar (rozilik bilan) ------------------------

async def _open_photo_flow(flow: str, message: Message, state: FSMContext, db: Database, lang: str, user_id: int) -> None:
    await state.clear()
    if flow != "academy" and not await db.has_consent(user_id):
        await message.answer(t("consent", lang), reply_markup=kb.consent_kb(flow, lang))
        return
    await PHOTO_FLOWS[flow](message, state, lang)


@router.message(F.text.in_(all_variants("btn_skin")))
@router.message(Command("skin"))
async def menu_skin(message: Message, state: FSMContext, db: Database, lang: str) -> None:
    await _open_photo_flow("skin", message, state, db, lang, message.from_user.id)


@router.message(F.text.in_(all_variants("btn_makeup")))
@router.message(Command("makeup"))
async def menu_makeup(message: Message, state: FSMContext, db: Database, lang: str) -> None:
    await _open_photo_flow("makeup", message, state, db, lang, message.from_user.id)


@router.message(F.text.in_(all_variants("btn_look")))
async def menu_look(message: Message, state: FSMContext, db: Database, lang: str) -> None:
    await _open_photo_flow("look", message, state, db, lang, message.from_user.id)


@router.message(F.text.in_(all_variants("btn_academy")))
async def menu_academy(message: Message, state: FSMContext, db: Database, lang: str) -> None:
    await _open_photo_flow("academy", message, state, db, lang, message.from_user.id)


@router.callback_query(F.data.startswith("consent:"))
async def cb_consent(callback: CallbackQuery, state: FSMContext, db: Database, lang: str) -> None:
    parts = callback.data.split(":")
    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=None)
    await db.ensure_user(callback.from_user.id, callback.from_user.full_name)
    if parts[1] != "yes" or len(parts) < 3 or parts[2] not in PHOTO_FLOWS:
        await callback.message.answer(t("consent_declined", lang))
        return
    await db.set_consent(callback.from_user.id, True)
    await state.clear()
    await PHOTO_FLOWS[parts[2]](callback.message, state, lang)


# --- Boshqa bo'limlar -----------------------------------------------------

@router.message(F.text.in_(all_variants("btn_perfume")))
async def menu_perfume(message: Message, state: FSMContext, lang: str) -> None:
    await state.clear()
    await perfume.start(message, state, lang)


@router.message(F.text.in_(all_variants("btn_shop")))
@router.message(Command("shop"))
async def menu_shop(message: Message, state: FSMContext, catalog: Catalog, lang: str) -> None:
    await state.clear()
    await shop.show_categories(message, catalog, lang)


@router.message(F.text.in_(all_variants("btn_cart")))
async def menu_cart(message: Message, state: FSMContext, db: Database, catalog: Catalog, lang: str) -> None:
    await state.clear()
    await shop.show_cart(message, db, catalog, lang, message.from_user.id)


@router.message(F.text.in_(all_variants("btn_club")))
async def menu_club(message: Message, state: FSMContext, db: Database, lang: str, settings: Settings) -> None:
    await state.clear()
    await club.show(message, db, settings, lang, message.from_user.id)
