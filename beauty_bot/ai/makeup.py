"""Rasmga makiyaj qo'yish (rasm tahrirlash modeli orqali).

Claude rasm yaratmaydi, shuning uchun bu qism alohida provayder orqali ishlaydi.
Hozircha OpenAI Images (gpt-image-1) qo'llab-quvvatlanadi. Provayder sozlanmagan
bo'lsa, bot faqat Claude tayyorlagan matnli makiyaj rejasini yuboradi.
"""

from __future__ import annotations

import base64
import logging
from typing import Protocol

import httpx

from .prompts import MAKEUP_IMAGE_PROMPT, MAKEUP_STYLE_PROMPTS

log = logging.getLogger(__name__)


class MakeupImageError(Exception):
    pass


class MakeupImageProvider(Protocol):
    async def apply(self, photo: bytes, style: str, media_type: str = "image/jpeg") -> bytes: ...


def build_prompt(style: str) -> str:
    look = MAKEUP_STYLE_PROMPTS.get(style, MAKEUP_STYLE_PROMPTS["daily"])
    return MAKEUP_IMAGE_PROMPT.format(look=look)


class OpenAIImageProvider:
    url = "https://api.openai.com/v1/images/edits"

    def __init__(self, api_key: str, model: str = "gpt-image-1", timeout: float = 180) -> None:
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    async def apply(self, photo: bytes, style: str, media_type: str = "image/jpeg") -> bytes:
        ext = "png" if media_type == "image/png" else "jpg"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(
                    self.url,
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    data={
                        "model": self.model,
                        "prompt": build_prompt(style),
                        "size": "auto",
                        "quality": "medium",
                        "input_fidelity": "high",
                        "n": "1",
                    },
                    files={"image": (f"face.{ext}", photo, media_type)},
                )
        except httpx.HTTPError as e:
            raise MakeupImageError(f"network: {e}") from e
        if resp.status_code != 200:
            log.error("Image API %s: %s", resp.status_code, resp.text[:500])
            raise MakeupImageError(f"status {resp.status_code}")
        try:
            b64 = resp.json()["data"][0]["b64_json"]
        except (KeyError, IndexError, ValueError) as e:
            raise MakeupImageError("unexpected response") from e
        return base64.b64decode(b64)


def make_provider(name: str, openai_api_key: str, openai_model: str) -> MakeupImageProvider | None:
    if name == "openai" and openai_api_key:
        return OpenAIImageProvider(openai_api_key, openai_model)
    if name:
        log.warning("MAKEUP_IMAGE_PROVIDER=%r sozlanmagan yoki kalit yo'q; rasm yaratish o'chirilgan", name)
    return None
