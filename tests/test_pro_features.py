"""To'lov, referal, admin panel, eslatmalar, FSM saqlanishi, spamdan himoya."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from aiogram.methods import (
    AnswerPreCheckoutQuery,
    CopyMessage,
    SendInvoice,
    SendMessage,
)
from aiogram.types import (
    Contact,
    PhotoSize,
    PreCheckoutQuery,
    SuccessfulPayment,
    Update,
    User,
)

from beauty_bot.ai.errors import AIError
from beauty_bot.handlers.admin import _broadcast
from beauty_bot.handlers.menu import parse_start_payload
from beauty_bot.handlers.utils import run_ai
from beauty_bot.middlewares import ThrottleMiddleware
from beauty_bot.scheduler import run_once
from beauty_bot.texts import t

from .test_bot_flows import (  # noqa: F401
    ADMIN,
    ADMIN_CHAT,
    USER,
    Harness,
    _ids,
    detach_routers,
    joined,
)

FRIEND = User(id=2, is_bot=False, first_name="Nigora")


async def checkout(h, user=USER, product="sk-spf50"):
    await h.click(f"add:{product}", user=user)
    await h.click("checkout", user=user)
    await h.send(user, contact=Contact(phone_number="+998901234567", first_name="X", user_id=user.id))
    await h.text("Toshkent, Chilonzor 5", user=user)
    return await h.click("skip", user=user)


# --- Onlayn to'lov ---------------------------------------------------------------

async def pre_checkout(h, order_id, amount, user=USER):
    h.session.requests.clear()
    q = PreCheckoutQuery(id="pcq", from_user=user, currency="UZS", total_amount=amount, invoice_payload=f"order:{order_id}")
    await h.dp.feed_update(h.bot, Update(update_id=next(_ids), pre_checkout_query=q))
    return h.session.sent(AnswerPreCheckoutQuery)[0]


async def test_online_payment_flow(db, catalog):
    h = Harness(db, catalog, payment_provider_token="TEST:TOKEN")
    await h.click("lang:uz")
    s = await checkout(h)
    assert "To'lov usulini tanlang" in joined(s)
    assert "Yetkazib berish: 25 000 so'm" in joined(s)  # 139 000 < 300 000

    s = await h.click("order:online")
    invoice = s.sent(SendInvoice)[0]
    order = await db.get_order(1)
    assert order.status == "awaiting_payment" and order.total == 139000 + 25000
    assert invoice.provider_token == "TEST:TOKEN" and invoice.currency == "UZS"
    assert invoice.prices[0].amount == order.total * 100 and invoice.payload == "order:1"
    assert not s.sent(SendMessage) or all(m.chat_id != ADMIN_CHAT for m in s.sent(SendMessage))
    assert await db.cart_items(1) == [("sk-spf50", 1)]  # to'lovgacha savat saqlanadi
    assert await db.user_orders(1) == []  # to'lanmagan buyurtma mijozga ko'rinmaydi

    assert (await pre_checkout(h, 1, order.total * 100 - 100)).ok is False  # summa mos emas
    assert (await pre_checkout(h, 1, order.total * 100, user=FRIEND)).ok is False  # boshqa odam
    assert (await pre_checkout(h, 1, order.total * 100)).ok is True

    payment = SuccessfulPayment(currency="UZS", total_amount=order.total * 100, invoice_payload="order:1",
                                telegram_payment_charge_id="tg_charge_1", provider_payment_charge_id="click_1")
    s = await h.send(successful_payment=payment)
    order = await db.get_order(1)
    assert order.paid and order.status == "new" and order.payment_charge_id == "tg_charge_1"
    assert await db.cart_items(1) == []
    assert "To'lov qabul qilindi" in joined(s)
    admin = [m for m in s.sent(SendMessage) if m.chat_id == ADMIN_CHAT]
    assert admin and "TO'LANGAN" in admin[0].text
    assert (await pre_checkout(h, 1, order.total * 100)).ok is False  # ikkinchi marta to'lab bo'lmaydi


async def test_cash_when_online_disabled_and_free_delivery(db, catalog):
    h = Harness(db, catalog)  # token yo'q
    await h.click("lang:ru")
    await h.click("add:pf-oud")  # 890 000 -> bepul yetkazish
    await h.click("checkout")
    await h.send(contact=Contact(phone_number="+998901234567", first_name="X", user_id=1))
    await h.text("Ташкент, Юнусабад 3")
    s = await h.click("skip")
    assert "бесплатно" in joined(s) and "курьеру" in joined(s)
    await h.click("order:confirm")
    order = await db.get_order(1)
    assert order.delivery_fee == 0 and order.payment_method == "cash" and order.status == "new"


async def test_unpaid_order_expires_and_bonus_returns(db, catalog):
    await db.ensure_user(1, "M")
    await db.add_bonus(1, 5000)
    await db.cart_add(1, "sk-spf50")
    order = await db.create_order(1, [{"id": "sk-spf50", "name": "SPF", "price": 139000, "qty": 1}], 139000, 5000,
                                  "+998901234567", "Toshkent", None, 3, delivery_fee=25000, payment_method="online")
    assert order.status == "awaiting_payment" and await db.get_bonus(1) == 0
    assert await db.expire_unpaid(timedelta(hours=24)) == []
    expired = await db.expire_unpaid(timedelta(hours=24), now=datetime.now(timezone.utc) + timedelta(hours=25))
    assert [o.id for o in expired] == [order.id]
    assert (await db.get_order(order.id)).status == "cancelled"
    assert await db.get_bonus(1) == 5000
    assert await db.cart_items(1) == [("sk-spf50", 1)]


# --- Referal va manbalar -------------------------------------------------------------

def test_parse_start_payload():
    assert parse_start_payload("ref_123") == ("ref", 123)
    assert parse_start_payload("Aziza_Blog") == ("aziza_blog", None)
    assert parse_start_payload("<script>") == ("script", None)
    assert parse_start_payload(None) == (None, None)


async def test_referral_reward_once_and_source_tracking(db, catalog):
    h = Harness(db, catalog)
    await h.text("/start aziza_blog")
    await h.click("lang:uz")
    s = await h.text(t("btn_club", "uz"))
    assert "https://t.me/ai_beauty_bot?start=ref_1" in joined(s)

    await h.text("/start ref_1", user=FRIEND)
    await h.click("lang:uz", user=FRIEND)
    await h.text("/start ref_999", user=FRIEND)  # takroriy start taklif qiluvchini o'zgartirmaydi
    await checkout(h, user=FRIEND)
    await h.click("order:confirm", user=FRIEND)

    s = await h.click("adm:1:delivered", user=ADMIN)
    assert await db.get_bonus(1) == 20000
    assert any(m.chat_id == USER.id and "dugonangiz" in m.text for m in s.sent(SendMessage))
    assert await db.referral_count(1) == 1

    await checkout(h, user=FRIEND)
    await h.click("order:confirm", user=FRIEND)
    await h.click("adm:2:delivered", user=ADMIN)
    assert await db.get_bonus(1) == 20000  # faqat birinchi buyurtma uchun

    stats = await db.stats(7)
    assert ("aziza_blog", 1) in stats["sources"] and ("ref", 1) in stats["sources"]


async def test_self_referral_ignored(db):
    await db.ensure_user(5, "A", source="ref", referrer_id=5)
    assert await db.referral_count(5) == 0


# --- Admin panel ---------------------------------------------------------------

async def test_admin_price_stock_reload_and_permissions(db, catalog):
    h = Harness(db, catalog)
    await h.click("lang:uz")
    s = await h.text("/price sk-spf50 150000")  # oddiy foydalanuvchi
    assert not s.sent(SendMessage) and catalog.get("sk-spf50").price == 139000

    s = await h.text("/price sk-spf50 150000", user=ADMIN)
    assert "150 000" in joined(s) and catalog.get("sk-spf50").price == 150000
    s = await h.text("/stock sk-spf50 off", user=ADMIN)
    assert not catalog.get("sk-spf50").in_stock
    assert "sk-spf50" not in catalog.ai_context(("skincare",))  # AI ham tavsiya qilmaydi
    s = await h.click("add:sk-spf50")
    assert "Hozir mavjud emas" in joined(s)

    catalog.update("sk-spf50", price=1, in_stock=True)  # xotirani buzamiz
    s = await h.text("/reload", user=ADMIN)
    assert "Katalog yangilandi" in joined(s)
    p = catalog.get("sk-spf50")
    assert p.price == 150000 and not p.in_stock  # bazadagi o'zgarishlar qayta qo'llanadi

    s = await h.text("/products perfume", user=ADMIN)
    assert "pf-oud" in joined(s) and "sk-spf50" not in joined(s)
    s = await h.text("/price nope 100", user=ADMIN)
    assert "topilmadi" in joined(s)


async def test_admin_stats(db, catalog):
    h = Harness(db, catalog)
    await h.text("/start insta")
    await h.click("lang:uz")
    await h.text(t("btn_perfume", "uz"))
    for data in ("pf_for:self", "pf_occ:date", "pf_fam:fruity", "pf_sea:all", "pf_bud:mid"):
        await h.click(data)
    await h.click("add:pf-peach:ai")
    await checkout(h, product="pf-peach")
    await h.click("order:confirm")
    s = await h.text("/stats 30", user=ADMIN)
    out = joined(s)
    assert "Atir tanlash: 1 / 1" in out
    assert "Savatga (AI tavsiyasidan): 1 / 1" in out
    assert "AI dan foydalanib xarid qilganlar: 1 / 1 (100%)" in out
    assert "insta: 1" in out and "Peach Kiss" in out


async def test_broadcast_copies_and_marks_blocked(db, catalog):
    h = Harness(db, catalog)
    for uid in (1, 2, 3):
        await db.ensure_user(uid, "u")
    sent = await _broadcast(h.bot, db, ADMIN_CHAT, ADMIN_CHAT, 77, delay=0)
    assert sent == (3, 0)
    assert len(h.session.sent(CopyMessage)) == 3
    s = await h.text("/broadcast", user=ADMIN)
    assert "javob (reply)" in joined(s)


# --- Eslatmalar ---------------------------------------------------------------

async def test_skin_reminder_scheduled_and_sent(db, catalog):
    h = Harness(db, catalog, reminder_days=14)
    await h.click("lang:uz")
    await db.set_consent(1, True)
    await h.text(t("btn_skin", "uz"))
    for data in ("sk_age:18_24", "sk_feel:oily", "sk_conc:acne", "skip"):
        await h.click(data)
    await h.photo()
    assert await db.pop_due_reminders() == []  # hali vaqti kelmagan
    await db.schedule_reminder(1, "skin", datetime.now(timezone.utc) - timedelta(minutes=1))

    h.session.requests.clear()
    await run_once(h.bot, db, h.settings)
    msgs = h.session.sent(SendMessage)
    assert len(msgs) == 1 and "14 kun oldin" in msgs[0].text
    assert msgs[0].reply_markup.inline_keyboard[0][0].callback_data == "remind:skin"
    s = await h.click("remind:skin")
    assert "AI Skin Doctor" in joined(s)


# --- Ishonchlilik ---------------------------------------------------------------

async def test_fsm_state_survives_restart(db, catalog):
    h1 = Harness(db, catalog)
    await h1.click("lang:uz")
    await db.set_consent(1, True)
    await h1.text(t("btn_skin", "uz"))
    await h1.click("sk_age:25_34")
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
    h2 = Harness(db, catalog)  # "qayta ishga tushgan" bot, o'sha baza
    s = await h2.click("sk_feel:dry")
    assert t("ask_concern", "uz") in joined(s)
    await h2.click("sk_conc:dryness")
    await h2.click("skip")
    await h2.photo()
    call = h2.ai.calls[-1][1]
    assert call["age"] == "25_34" and call["skin_feel"] == "dry"


async def test_album_is_processed_once(db, catalog):
    h = Harness(db, catalog)
    await h.click("lang:uz")
    await db.set_consent(1, True)
    await h.text(t("btn_look", "uz"))
    photo = [PhotoSize(file_id="f", file_unique_id="u", width=10, height=10, file_size=10)]
    await h.send(photo=photo, media_group_id="album1")
    await h.send(photo=photo, media_group_id="album1")
    assert [c[0] for c in h.ai.calls] == ["look"]


def test_throttle_window():
    now = [0.0]
    mw = ThrottleMiddleware(limit=3, window=10, clock=lambda: now[0])
    assert [mw._allowed(1) for _ in range(4)] == [True, True, True, False]
    assert mw._allowed(2)
    now[0] = 11
    assert mw._allowed(1)


async def test_run_ai_blocks_parallel_requests_and_refunds_errors(db, catalog):
    h = Harness(db, catalog, limit=5)
    await db.ensure_user(1, "M")
    gate = asyncio.Event()
    answers = []

    class Msg:
        async def answer(self, text, **kw):
            answers.append(text)

    async def slow():
        await gate.wait()
        return "ok"

    first = asyncio.create_task(run_ai(Msg(), db, h.settings, "uz", 1, slow, event="look"))
    await asyncio.sleep(0)
    assert await run_ai(Msg(), db, h.settings, "uz", 1, slow) is None
    assert t("busy", "uz") in answers
    gate.set()
    assert await first == "ok"

    async def boom():
        raise AIError("x")

    assert await run_ai(Msg(), db, h.settings, "uz", 1, boom) is None
    assert await db.try_consume_ai(1, 2)  # xato limitdan ayirilmagan: 1 ta ishlatilgan, 1 ta qaytgan
    stats = await db.stats(1)
    assert stats["events"]["look"] == (1, 1)


@pytest.mark.parametrize("cmd", ["/delete_me"])
async def test_delete_me_clears_state(db, catalog, cmd):
    h = Harness(db, catalog)
    await h.click("lang:uz")
    await db.set_consent(1, True)
    await h.text(t("btn_skin", "uz"))
    await h.text(cmd)
    cur = await db.conn.execute("SELECT COUNT(*) FROM fsm")
    assert (await cur.fetchone())[0] == 0
