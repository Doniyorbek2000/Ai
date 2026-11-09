"""SQLite ma'lumotlar bazasi: foydalanuvchilar, savat, buyurtmalar, bonuslar, AI limiti."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timezone

import aiosqlite

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_id     INTEGER PRIMARY KEY,
    lang        TEXT NOT NULL DEFAULT 'uz',
    name        TEXT,
    consent     INTEGER NOT NULL DEFAULT 0,
    bonus       INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS cart (
    user_id     INTEGER NOT NULL,
    product_id  TEXT NOT NULL,
    qty         INTEGER NOT NULL,
    PRIMARY KEY (user_id, product_id)
);
CREATE TABLE IF NOT EXISTS orders (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL,
    items       TEXT NOT NULL,
    subtotal    INTEGER NOT NULL,
    bonus_used  INTEGER NOT NULL DEFAULT 0,
    total       INTEGER NOT NULL,
    phone       TEXT NOT NULL,
    address     TEXT NOT NULL,
    comment     TEXT,
    status      TEXT NOT NULL DEFAULT 'new',
    bonus_earned INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS ai_usage (
    user_id     INTEGER NOT NULL,
    day         TEXT NOT NULL,
    count       INTEGER NOT NULL,
    PRIMARY KEY (user_id, day)
);
"""

ORDER_STATUSES = ("new", "confirmed", "delivered", "cancelled")


