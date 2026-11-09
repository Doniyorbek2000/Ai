import pytest

from beauty_bot.texts import LANGS, OPTIONS, T, all_variants, fmt_price, opt, t, to_cyrillic


@pytest.mark.parametrize(
    "latin,cyrillic",
    [
        ("O'zbekcha", "Ўзбекча"),
        ("sun'iy", "сунъий"),
        ("ma'lumot", "маълумот"),
        ("yo'q", "йўқ"),
        ("yosh", "ёш"),
        ("Ertaga", "Эртага"),
        ("bog'lanadi", "боғланади"),
        ("choy", "чой"),
        ("shaxsiy", "шахсий"),
        ("hech", "ҳеч"),
    ],
)
def test_transliteration(latin, cyrillic):
    assert to_cyrillic(latin) == cyrillic


def test_transliteration_keeps_markup_commands_and_brands():
    src = "<b>AI Beauty</b> {name} /delete_me &amp; SPF"
    assert to_cyrillic(src) == src


def test_every_text_has_uz_and_ru():
    for key, entry in T.items():
        assert entry.get("uz") and entry.get("ru"), key
    for group, items in OPTIONS.items():
        for code, entry in items.items():
            assert entry.get("uz") and entry.get("ru"), (group, code)


def test_formatting_works_in_all_languages():
    kwargs = dict(name="Dilnoza", limit=10, reason="x", style="y", id=1, bonus=5, amount=3,
                  balance=0, percent=3, orders="-", cart="c", phone="p", address="a",
                  comment="c", status="s")
    for key in T:
        for lang in LANGS:
            assert t(key, lang, **kwargs)


def test_buttons_variants_are_distinct_per_language():
    assert len(all_variants("btn_skin")) == 3
    assert opt("makeup_style", "daily", "ru").endswith("Повседневный")


def test_fmt_price():
    assert fmt_price(1250000, "uz") == "1 250 000 so'm"
    assert fmt_price(89000, "ru") == "89 000 сум"
    assert fmt_price(89000, "uz_cyrl") == "89 000 сўм"
