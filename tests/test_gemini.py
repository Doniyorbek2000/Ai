"""Gemini so'rovlari: haqiqiy SDK, soxta HTTP javoblar."""

import base64
import json

import httpx
import pytest
from google import genai
from google.genai import types

from beauty_bot.ai.errors import AIError, AIRefused
from beauty_bot.ai.gemini import BeautyAI
from beauty_bot.ai.makeup import GeminiImageProvider, MakeupImageError

from .fakes import skin_result


def gemini_transport(parts=None, finish="STOP", block=None, status=200, captured=None):
    def handler(request: httpx.Request) -> httpx.Response:
        if captured is not None:
            captured.append(request)
        if status != 200:
            return httpx.Response(status, json={"error": {"code": status, "message": "boom", "status": "INTERNAL"}})
        body = {"usageMetadata": {"promptTokenCount": 10, "candidatesTokenCount": 10}}
        if block:
            body["promptFeedback"] = {"blockReason": block}
        else:
            body["candidates"] = [{"content": {"role": "model", "parts": parts or []}, "finishReason": finish}]
        return httpx.Response(200, json=body)

    return httpx.MockTransport(handler)


def make_client(transport) -> genai.Client:
    return genai.Client(
        api_key="test-key",
        http_options=types.HttpOptions(
            httpx_async_client=httpx.AsyncClient(transport=transport),
            retry_options=types.HttpRetryOptions(attempts=1),
        ),
    )


def text_parts(obj) -> list[dict]:
    return [{"text": obj if isinstance(obj, str) else json.dumps(obj, ensure_ascii=False)}]


async def test_skin_request_shape_and_parsing(catalog):
    captured = []
    expected = skin_result()
    ai = BeautyAI(catalog, client=make_client(gemini_transport(text_parts(expected.model_dump()), captured=captured)))

    result = await ai.analyze_skin(b"jpegbytes", "ru", age="18_24", skin_feel="oily", concern="acne", extra=None)

    assert result == expected
    req = captured[0]
    assert req.url.path.endswith("/models/gemini-3.5-flash:generateContent")
    body = json.loads(req.content)
    cfg = body["generationConfig"]
    assert cfg["responseMimeType"] == "application/json"
    assert "responseSchema" in cfg or "responseJsonSchema" in cfg
    thinking = cfg["thinkingConfig"]
    assert (thinking.get("thinkingLevel") or thinking.get("thinking_level")) == "HIGH"
    system = body["systemInstruction"]["parts"][0]["text"]
    assert '"sk-spf50"' in system and '"pf-oud"' not in system
    assert "Never recommend or dose prescription medicines" in system
    parts = body["contents"][0]["parts"]
    inline = parts[0]["inlineData"]
    assert (inline.get("mimeType") or inline.get("mime_type")) == "image/jpeg"
    assert base64.b64decode(inline["data"]) == b"jpegbytes"
    assert "Russian" in parts[1]["text"] and "18_24" in parts[1]["text"]


@pytest.mark.parametrize("kwargs", [{"block": "SAFETY"}, {"finish": "SAFETY"}, {"finish": "PROHIBITED_CONTENT"}])
async def test_blocked_responses_raise_refused(catalog, kwargs):
    ai = BeautyAI(catalog, client=make_client(gemini_transport(**kwargs)))
    with pytest.raises(AIRefused):
        await ai.ideal_look(b"x", "uz")


async def test_server_error_and_bad_json_raise_ai_error(catalog):
    ai = BeautyAI(catalog, client=make_client(gemini_transport(status=500)))
    with pytest.raises(AIError):
        await ai.pick_perfume("uz", for_whom="self", occasion="daily", family="floral", season="all", budget="low")
    ai = BeautyAI(catalog, client=make_client(gemini_transport(text_parts("bu json emas"))))
    with pytest.raises(AIError):
        await ai.pick_perfume("uz", for_whom="self", occasion="daily", family="floral", season="all", budget="low")


async def test_academy_maps_roles_and_skips_thoughts(catalog):
    captured = []
    parts = [{"text": "o'ylayapman", "thought": True}, {"text": "Halqa lampani ko'z darajasiga qo'ying."}]
    ai = BeautyAI(catalog, client=make_client(gemini_transport(parts, captured=captured)))
    history = [{"role": "user", "content": "salom"}, {"role": "assistant", "content": "salom!"}]
    reply = await ai.academy_reply(history, "uz", "Reels uchun yorug'lik?")
    assert reply == "Halqa lampani ko'z darajasiga qo'ying."
    contents = json.loads(captured[0].content)["contents"]
    assert [c["role"] for c in contents] == ["user", "model", "user"]
    assert contents[1]["parts"][0]["text"] == "salom!"


async def test_makeup_image_provider(catalog):
    captured = []
    png = b"\x89PNG\r\n fake"
    parts = [{"inlineData": {"mimeType": "image/png", "data": base64.b64encode(png).decode()}}]
    provider = GeminiImageProvider(make_client(gemini_transport(parts, captured=captured)), "gemini-3.1-flash-image")
    assert await provider.apply(b"face", "wedding") == png
    body = json.loads(captured[0].content)
    assert captured[0].url.path.endswith("/models/gemini-3.1-flash-image:generateContent")
    assert body["generationConfig"]["responseModalities"] == ["IMAGE"]
    prompt = body["contents"][0]["parts"][1]["text"]
    assert "bridal" in prompt and "Keep the person's identity exactly the same" in prompt

    no_image = GeminiImageProvider(make_client(gemini_transport(text_parts("rasm yo'q"))), "m")
    with pytest.raises(MakeupImageError):
        await no_image.apply(b"face", "daily")
    blocked = GeminiImageProvider(make_client(gemini_transport(finish="IMAGE_SAFETY")), "m")
    with pytest.raises(MakeupImageError):
        await blocked.apply(b"face", "daily")
