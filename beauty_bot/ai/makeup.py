"""Rasmga makiyaj qo'yish: Gemini rasm tahrirlash modeli (Nano Banana) orqali.

Rasm yaratish o'chirilgan bo'lsa (MAKEUP_IMAGES=0), bot faqat matnli makiyaj rejasini yuboradi.
"""

from __future__ import annotations

import logging
from typing import Protocol

from google import genai
from google.genai import types

from .errors import AIError
from .gemini import call_gemini, check_response, image_part
from .prompts import MAKEUP_IMAGE_PROMPT, MAKEUP_STYLE_PROMPTS

log = logging.getLogger(__name__)


class MakeupImageError(Exception):
    pass


class MakeupImageProvider(Protocol):
    async def apply(self, photo: bytes, style: str, media_type: str = "image/jpeg") -> bytes: ...


def build_prompt(style: str) -> str:
    look = MAKEUP_STYLE_PROMPTS.get(style, MAKEUP_STYLE_PROMPTS["daily"])
    return MAKEUP_IMAGE_PROMPT.format(look=look)


class GeminiImageProvider:
    def __init__(self, client: genai.Client, model: str) -> None:
        self.client = client
        self.model = model

    async def apply(self, photo: bytes, style: str, media_type: str = "image/jpeg") -> bytes:
        try:
            response = await call_gemini(
                self.client,
                model=self.model,
                contents=[types.Content(role="user", parts=[image_part(photo, media_type), types.Part(text=build_prompt(style))])],
                config=types.GenerateContentConfig(response_modalities=["IMAGE"]),
            )
            candidate = check_response(response)
        except AIError as e:
            raise MakeupImageError(str(e)) from e
        for part in (candidate.content.parts if candidate.content and candidate.content.parts else []):
            if part.inline_data and part.inline_data.data:
                return part.inline_data.data
        log.warning("Gemini rasm qaytarmadi: finish_reason=%s", candidate.finish_reason)
        raise MakeupImageError("no image in response")
