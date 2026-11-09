"""✨ Ideal obraz: yuz shakli, rang tipi, qosh, soch va makiyaj bo'yicha shaxsiy maslahat."""

from __future__ import annotations

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message
from aiogram.utils.chat_action import ChatActionSender

from .. import keyboards as kb
from ..ai.gemini import BeautyAI
from ..catalog import Catalog
from ..config import Settings
from ..db import Database
from ..render import render_look, render_products
from ..texts import t
from .utils import download_photo, run_ai, send_long

router = Router(name="look")


class LookStates(StatesGroup):
    photo = State()


async def start(message: Message, state: FSMContext, lang: str) -> None:
    await state.set_state(LookStates.photo)
    await message.answer(t("look_intro", lang), reply_markup=kb.cancel_kb(lang))


@router.message(LookStates.photo, F.photo | F.document)
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
    await message.answer(t("analyzing", lang))
    async with ChatActionSender.typing(bot=bot, chat_id=message.chat.id):
        result = await run_ai(
            message, db, settings, lang, message.from_user.id,
            lambda: ai.ideal_look(data, lang, media_type),
        )
    if result is None:
        return
    if not result.is_face_photo:
        await message.answer(t("not_face", lang))
        return
    await state.clear()
    await send_long(message, render_look(result, lang), reply_markup=kb.main_menu(lang))
    products = catalog.valid_ids(result.product_ids)
    if products:
        await message.answer(render_products(products, lang), reply_markup=kb.products_kb(products, lang))


@router.message(LookStates.photo)
async def msg_not_photo(message: Message, lang: str) -> None:
    await message.answer(t("look_intro", lang), reply_markup=kb.cancel_kb(lang))