@dataclass
class Order:
    id: int
    user_id: int
    items: list[dict]
    subtotal: int
    bonus_used: int
    total: int
    phone: str
    address: str
    comment: str | None
    status: str
    bonus_earned: int
    created_at: str


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Database:
    def __init__(self, path: str) -> None:
        self.path = path
        self._conn: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        self._conn = await aiosqlite.connect(self.path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.executescript(SCHEMA)
        await self._conn.commit()

    async def close(self) -> None:
        if self._conn:
            await self._conn.close()
            self._conn = None

    @property
    def conn(self) -> aiosqlite.Connection:
        if self._conn is None:
            raise RuntimeError("Database.connect() chaqirilmagan")
        return self._conn

    # --- Foydalanuvchilar -------------------------------------------------
    async def ensure_user(self, user_id: int, name: str | None) -> None:
        await self.conn.execute(
            "INSERT INTO users(user_id, name, created_at) VALUES (?, ?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET name = excluded.name",
            (user_id, name, _now()),
        )
        await self.conn.commit()

    async def user_exists(self, user_id: int) -> bool:
        cur = await self.conn.execute("SELECT 1 FROM users WHERE user_id = ?", (user_id,))
        return await cur.fetchone() is not None

    async def get_lang(self, user_id: int) -> str | None:
        cur = await self.conn.execute("SELECT lang FROM users WHERE user_id = ?", (user_id,))
        row = await cur.fetchone()
        return row["lang"] if row else None

    async def set_lang(self, user_id: int, lang: str) -> None:
        await self.conn.execute(
            "INSERT INTO users(user_id, lang, created_at) VALUES (?, ?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET lang = excluded.lang",
            (user_id, lang, _now()),
        )
        await self.conn.commit()

    async def has_consent(self, user_id: int) -> bool:
        cur = await self.conn.execute("SELECT consent FROM users WHERE user_id = ?", (user_id,))
        row = await cur.fetchone()
        return bool(row and row["consent"])

    async def set_consent(self, user_id: int, value: bool) -> None:
        await self.conn.execute("UPDATE users SET consent = ? WHERE user_id = ?", (int(value), user_id))
        await self.conn.commit()

    async def get_bonus(self, user_id: int) -> int:
        cur = await self.conn.execute("SELECT bonus FROM users WHERE user_id = ?", (user_id,))
        row = await cur.fetchone()
        return int(row["bonus"]) if row else 0

    async def delete_user(self, user_id: int) -> None:
        for table in ("cart", "ai_usage", "orders", "users"):
            await self.conn.execute(f"DELETE FROM {table} WHERE user_id = ?", (user_id,))
        await self.conn.commit()

    # --- AI limiti ---------------------------------------------------------
    async def try_consume_ai(self, user_id: int, limit: int, today: date | None = None) -> bool:
        """Limit ichida bo'lsa hisoblagichni oshiradi va True qaytaradi."""
        day = (today or date.today()).isoformat()
        cur = await self.conn.execute(
            "SELECT count FROM ai_usage WHERE user_id = ? AND day = ?", (user_id, day)
        )
        row = await cur.fetchone()
        used = int(row["count"]) if row else 0
        if used >= limit:
            return False
        await self.conn.execute(
            "INSERT INTO ai_usage(user_id, day, count) VALUES (?, ?, 1) "
            "ON CONFLICT(user_id, day) DO UPDATE SET count = count + 1",
            (user_id, day),
        )
        await self.conn.commit()
        return True

    async def refund_ai(self, user_id: int, today: date | None = None) -> None:
        """AI xatosi bo'lsa, so'rov limitdan qaytariladi."""
        day = (today or date.today()).isoformat()
        await self.conn.execute(
            "UPDATE ai_usage SET count = MAX(count - 1, 0) WHERE user_id = ? AND day = ?",
            (user_id, day),
        )
        await self.conn.commit()

    # --- Savat -------------------------------------------------------------
    async def cart_add(self, user_id: int, product_id: str, qty: int = 1) -> None:
        await self.conn.execute(
            "INSERT INTO cart(user_id, product_id, qty) VALUES (?, ?, ?) "
            "ON CONFLICT(user_id, product_id) DO UPDATE SET qty = qty + excluded.qty",
            (user_id, product_id, qty),
        )
        await self.conn.execute("DELETE FROM cart WHERE user_id = ? AND qty <= 0", (user_id,))
        await self.conn.commit()

    async def cart_items(self, user_id: int) -> list[tuple[str, int]]:
        cur = await self.conn.execute(
            "SELECT product_id, qty FROM cart WHERE user_id = ? ORDER BY rowid", (user_id,)
        )
        return [(r["product_id"], int(r["qty"])) for r in await cur.fetchall()]

    async def cart_clear(self, user_id: int) -> None:
        await self.conn.execute("DELETE FROM cart WHERE user_id = ?", (user_id,))
        await self.conn.commit()

    # --- Buyurtmalar ---------------------------------------------------------
    async def create_order(
        self,
        user_id: int,
        items: list[dict],
        subtotal: int,
        bonus_used: int,
        phone: str,
        address: str,
        comment: str | None,
        bonus_percent: int,
    ) -> Order:
        bonus_used = max(0, min(bonus_used, subtotal, await self.get_bonus(user_id)))
        total = subtotal - bonus_used
        bonus_earned = total * bonus_percent // 100
        cur = await self.conn.execute(
            "INSERT INTO orders(user_id, items, subtotal, bonus_used, total, phone, address, "
            "comment, bonus_earned, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (user_id, json.dumps(items, ensure_ascii=False), subtotal, bonus_used, total,
             phone, address, comment, bonus_earned, _now()),
        )
        order_id = cur.lastrowid
        if bonus_used:
            await self.conn.execute(
                "UPDATE users SET bonus = bonus - ? WHERE user_id = ?", (bonus_used, user_id)
            )
        await self.conn.execute("DELETE FROM cart WHERE user_id = ?", (user_id,))
        await self.conn.commit()
        order = await self.get_order(int(order_id))
        assert order is not None
        return order

    async def get_order(self, order_id: int) -> Order | None:
        cur = await self.conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
        row = await cur.fetchone()
        return _order(row) if row else None

    async def user_orders(self, user_id: int, limit: int = 10) -> list[Order]:
        cur = await self.conn.execute(
            "SELECT * FROM orders WHERE user_id = ? ORDER BY id DESC LIMIT ?", (user_id, limit)
        )
        return [_order(r) for r in await cur.fetchall()]

    async def orders_by_status(self, status: str, limit: int = 20) -> list[Order]:
        cur = await self.conn.execute(
            "SELECT * FROM orders WHERE status = ? ORDER BY id DESC LIMIT ?", (status, limit)
        )
        return [_order(r) for r in await cur.fetchall()]

    async def set_order_status(self, order_id: int, status: str) -> Order | None:
        """Holatni o'zgartiradi. Yetkazilganda bonus beriladi, bekor qilinganda ishlatilgan bonus qaytadi."""
        if status not in ORDER_STATUSES:
            raise ValueError(f"Noma'lum holat: {status}")
        order = await self.get_order(order_id)
        if order is None or order.status == status:
            return order
        if order.status in ("delivered", "cancelled"):
            raise ValueError("Yakunlangan buyurtma holatini o'zgartirib bo'lmaydi")
        await self.conn.execute("UPDATE orders SET status = ? WHERE id = ?", (status, order_id))
        if status == "delivered" and order.bonus_earned:
            await self.conn.execute(
                "UPDATE users SET bonus = bonus + ? WHERE user_id = ?", (order.bonus_earned, order.user_id)
            )
        if status == "cancelled" and order.bonus_used:
            await self.conn.execute(
                "UPDATE users SET bonus = bonus + ? WHERE user_id = ?", (order.bonus_used, order.user_id)
            )
        await self.conn.commit()
        return await self.get_order(order_id)


def _order(row: aiosqlite.Row) -> Order:
    data = dict(row)
    data["items"] = json.loads(data["items"])
    return Order(**data)
