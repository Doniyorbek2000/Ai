"""🎬 Beauty Academy: Reels, suratga tushish, makiyaj texnikasi bo'yicha suhbat."""

from __future__ import annotations

from html import escape

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message
from aiogram.utils.chat_action import ChatActionSender

from .. import keyboards as kb
from ..ai.claude import BeautyAI
from ..config import Settings
from ..db import Database
from ..texts import t
from .utils import download_photo, run_ai, send_long

router = Router(name="academy")

MAX_HISTORY_MESSAGES = 12  # oxirgi 6 savol-javob
PHOTO_PLACEHOLDER = "[photo sent]"


class AcademyStates(StatesGroup):
    chat = State()


async def start(message: Message, state: FSMContext, lang: str) -> None:
    await state.set_state(AcademyStates.chat)
    await state.update_data(history=[])
    await message.answer(t("academy_intro", lang), reply_markup=kb.main_menu(lang))


def trim_history(history: list[dict]) -> list[dict]:
    """Oxirgi xabarlarni saqlaydi; tarix doim 'user' xabari bilan boshlanadi."""
    trimmed = history[-MAX_HISTORY_MESSAGES:]
    while trimmed and trimmed[0]["role"] != "user":
        trimmed = trimmed[1:]
    return trimmed


@router.message(AcademyStates.chat, F.text | F.photo | F.document)
async def msg_chat(
    message: Message,
    state: FSMContext,
    bot: Bot,
    db: Database,
    ai: BeautyAI,
    settings: Settings,
    lang: str,
) -> None:
    text = (message.text or message.caption or "").strip()[:2000]
    photo = None
    if message.photo or message.document:
        if not await db.has_consent(message.from_user.id):
            await message.answer(t("consent", lang), reply_markup=kb.consent_kb("academy", lang))
            return
        photo = await download_photo(message, bot)
        if photo is None:
            await message.answer(t("send_photo_not_file", lang))
            return
    if not text and photo is None:
        return

    history = trim_history((await state.get_data()).get("history", []))
    async with ChatActionSender.typing(bot=bot, chat_id=message.chat.id):
        reply = await run_ai(
            message, db, settings, lang, message.from_user.id,
            lambda: ai.academy_reply(
                history, lang, text,
                photo=photo[0] if photo else None,
                media_type=photo[1] if photo else "image/jpeg",
            ),
        )
    if reply is None:
        return
    # Tarixda rasm o'rniga belgi saqlanadi (rasmlar saqlanmaydi)
    user_turn = f"{PHOTO_PLACEHOLDER} {text}".strip() if photo else text
    history = trim_history([*history, {"role": "user", "content": user_turn}, {"role": "assistant", "content": reply}])
    await state.update_data(history=history)

    await send_long(message, escape(reply, quote=False))
