from datetime import date


async def test_language_and_consent(db):
    assert await db.get_lang(1) is None
    await db.ensure_user(1, "Malika")
    assert await db.get_lang(1) == "uz"
    await db.set_lang(1, "ru")
    assert await db.get_lang(1) == "ru"
    assert not await db.has_consent(1)
    await db.set_consent(1, True)
    assert await db.has_consent(1)


async def test_ai_daily_limit_and_refund(db):
    day = date(2026, 11, 9)
    assert await db.try_consume_ai(1, 2, day)
    assert await db.try_consume_ai(1, 2, day)
    assert not await db.try_consume_ai(1, 2, day)
    await db.refund_ai(1, day)
    assert await db.try_consume_ai(1, 2, day)
    assert await db.try_consume_ai(1, 2, date(2026, 11, 10))  # yangi kun


async def test_cart_add_decrement_and_clear(db):
    await db.cart_add(1, "a")
    await db.cart_add(1, "a")
    await db.cart_add(1, "b")
    assert await db.cart_items(1) == [("a", 2), ("b", 1)]
    await db.cart_add(1, "b", -1)
    assert await db.cart_items(1) == [("a", 2)]
    await db.cart_clear(1)
    assert await db.cart_items(1) == []


async def _order(db, subtotal=100_000, bonus_used=0):
    await db.ensure_user(1, "Malika")
    await db.cart_add(1, "a")
    return await db.create_order(1, [{"id": "a", "name": "A", "price": subtotal, "qty": 1}],
                                 subtotal, bonus_used, "+998901234567", "Toshkent", None, bonus_percent=3)


async def test_order_bonus_lifecycle(db):
    order = await _order(db)
    assert order.total == 100_000 and order.bonus_earned == 3_000
    assert await db.cart_items(1) == []
    assert await db.get_bonus(1) == 0  # bonus faqat yetkazilgandan keyin
    await db.set_order_status(order.id, "confirmed")
    await db.set_order_status(order.id, "delivered")
    assert await db.get_bonus(1) == 3_000
    try:
        await db.set_order_status(order.id, "cancelled")
        raise AssertionError("yakunlangan buyurtma o'zgarmasligi kerak")
    except ValueError:
        pass


async def test_bonus_is_spent_capped_and_refunded_on_cancel(db):
    first = await _order(db)
    await db.set_order_status(first.id, "delivered")  # 3 000 bonus
    second = await _order(db, subtotal=2_000, bonus_used=10_000)
    assert second.bonus_used == 2_000 and second.total == 0
    assert await db.get_bonus(1) == 1_000
    await db.set_order_status(second.id, "cancelled")
    assert await db.get_bonus(1) == 3_000


async def test_delete_user_removes_everything(db):
    await _order(db)
    await db.delete_user(1)
    assert await db.get_lang(1) is None
    assert await db.user_orders(1) == []
