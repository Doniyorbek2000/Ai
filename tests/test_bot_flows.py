"""Botni boshidan oxirigacha sinash: haqiqiy dispatcher, soxta Telegram va soxta AI."""

from __future__ import annotations

import itertools
from datetime import datetime

import pytest
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.methods import SendMessage, SendPhoto
from aiogram.types import CallbackQuery, Chat, Contact, Message, PhotoSize, Update, User

from beauty_bot.__main__ import build_dispatcher
from beauty_bot.config import Settings
from beauty_bot.middlewares import ThrottleMiddleware
from beauty_bot.texts import t

from .fakes import FakeAI, FakeImageProvider, FakeSession

USER = User(id=1, is_bot=False, first_name="Malika")
ADMIN = User(id=99, is_bot=False, first_name="Admin")
ADMIN_CHAT = -100500
_ids = itertools.count(1)


class Harness:
    def __init__(self, db, catalog, limit=15, image_provider=None, **settings_kw):
        self.session = FakeSession()
        self.bot = Bot("42:TEST", session=self.session, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
        self.ai = FakeAI()
        self.db = db
        self.catalog = catalog
        self.settings = Settings(bot_token="42:TEST", admin_chat_id=ADMIN_CHAT, admin_ids=[ADMIN.id],
                                 daily_ai_limit=limit, **settings_kw)
        self.dp = build_dispatcher(db, catalog, self.ai, self.settings, image_provider,
                                   throttle=ThrottleMiddleware(limit=10_000))

    def _msg(self, user=USER, **kw) -> Message:
        return Message(message_id=next(_ids), date=datetime.now(), chat=Chat(id=user.id, type="private"),
                       from_user=user, **kw)

    async def send(self, user=USER, **kw):
        self.session.requests.clear()
        await self.dp.feed_update(self.bot, Update(update_id=next(_ids), message=self._msg(user, **kw)))
        return self.session

    async def text(self, text, user=USER):
        return await self.send(user, text=text)

    async def photo(self, user=USER):
        return await self.send(user, photo=[PhotoSize(file_id="f1", file_unique_id="u1", width=800, height=800, file_size=1000)])

    async def click(self, data, user=USER):
        self.session.requests.clear()
        cq = CallbackQuery(id=str(next(_ids)), from_user=user, chat_instance="ci", data=data,
                           message=self._msg(user, text="bot message"))
        await self.dp.feed_update(self.bot, Update(update_id=next(_ids), callback_query=cq))
        return self.session


@pytest.fixture(autouse=True)
def detach_routers():
    """Routerlar modul darajasida yaratiladi; har bir test yangi dispatcherga ulaydi."""
    yield
    from beauty_bot.handlers import (
        academy,
        admin,
        look,
        makeup,
        menu,
        perfume,
        shop,
        skin,
    )

    for module in (academy, admin, look, makeup, menu, perfume, shop, skin):
        module.router._parent_router = None


@pytest.fixture
def h(db, catalog):
    return Harness(db, catalog)


def joined(session) -> str:
    return "\n".join(session.texts())


async def test_start_language_and_menu(h):
    s = await h.text("/start")
    assert t("choose_lang", "uz") in joined(s)
    s = await h.click("lang:ru")
    assert "Добро пожаловать" in joined(s)
    assert await h.db.get_lang(1) == "ru"
    s = await h.text("/start")
    assert "Добро пожаловать" in joined(s)  # til qayta so'ralmaydi


async def test_skin_flow_with_consent(h):
    await h.text("/start")
    await h.click("lang:uz")
    s = await h.text(t("btn_skin", "uz"))
    assert "Rozimisiz" in joined(s)
    s = await h.click("consent:yes:skin")
    assert "AI Skin Doctor" in joined(s)
    await h.click("sk_age:18_24")
    await h.click("sk_feel:oily")
    await h.click("sk_conc:acne")
    s = await h.text("Homilador emasman, 2 oydan beri toshma bor")
    assert "rasmini yuboring" in joined(s)
    s = await h.photo()

    name, call = h.ai.calls[-1]
    assert name == "skin"
    assert call["age"] == "18_24" and call["skin_feel"] == "oily" and call["concern"] == "acne"
    assert call["extra"].startswith("Homilador") and call["lang"] == "uz"
    out = joined(s)
    assert "Teri tahlili natijasi" in out and "tibbiy tashxis emas" in out
    buttons = [b.callback_data for m in s.sent(SendMessage) if m.reply_markup and hasattr(m.reply_markup, "inline_keyboard")
               for row in m.reply_markup.inline_keyboard for b in row]
    assert "add:sk-cleanser-gel:ai" in buttons and not any("made-up-id" in b for b in buttons)

    # Ikkinchi marta rozilik so'ralmaydi
    s = await h.text(t("btn_skin", "uz"))
    assert "Rozimisiz" not in joined(s) and "AI Skin Doctor" in joined(s)


async def test_text_instead_of_photo_and_menu_escape(h):
    await h.click("lang:uz")
    await h.db.set_consent(1, True)
    await h.text(t("btn_look", "uz"))
    s = await h.text("salom")
    assert "rasm yuboring" in joined(s)
    s = await h.text(t("btn_shop", "uz"))  # menyu tugmasi har qanday holatda ishlaydi
    assert "Do'kon" in joined(s)
    assert not h.ai.calls


async def test_shop_checkout_admin_and_bonus(h):
    await h.text("/start")
    await h.click("lang:uz")
    await h.click("add:sk-spf50")
    await h.click("add:sk-spf50")
    await h.click("inc:mk-mascara")
    s = await h.click("cart")
    assert "363 000 so'm" in joined(s)

    await h.click("checkout")
    s = await h.text("12345")
    assert "noto'g'ri" in joined(s)
    await h.send(contact=Contact(phone_number="998901234567", first_name="Malika", user_id=1))
    await h.text("Toshkent, Chilonzor 5, 12-uy")
    s = await h.click("skip")  # izoh yo'q, bonus yo'q -> tasdiqlash
    assert "Tasdiqlaysizmi" in joined(s) and "+998901234567" in joined(s)
    s = await h.click("order:confirm")
    assert "№1 qabul qilindi" in joined(s)
    admin_msgs = [m for m in s.sent(SendMessage) if m.chat_id == ADMIN_CHAT]
    assert admin_msgs and "Jami: 363 000 so'm" in admin_msgs[0].text
    assert await h.db.cart_items(1) == []

    # Begona odam holatni o'zgartira olmaydi
    await h.click("adm:1:delivered")
    assert (await h.db.get_order(1)).status == "new"
    s = await h.click("adm:1:delivered", user=ADMIN)
    assert (await h.db.get_order(1)).status == "delivered"
    assert await h.db.get_bonus(1) == 363000 * 3 // 100
    assert any(m.chat_id == USER.id and "yetkazilgan" in m.text for m in s.sent(SendMessage))

    # Keyingi buyurtmada bonus ishlatiladi
    await h.click("add:mk-mascara")
    await h.click("checkout")
    await h.text("+998 90 123 45 67")
    await h.text("Toshkent, Yunusobod 3")
    await h.text("Kechqurun olib keling")
    s = await h.click("bonus:yes")
    assert "Bonus ishlatildi" in joined(s)
    await h.click("order:confirm")
    order = await h.db.get_order(2)
    # 300 000 dan kam: yetkazib berish 25 000 so'm; bonus faqat mahsulotga ishlatiladi
    assert order.bonus_used == 10890 and order.delivery_fee == 25000
    assert order.total == 85000 - 10890 + 25000
    assert order.comment == "Kechqurun olib keling"


async def test_perfume_and_daily_limit(db, catalog):
    h = Harness(db, catalog, limit=1)
    await h.click("lang:uz")

    async def run_quiz():
        await h.text(t("btn_perfume", "uz"))
        for data in ("pf_for:self", "pf_occ:date", "pf_fam:fruity", "pf_sea:all"):
            await h.click(data)
        return await h.click("pf_bud:mid")

    s = await run_quiz()
    out = joined(s)
    assert "Peach Kiss" in out and "SPF" not in out  # atir bo'lmagan ID tashlab yuboriladi
    s = await run_quiz()
    assert "limiti tugadi" in joined(s)
    assert len(h.ai.calls) == 1


async def test_academy_keeps_short_history(h):
    await h.click("lang:uz")
    await h.text(t("btn_academy", "uz"))
    await h.text("Reels uchun qanday yorug'lik kerak?")
    s = await h.text("Halqa lampa qayerda turadi?")
    assert "Javob &lt;2&gt;" in joined(s)
    assert h.ai.calls[-1][1]["history"][0] == {"role": "user", "content": "Reels uchun qanday yorug'lik kerak?"}
    s = await h.photo()  # rozilik yo'q -> so'raladi
    assert "Rozimisiz" in joined(s)
    await h.text(t("btn_cart", "uz"))
    calls = len(h.ai.calls)
    await h.text("bu endi academy emas")
    assert len(h.ai.calls) == calls


async def test_makeup_with_image_provider(db, catalog):
    provider = FakeImageProvider()
    h = Harness(db, catalog, image_provider=provider)
    await h.click("lang:ru")
    await h.db.set_consent(1, True)
    await h.text(t("btn_makeup", "ru"))
    await h.click("mk:wedding")
    s = await h.photo()
    assert provider.calls == 1
    photos = s.sent(SendPhoto)
    assert photos and "Свадебный" in photos[0].caption
    assert h.ai.calls[-1] == ("makeup", {"lang": "ru", "style": "wedding"})
    assert "План макияжа" in joined(s)


async def test_delete_me(h):
    await h.click("lang:uz")
    await h.click("add:sk-spf50")
    await h.text("/delete_me")
    assert await h.db.get_lang(1) is None and await h.db.cart_items(1) == []
