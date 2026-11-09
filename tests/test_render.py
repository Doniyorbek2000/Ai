from beauty_bot.ai.schemas import PerfumePick, PerfumePicks
from beauty_bot.render import (
    cart_lines,
    render_cart,
    render_perfume,
    render_skin,
    split_message,
)

from .fakes import skin_result


def test_render_skin_escapes_ai_text_and_adds_disclaimer(catalog):
    text = render_skin(skin_result(), catalog, "uz")
    assert "&lt;ko'rinadi&gt;" in text  # AI matni HTML sifatida talqin qilinmaydi
    assert "Yumshoq tozalovchi gel" in text  # mahsulot nomi katalogdan
    assert "tibbiy tashxis emas" in text
    assert "Dermatolog" not in text


def test_render_skin_urgent_warning_first(catalog):
    r = skin_result(urgent=True, see_dermatologist=True, urgent_reason="Xol shakli notekis")
    text = render_skin(r, catalog, "ru")
    assert text.index("без промедления") < text.index("Тип кожи")


def test_render_perfume_drops_non_perfume_ids(catalog):
    picks = PerfumePicks(intro="", picks=[PerfumePick(product_id="sk-spf50", why="x"),
                                          PerfumePick(product_id="pf-oud", why="y")])
    text, products = render_perfume(picks, catalog, "uz")
    assert [p.id for p in products] == ["pf-oud"]
    empty_text, none = render_perfume(PerfumePicks(intro="", picks=[]), catalog, "uz")
    assert none == [] and "topilmadi" in empty_text


def test_cart_total(catalog):
    lines = cart_lines([("sk-spf50", 2), ("missing", 1), ("mk-mascara", 1)], catalog)
    text, total = render_cart(lines, "uz")
    assert total == 139000 * 2 + 85000
    assert "363 000 so'm" in text


def test_split_message_respects_limit():
    text = "\n".join(f"qator {i} " + "x" * 50 for i in range(300))
    chunks = split_message(text, limit=1000)
    assert all(len(c) <= 1000 for c in chunks)
    assert "\n".join(chunks) == text
