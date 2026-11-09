"""🌸 AI Perfume: 5 ta savol -> katalogdan 1–3 ta atir."""

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
from ..render import render_perfume
from ..texts import OPTIONS, t
from .utils import run_ai

router = Router(name="perfume")


class PerfumeStates(StatesGroup):
    for_whom = State()
    occasion = State()
    family = State()
    season = State()
    budget = State()


# (holat, callback prefiksi, saqlanadigan kalit, variantlar guruhi, keyingi holat, keyingi savol)
STEPS = [
    (PerfumeStates.for_whom, "pf_for", "for_whom", "perfume_for", PerfumeStates.occasion, ("ask_occasion", "occasion", "pf_occ")),
    (PerfumeStates.occasion, "pf_occ", "occasion", "occasion", PerfumeStates.family, ("ask_family", "family", "pf_fam")),
    (PerfumeStates.family, "pf_fam", "family", "family", PerfumeStates.season, ("ask_season", "season", "pf_sea")),
    (PerfumeStates.season, "pf_sea", "season", "season", PerfumeStates.budget, ("ask_budget", "budget", "pf_bud")),
]


async def start(message: Message, state: FSMContext, lang: str) -> None:
    await state.set_state(PerfumeStates.for_whom)
    await message.answer(t("perfume_intro", lang), reply_markup=kb.choices_kb("perfume_for", "pf_for", lang))


def _make_step(cur_state, prefix, key, group, next_state, next_q):
    q_key, q_group, q_prefix = next_q

    async def handler(callback: CallbackQuery, state: FSMContext, lang: str) -> None:
        code = callback.data.split(":", 1)[1]
        await callback.answer()
        if code not in OPTIONS[group]:
            return
        await state.update_data(**{key: code})
        await state.set_state(next_state)
        await callback.message.edit_text(t(q_key, lang), reply_markup=kb.choices_kb(q_group, q_prefix, lang))

    handler.__name__ = f"cb_{key}"
    router.callback_query.register(handler, cur_state, F.data.startswith(f"{prefix}:"))


for _step in STEPS:
    _make_step(*_step)


@router.callback_query(PerfumeStates.budget, F.data.startswith("pf_bud:"))
async def cb_budget(
    callback: CallbackQuery,
    state: FSMContext,
    bot: Bot,
    db: Database,
    ai: BeautyAI,
    catalog: Catalog,
    settings: Settings,
    lang: str,
) -> None:
    code = callback.data.split(":", 1)[1]
    await callback.answer()
    if code not in OPTIONS["budget"]:
        return
    answers = await state.get_data()
    await state.clear()
    await callback.message.edit_text(t("picking", lang))
    message = callback.message
    async with ChatActionSender.typing(bot=bot, chat_id=message.chat.id):
        result = await run_ai(
            message, db, settings, lang, callback.from_user.id,
            lambda: ai.pick_perfume(
                lang,
                for_whom=answers.get("for_whom"),
                occasion=answers.get("occasion"),
                family=answers.get("family"),
                season=answers.get("season"),
                budget=code,
            ),
        )
    if result is None:
        return
    text, products = render_perfume(result, catalog, lang)
    await message.answer(text, reply_markup=kb.products_kb(products, lang) if products else None)
