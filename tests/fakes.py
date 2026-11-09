"""Testlar uchun soxta AI javoblari va Telegram sessiyasi."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from aiogram import Bot
from aiogram.client.session.base import BaseSession
from aiogram.methods import GetFile, TelegramMethod
from aiogram.types import Chat, File, Message

from beauty_bot.ai.schemas import LookProfile, MakeupPlan, Observation, PerfumePick, PerfumePicks, RoutineStep, SkinAnalysis


def skin_result(**overrides) -> SkinAnalysis:
    data = dict(
        is_face_photo=True,
        photo_usable=True,
        photo_tip="",
        skin_type="oily",
        skin_type_label="Yog'li",
        summary="Teringiz umuman sog'lom <ko'rinadi>.",
        observations=[Observation(name="Toshmalar", area="iyak", likelihood="medium", note="Gormonal bo'lishi mumkin")],
        morning_routine=[RoutineStep(step="Tozalash", product_id="sk-cleanser-gel", how="Iliq suv bilan")],
        evening_routine=[RoutineStep(step="BHA", product_id="sk-bha-toner", how="Haftasiga 2 marta")],
        tips=["Yostiq jildini tez-tez almashtiring"],
        see_dermatologist=False,
        dermatologist_reason="",
        urgent=False,
        urgent_reason="",
        product_ids=["sk-cleanser-gel", "sk-bha-toner", "made-up-id"],
    )
    data.update(overrides)
    return SkinAnalysis(**data)


class FakeAI:
    """BeautyAI o'rnini bosadi: chaqiruvlarni yozib boradi."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []
        self.skin = skin_result()

    async def analyze_skin(self, photo, lang, **kw):
        self.calls.append(("skin", {"lang": lang, "size": len(photo), **kw}))
        return self.skin

    async def ideal_look(self, photo, lang, media_type="image/jpeg"):
        self.calls.append(("look", {"lang": lang}))
        return LookProfile(is_face_photo=True, face_shape="oval", undertone="iliq", color_type="kuz",
                           best_colors=["terrakota"], avoid_colors=["neon"], brows="yumshoq", hair="to'lqin",
                           makeup="shaftoli", summary="Sizga iliq ranglar yarashadi", product_ids=["mk-blush"])

    async def makeup_plan(self, photo, lang, style, media_type="image/jpeg"):
        self.calls.append(("makeup", {"lang": lang, "style": style}))
        return MakeupPlan(is_face_photo=True, summary="Yarashadi", steps=["Tonal", "Tush"], product_ids=["mk-mascara"])

    async def pick_perfume(self, lang, **kw):
        self.calls.append(("perfume", {"lang": lang, **kw}))
        return PerfumePicks(intro="Mana", picks=[PerfumePick(product_id="pf-peach", why="Shirin"),
                                                 PerfumePick(product_id="sk-spf50", why="atir emas")])

    async def academy_reply(self, history, lang, text, photo=None, media_type="image/jpeg"):
        self.calls.append(("academy", {"history": list(history), "text": text, "photo": photo is not None}))
        return f"Javob <{len(history)}>"


class FakeImageProvider:
    def __init__(self) -> None:
        self.calls = 0

    async def apply(self, photo, style, media_type="image/jpeg"):
        self.calls += 1
        return b"\x89PNG fake"


class FakeSession(BaseSession):
    """Telegramga yuborilgan barcha so'rovlarni yozib boradi."""

    def __init__(self) -> None:
        super().__init__()
        self.requests: list[TelegramMethod] = []
        self._msg_id = 100

    async def make_request(self, bot: Bot, method: TelegramMethod, timeout: int | None = None) -> Any:
        self.requests.append(method)
        if isinstance(method, GetFile):
            return File(file_id=method.file_id, file_unique_id="u", file_path="photos/face.jpg", file_size=10)
        returning = getattr(method, "__returning__", None)
        if returning is Message:
            self._msg_id += 1
            chat_id = getattr(method, "chat_id", 1)
            return Message(message_id=self._msg_id, date=datetime.now(),
                           chat=Chat(id=chat_id if isinstance(chat_id, int) else 1, type="private"),
                           text=getattr(method, "text", None) or getattr(method, "caption", None))
        return True

    async def stream_content(self, url, headers=None, timeout=30, chunk_size=65536, raise_for_status=True):
        yield b"\xff\xd8 fake jpeg bytes"

    async def close(self) -> None:
        pass

    def sent(self, kind: type | None = None) -> list[TelegramMethod]:
        return [r for r in self.requests if kind is None or isinstance(r, kind)]

    def texts(self) -> list[str]:
        out = []
        for r in self.requests:
            for attr in ("text", "caption"):
                val = getattr(r, attr, None)
                if isinstance(val, str):
                    out.append(val)
        return out
