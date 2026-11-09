"""💋 AI makiyaj: uslub tanlash + rasm -> makiyajli rasm, makiyaj rejasi va mahsulotlar."""

from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import BufferedInputFile, CallbackQuery, Message
from aiogram.utils.chat_action import ChatActionSender

from .. import keyboards as kb
from ..ai.errors import AIError
from ..ai.gemini import BeautyAI
from ..ai.makeup import MakeupImageProvider
from ..ai.schemas import MakeupPlan
from ..catalog import Catalog
from ..config import Settings
from ..db import Database
from ..render import render_makeup_plan, render_products
from ..texts import OPTIONS, opt, t
from .utils import download_photo, run_ai, send_long

log = logging.getLogger(__name__)
router = Router(name="makeup")


class MakeupStates(StatesGroup):
    style = State()
    photo = State()


async def start(message: Message, state: FSMContext, lang: str) -> None:
    await state.set_state(MakeupStates.style)
    await message.answer(t("makeup_intro", lang), reply_markup=kb.choices_kb("makeup_style", "mk", lang))


@router.callback_query(F.data == "mk_again")
async def cb_again(callback: CallbackQuery, state: FSMContext, lang: str) -> None:
    await callback.answer()
    await start(callback.message, state, lang)


@router.callback_query(MakeupStates.style, F.data.startswith("mk:"))
async def cb_style(callback: CallbackQuery, state: FSMContext, lang: str) -> None:
    style = callback.data.split(":", 1)[1]
    if style not in OPTIONS["makeup_style"]:
        await callback.answer()
        return
    await state.update_data(style=style)
    await state.set_state(MakeupStates.photo)
    await callback.answer()
    await callback.message.edit_text(t("send_photo", lang), reply_markup=kb.cancel_kb(lang))


@router.message(MakeupStates.photo, F.photo | F.document)
async def msg_photo(
    message: Message,
    state: FSMContext,
    bot: Bot,
    db: Database,
    ai: BeautyAI,
    catalog: Catalog,
    settings: Settings,
    image_provider: MakeupImageProvider | None,
    lang: str,
) -> None:
    photo = await download_photo(message, bot)
    if photo is None:
        await message.answer(t("send_photo_not_file", lang))
        return
    data, media_type = photo
    style = (await state.get_data()).get("style", "daily")
    await message.answer(t("makeup_generating", lang))

    async def work() -> tuple[MakeupPlan | None, bytes | None]:
        tasks = [ai.makeup_plan(data, lang, style, media_type)]
        if image_provider:
            tasks.append(image_provider.apply(data, style, media_type))
        results = await asyncio.gather(*tasks, return_exceptions=True)
        plan = results[0]
        image = results[1] if len(results) > 1 else None
        if isinstance(image, BaseException):
            log.warning("Makiyaj rasmi tayyorlanmadi: %s", image)
            image = None
        if isinstance(plan, BaseException):
            if image is None:
                raise plan if isinstance(plan, AIError) else AIError(str(plan))
            log.warning("Makiyaj rejasi tayyorlanmadi: %s", plan)
            plan = None
        return plan, image

    action = ChatActionSender.upload_photo if image_provider else ChatActionSender.typing
    async with action(bot=bot, chat_id=message.chat.id):
        result = await run_ai(message, db, settings, lang, message.from_user.id, work)
    if result is None:
        return
    plan, image = result
    if plan is not None and not plan.is_face_photo:
        await message.answer(t("not_face", lang))
        return

    await state.clear()
    style_name = opt("makeup_style", style, lang)
    if image:
        await message.answer_photo(
            BufferedInputFile(image, filename="ai_beauty_makeup.png"),
            caption=t("makeup_caption", lang, style=style_name),
        )
    elif image_provider:
        await message.answer(t("makeup_image_failed", lang))

    if plan is not None:
        await send_long(message, render_makeup_plan(plan, lang))
        products = catalog.valid_ids(plan.product_ids)
        if products:
            await message.answer(render_products(products, lang), reply_markup=kb.products_kb(products, lang))
    await message.answer(t("menu", lang), reply_markup=kb.again_kb("mk_again", "makeup_again", lang))


@router.message(MakeupStates.photo)
async def msg_not_photo(message: Message, lang: str) -> None:
    await message.answer(t("send_photo", lang), reply_markup=kb.cancel_kb(lang))
