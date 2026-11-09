"""🔬 AI Skin Doctor: anketa + yuz rasmi -> teri tahlili va parvarish rejasi."""

from __future__ import annotations

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from aiogram.utils.chat_action import ChatActionSender

from .. import keyboards as kb
from ..ai.claude import BeautyAI
from ..catalog import Catalog
from ..config import Settings
from ..db import Database
from ..render import render_products, render_skin
from ..texts import OPTIONS, t
from .utils import download_photo, run_ai, send_long

router = Router(name="skin")


class SkinStates(StatesGroup):
    age = State()
    feel = State()
    concern = State()
    extra = State()
    photo = State()


async def start(message: Message, state: FSMContext, lang: str) -> None:
    await state.set_state(SkinStates.age)
    await message.answer(t("skin_intro", lang), reply_markup=kb.choices_kb("age", "sk_age", lang, per_row=3))


def _code(callback: CallbackQuery, group: str) -> str | None:
    code = callback.data.split(":", 1)[1]
    return code if code in OPTIONS[group] else None


@router.callback_query(SkinStates.age, F.data.startswith("sk_age:"))
async def cb_age(callback: CallbackQuery, state: FSMContext, lang: str) -> None:
    await state.update_data(age=_code(callback, "age"))
    await state.set_state(SkinStates.feel)
    await callback.answer()
    await callback.message.edit_text(t("ask_skin_feel", lang), reply_markup=kb.choices_kb("skin_feel", "sk_feel", lang))


@router.callback_query(SkinStates.feel, F.data.startswith("sk_feel:"))
async def cb_feel(callback: CallbackQuery, state: FSMContext, lang: str) -> None:
    await state.update_data(skin_feel=_code(callback, "skin_feel"))
    await state.set_state(SkinStates.concern)
    await callback.answer()
    await callback.message.edit_text(t("ask_concern", lang), reply_markup=kb.choices_kb("concern", "sk_conc", lang))


@router.callback_query(SkinStates.concern, F.data.startswith("sk_conc:"))
async def cb_concern(callback: CallbackQuery, state: FSMContext, lang: str) -> None:
    await state.update_data(concern=_code(callback, "concern"))
    await state.set_state(SkinStates.extra)
    await callback.answer()
    await callback.message.edit_text(t("ask_extra", lang), reply_markup=kb.skip_kb(lang))


@router.callback_query(SkinStates.extra, F.data == "skip")
async def cb_skip_extra(callback: CallbackQuery, state: FSMContext, lang: str) -> None:
    await state.set_state(SkinStates.photo)
    await callback.answer()
    await callback.message.edit_text(t("send_photo", lang), reply_markup=kb.cancel_kb(lang))


@router.message(SkinStates.extra, F.text)
async def msg_extra(message: Message, state: FSMContext, lang: str) -> None:
    await state.update_data(extra=message.text[:800])
    await state.set_state(SkinStates.photo)
    await message.answer(t("send_photo", lang), reply_markup=kb.cancel_kb(lang))


@router.message(SkinStates.photo, F.photo | F.document)
async def msg_photo(
    message: Message,
    state: FSMContext,
    bot: Bot,
    db: Database,
    ai: BeautyAI,
    catalog: Catalog,
    settings: Settings,
    lang: str,
) -> None:
    photo = await download_photo(message, bot)
    if photo is None:
        await message.answer(t("send_photo_not_file", lang))
        return
    data, media_type = photo
    answers = await state.get_data()
    await message.answer(t("analyzing", lang))
    async with ChatActionSender.typing(bot=bot, chat_id=message.chat.id):
        result = await run_ai(
            message, db, settings, lang, message.from_user.id,
            lambda: ai.analyze_skin(
                data, lang,
                age=answers.get("age"),
                skin_feel=answers.get("skin_feel"),
                concern=answers.get("concern"),
                extra=answers.get("extra"),
                media_type=media_type,
            ),
        )
    if result is None:
        return  # xato xabari yuborilgan; holat saqlanadi, qayta rasm yuborish mumkin
    if not result.is_face_photo:
        await message.answer(t("not_face", lang))
        return
    await state.clear()
    await send_long(message, render_skin(result, catalog, lang), reply_markup=kb.main_menu(lang))
    products = catalog.valid_ids(result.product_ids)
    if products:
        await message.answer(render_products(products, lang), reply_markup=kb.products_kb(products, lang))


@router.message(SkinStates.photo)
async def msg_not_photo(message: Message, lang: str) -> None:
    await message.answer(t("send_photo", lang), reply_markup=kb.cancel_kb(lang))
