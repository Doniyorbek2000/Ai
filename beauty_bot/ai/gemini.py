"""Gemini API bilan ishlash: teri tahlili, stilist, makiyaj rejasi, atir va Academy suhbati."""

from __future__ import annotations

import json
import logging
from typing import TypeVar

from google import genai
from google.genai import errors, types
from pydantic import BaseModel, ValidationError

from ..catalog import Catalog
from ..texts import AI_LANGUAGE_NAME, OPTIONS, norm_lang
from . import prompts
from .errors import AIError, AIRefused
from .schemas import LookProfile, MakeupPlan, PerfumePicks, SkinAnalysis

log = logging.getLogger(__name__)

M = TypeVar("M", bound=BaseModel)

BLOCKED_FINISH_REASONS = {
    types.FinishReason.SAFETY,
    types.FinishReason.PROHIBITED_CONTENT,
    types.FinishReason.BLOCKLIST,
    types.FinishReason.SPII,
    types.FinishReason.IMAGE_SAFETY,
    types.FinishReason.IMAGE_PROHIBITED_CONTENT,
}


def image_part(data: bytes, media_type: str = "image/jpeg") -> types.Part:
    return types.Part.from_bytes(data=data, mime_type=media_type)


def _language_line(lang: str) -> str:
    return f"Answer language: {AI_LANGUAGE_NAME[norm_lang(lang)]}."


def _label(group: str, code: str | None) -> str:
    """Anketa javobini model uchun kod va ruscha matn ko'rinishida beradi."""
    if not code:
        return "not specified"
    entry = OPTIONS.get(group, {}).get(code)
    return f"{code} ({entry['ru']})" if entry else code


def check_response(response: types.GenerateContentResponse) -> types.Candidate:
    """Bloklangan yoki bo'sh javobni xatoga aylantiradi, birinchi nomzodni qaytaradi."""
    feedback = response.prompt_feedback
    if feedback is not None and feedback.block_reason:
        raise AIRefused(str(feedback.block_reason))
    if not response.candidates:
        raise AIError("no candidates")
    candidate = response.candidates[0]
    if candidate.finish_reason in BLOCKED_FINISH_REASONS:
        raise AIRefused(str(candidate.finish_reason))
    if candidate.finish_reason == types.FinishReason.MAX_TOKENS:
        raise AIError("max_tokens")
    return candidate


async def call_gemini(client: genai.Client, **kwargs) -> types.GenerateContentResponse:
    try:
        return await client.aio.models.generate_content(**kwargs)
    except errors.ClientError as e:  # 4xx: kalit, kvota, noto'g'ri so'rov
        log.error("Gemini client error %s: %s", e.code, e.message)
        raise AIError(f"client {e.code}") from e
    except errors.ServerError as e:  # 5xx
        log.error("Gemini server error %s: %s", e.code, e.message)
        raise AIError(f"server {e.code}") from e
    except errors.APIError as e:
        log.error("Gemini API error %s: %s", e.code, e.message)
        raise AIError(str(e.code)) from e


