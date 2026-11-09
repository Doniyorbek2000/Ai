"""Claude API bilan ishlash: teri tahlili, stilist, makiyaj rejasi, atir va Academy suhbati."""

from __future__ import annotations

import base64
import json
import logging
from typing import TypeVar

import anthropic
from pydantic import BaseModel

from ..catalog import Catalog
from ..texts import AI_LANGUAGE_NAME, OPTIONS, norm_lang
from . import prompts
from .schemas import LookProfile, MakeupPlan, PerfumePicks, SkinAnalysis

log = logging.getLogger(__name__)

# Xavfsizlik klassifikatori oddiy so'rovni rad etsa, server boshqa modelda qayta urinadi.
FALLBACK_BETA = "server-side-fallback-2026-07-01"

M = TypeVar("M", bound=BaseModel)


class AIError(Exception):
    """AI javob bera olmadi (tarmoq, limit, noto'g'ri format)."""


class AIRefused(AIError):
    """Model so'rovni rad etdi."""


def image_block(data: bytes, media_type: str = "image/jpeg") -> dict:
    return {
        "type": "image",
        "source": {
            "type": "base64",
            "media_type": media_type,
            "data": base64.standard_b64encode(data).decode("ascii"),
        },
    }


def _language_line(lang: str) -> str:
    return f"Answer language: {AI_LANGUAGE_NAME[norm_lang(lang)]}."


def _label(group: str, code: str | None) -> str:
    """Anketa javobini model uchun kod va ruscha matn ko'rinishida beradi."""
    if not code:
        return "not specified"
    entry = OPTIONS.get(group, {}).get(code)
    return f"{code} ({entry['ru']})" if entry else code


class BeautyAI:
    def __init__(
        self,
        catalog: Catalog,
        model: str = "claude-opus-5-5",
        client: anthropic.AsyncAnthropic | None = None,
    ) -> None:
        self.catalog = catalog
        self.model = model
        self.client = client or anthropic.AsyncAnthropic()
        self._system_cache: dict[tuple[str, ...], str] = {}

    # --- Ichki yordamchilar -------------------------------------------------
    def _system(self, task: str, categories: tuple[str, ...]) -> list[dict]:
        # Barqaror qism (asosiy qoidalar + katalog) keshlanadi; vazifa matni undan keyin.
        key = categories
        if key not in self._system_cache:
            self._system_cache[key] = prompts.BASE_SYSTEM + self.catalog.ai_context(categories)
        return [
            {"type": "text", "text": self._system_cache[key], "cache_control": {"type": "ephemeral"}},
            {"type": "text", "text": task},
        ]

    async def _parse(
        self,
        task: str,
        categories: tuple[str, ...],
        content: list[dict],
        schema: type[M],
        effort: str = "medium",
    ) -> M:
        try:
            response = await self.client.beta.messages.parse(
                model=self.model,
                max_tokens=16000,
                system=self._system(task, categories),
                messages=[{"role": "user", "content": content}],
                output_format=schema,
                output_config={"effort": effort},
                betas=[FALLBACK_BETA],
                fallbacks="default",
            )
        except anthropic.BadRequestError as e:
            log.error("Claude bad request: %s", e.message)
            raise AIError(str(e.message)) from e
        except anthropic.RateLimitError as e:
            log.warning("Claude rate limited")
            raise AIError("rate_limited") from e
        except anthropic.APIStatusError as e:
            log.error("Claude API error %s: %s", e.status_code, e.message)
            raise AIError(str(e.message)) from e
        except anthropic.APIConnectionError as e:
            log.error("Claude connection error: %s", e)
            raise AIError("connection") from e

        if response.stop_reason == "refusal":
            raise AIRefused(getattr(response.stop_details, "category", None) or "refusal")
        if response.stop_reason == "max_tokens" or response.parsed_output is None:
            log.error("Claude javobi to'liq emas: stop_reason=%s", response.stop_reason)
            raise AIError("incomplete")
        return response.parsed_output

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
        content = [
            image_block(photo, media_type),
            {
                "type": "text",
                "text": f"{_language_line(lang)}\nQuestionnaire: "
                + json.dumps(questionnaire, ensure_ascii=False),
            },
        ]
        return await self._parse(prompts.SKIN_TASK, ("skincare",), content, SkinAnalysis, effort="high")

    async def ideal_look(self, photo: bytes, lang: str, media_type: str = "image/jpeg") -> LookProfile:
        content = [image_block(photo, media_type), {"type": "text", "text": _language_line(lang)}]
        return await self._parse(prompts.LOOK_TASK, ("makeup",), content, LookProfile)

    async def makeup_plan(
        self, photo: bytes, lang: str, style: str, media_type: str = "image/jpeg"
    ) -> MakeupPlan:
        look = prompts.MAKEUP_STYLE_PROMPTS.get(style, prompts.MAKEUP_STYLE_PROMPTS["daily"])
        content = [
            image_block(photo, media_type),
            {"type": "text", "text": f"{_language_line(lang)}\nRequested look ({style}): {look}"},
        ]
        return await self._parse(prompts.MAKEUP_TASK, ("makeup",), content, MakeupPlan)

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
        content = [{
            "type": "text",
            "text": f"{_language_line(lang)}\nAnswers: " + json.dumps(answers, ensure_ascii=False),
        }]
        return await self._parse(prompts.PERFUME_TASK, ("perfume",), content, PerfumePicks, effort="low")

    async def academy_reply(
        self,
        history: list[dict],
        lang: str,
        text: str | None,
        photo: bytes | None = None,
        media_type: str = "image/jpeg",
    ) -> str:
        """Beauty Academy suhbati. ``history`` — oldingi navbatlar (faqat matn)."""
        content: list[dict] = []
        if photo:
            content.append(image_block(photo, media_type))
        content.append({"type": "text", "text": f"{_language_line(lang)}\n{text or ''}".strip()})
        try:
            response = await self.client.beta.messages.create(
                model=self.model,
                max_tokens=16000,
                system=self._system(prompts.ACADEMY_TASK, ("skincare", "makeup", "perfume")),
                messages=[*history, {"role": "user", "content": content}],
                output_config={"effort": "low"},
                betas=[FALLBACK_BETA],
                fallbacks="default",
            )
        except anthropic.APIStatusError as e:
            log.error("Claude API error %s: %s", e.status_code, e.message)
            raise AIError(str(e.message)) from e
        except anthropic.APIConnectionError as e:
            raise AIError("connection") from e
        if response.stop_reason == "refusal":
            raise AIRefused("refusal")
        reply = "".join(b.text for b in response.content if b.type == "text").strip()
        if not reply:
            raise AIError("empty")
        return reply
