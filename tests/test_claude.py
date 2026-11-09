import json

import anthropic
import httpx2
import pytest

from beauty_bot.ai.claude import FALLBACK_BETA, AIError, AIRefused, BeautyAI

from .fakes import claude_transport, skin_result


def make_ai(catalog, transport) -> BeautyAI:
    client = anthropic.AsyncAnthropic(
        api_key="test-key", http_client=httpx2.AsyncClient(transport=transport), max_retries=0
    )
    return BeautyAI(catalog, client=client)


async def test_skin_request_shape_and_parsing(catalog):
    captured = []
    expected = skin_result()
    ai = make_ai(catalog, claude_transport(expected.model_dump(), captured=captured))

    result = await ai.analyze_skin(b"jpegbytes", "ru", age="18_24", skin_feel="oily", concern="acne", extra=None)

    assert result == expected
    req = captured[0]
    assert FALLBACK_BETA in req.headers["anthropic-beta"]
    body = json.loads(req.content)
    assert body["model"] == "claude-opus-5-5"
    assert body["fallbacks"] == "default"
    assert body["output_config"]["effort"] == "high"
    assert body["output_config"]["format"]["type"] == "json_schema"
    assert "thinking" not in body and "temperature" not in body
    system = body["system"]
    assert system[0]["cache_control"] == {"type": "ephemeral"}
    assert '"sk-spf50"' in system[0]["text"] and '"pf-oud"' not in system[0]["text"]
    content = body["messages"][0]["content"]
    assert content[0]["type"] == "image" and content[0]["source"]["media_type"] == "image/jpeg"
    assert "Russian" in content[1]["text"] and "18_24" in content[1]["text"]


async def test_refusal_raises(catalog):
    ai = make_ai(catalog, claude_transport({}, stop_reason="refusal"))
    with pytest.raises(AIRefused):
        await ai.ideal_look(b"x", "uz")


async def test_api_error_is_wrapped(catalog):
    transport = httpx2.MockTransport(lambda r: httpx2.Response(500, json={"type": "error", "error": {"type": "api_error", "message": "boom"}}))
    ai = make_ai(catalog, transport)
    with pytest.raises(AIError):
        await ai.pick_perfume("uz", for_whom="self", occasion="daily", family="floral", season="all", budget="low")


async def test_academy_returns_text_and_sends_history(catalog):
    captured = []
    ai = make_ai(catalog, claude_transport("Halqa lampani ko'z darajasiga qo'ying.", captured=captured))
    history = [{"role": "user", "content": "salom"}, {"role": "assistant", "content": "salom!"}]
    reply = await ai.academy_reply(history, "uz", "Reels uchun yorug'lik?")
    assert reply.startswith("Halqa")
    body = json.loads(captured[0].content)
    assert body["messages"][:2] == history
    assert body["messages"][2]["role"] == "user"
    assert body["output_config"] == {"effort": "low"}