class BeautyAI:
    def __init__(
        self,
        catalog: Catalog,
        model: str = "gemini-3.5-flash",
        client: genai.Client | None = None,
    ) -> None:
        self.catalog = catalog
        self.model = model
        # Kalit GEMINI_API_KEY muhit o'zgaruvchisidan o'qiladi
        self.client = client or genai.Client()

    def _system(self, task: str, categories: tuple[str, ...]) -> str:
        # Har safar yangidan: admin narx yoki mavjudlikni o'zgartirsa, AI darhol yangisini ko'radi
        return f"{prompts.BASE_SYSTEM}{self.catalog.ai_context(categories)}\n\n{task}"

    async def _parse(
        self,
        task: str,
        categories: tuple[str, ...],
        parts: list[types.Part | str],
        schema: type[M],
        thinking: types.ThinkingLevel = types.ThinkingLevel.MEDIUM,
    ) -> M:
        response = await call_gemini(
            self.client,
            model=self.model,
            contents=[types.Content(role="user", parts=[p if isinstance(p, types.Part) else types.Part(text=p) for p in parts])],
            config=types.GenerateContentConfig(
                system_instruction=self._system(task, categories),
                response_mime_type="application/json",
                response_schema=schema,
                thinking_config=types.ThinkingConfig(thinking_level=thinking),
                max_output_tokens=16000,
            ),
        )
        check_response(response)
        parsed = response.parsed
        if isinstance(parsed, schema):
            return parsed
        try:  # SDK parse qila olmagan bo'lsa, matndan o'zimiz o'qiymiz
            return schema.model_validate(json.loads(response.text or ""))
        except (ValueError, ValidationError) as e:
            log.error("Gemini javobi formatga mos emas: %s", (response.text or "")[:300])
            raise AIError("bad_format") from e

    # --- Ommaviy funksiyalar -------------------------------------------------
    async def analyze_skin(
        self,
        photo: bytes,
        lang: str,
        age: str | None,
        skin_feel: str | None,
        concern: str | None,
        extra: str | None,
        media_type: str = "image/jpeg",
    ) -> SkinAnalysis:
        questionnaire = {
            "age_group": _label("age", age),
            "how_skin_feels": _label("skin_feel", skin_feel),
            "main_concern": _label("concern", concern),
            "extra_info_from_user": extra or "none",
        }
        text = f"{_language_line(lang)}\nQuestionnaire: " + json.dumps(questionnaire, ensure_ascii=False)
        return await self._parse(
            prompts.SKIN_TASK, ("skincare",), [image_part(photo, media_type), text], SkinAnalysis,
            thinking=types.ThinkingLevel.HIGH,
        )

    async def ideal_look(self, photo: bytes, lang: str, media_type: str = "image/jpeg") -> LookProfile:
        return await self._parse(
            prompts.LOOK_TASK, ("makeup",), [image_part(photo, media_type), _language_line(lang)], LookProfile
        )

    async def makeup_plan(
        self, photo: bytes, lang: str, style: str, media_type: str = "image/jpeg"
    ) -> MakeupPlan:
        look = prompts.MAKEUP_STYLE_PROMPTS.get(style, prompts.MAKEUP_STYLE_PROMPTS["daily"])
        text = f"{_language_line(lang)}\nRequested look ({style}): {look}"
        return await self._parse(
            prompts.MAKEUP_TASK, ("makeup",), [image_part(photo, media_type), text], MakeupPlan
        )

    async def pick_perfume(
        self,
        lang: str,
        for_whom: str | None,
        occasion: str | None,
        family: str | None,
        season: str | None,
        budget: str | None,
    ) -> PerfumePicks:
        answers = {
            "for_whom": _label("perfume_for", for_whom),
            "occasion": _label("occasion", occasion),
            "liked_scent_family": _label("family", family),
            "season": _label("season", season),
            "budget": _label("budget", budget),
        }
        text = f"{_language_line(lang)}\nAnswers: " + json.dumps(answers, ensure_ascii=False)
        return await self._parse(
            prompts.PERFUME_TASK, ("perfume",), [text], PerfumePicks, thinking=types.ThinkingLevel.LOW
        )

    async def academy_reply(
        self,
        history: list[dict],
        lang: str,
        text: str | None,
        photo: bytes | None = None,
        media_type: str = "image/jpeg",
    ) -> str:
        """Beauty Academy suhbati. ``history`` — oldingi navbatlar: {"role": "user"|"assistant", "content": str}."""
        contents = [
            types.Content(
                role="model" if turn["role"] == "assistant" else "user",
                parts=[types.Part(text=turn["content"])],
            )
            for turn in history
        ]
        parts: list[types.Part] = []
        if photo:
            parts.append(image_part(photo, media_type))
        parts.append(types.Part(text=f"{_language_line(lang)}\n{text or ''}".strip()))
        contents.append(types.Content(role="user", parts=parts))

        response = await call_gemini(
            self.client,
            model=self.model,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=self._system(prompts.ACADEMY_TASK, ("skincare", "makeup", "perfume")),
                thinking_config=types.ThinkingConfig(thinking_level=types.ThinkingLevel.LOW),
                max_output_tokens=8000,
            ),
        )
        candidate = check_response(response)
        parts_out = candidate.content.parts if candidate.content and candidate.content.parts else []
        reply = "".join(p.text for p in parts_out if p.text and not p.thought).strip()
        if not reply:
            raise AIError("empty")
        return reply

    async def available_models(self) -> set[str]:
        """Kalit bilan ishlatish mumkin bo'lgan modellar (ishga tushishda tekshirish uchun)."""
        names: set[str] = set()
        async for m in await self.client.aio.models.list():
            if m.name:
                names.add(m.name.removeprefix("models/"))
        return names
