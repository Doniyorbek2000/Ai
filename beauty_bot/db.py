"""SQLite ma'lumotlar bazasi.

Jadvallar: foydalanuvchilar, savat, buyurtmalar, bonuslar, AI limiti, hodisalar (statistika),
eslatmalar, katalog o'zgartirishlari (narx/mavjudlik) va FSM holati.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

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
CREATE TABLE IF NOT EXISTS events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL,
    kind        TEXT NOT NULL,
    data        TEXT,
    created_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events_kind_time ON events(kind, created_at);
CREATE TABLE IF NOT EXISTS reminders (
    user_id     INTEGER NOT NULL,
    kind        TEXT NOT NULL,
    due_at      TEXT NOT NULL,
    PRIMARY KEY (user_id, kind)
);
CREATE TABLE IF NOT EXISTS product_overrides (
    product_id  TEXT PRIMARY KEY,
    price       INTEGER,
    in_stock    INTEGER
);
CREATE TABLE IF NOT EXISTS fsm (
    key         TEXT PRIMARY KEY,
    state       TEXT,
    data        TEXT NOT NULL DEFAULT '{}'
);
"""

# Eski bazalarga qo'shiladigan ustunlar (jadval, ustun, ta'rif)
MIGRATIONS = [
    ("users", "source", "TEXT"),
    ("users", "referrer_id", "INTEGER"),
    ("users", "ref_rewarded", "INTEGER NOT NULL DEFAULT 0"),
    ("users", "blocked", "INTEGER NOT NULL DEFAULT 0"),
    ("orders", "delivery_fee", "INTEGER NOT NULL DEFAULT 0"),
    ("orders", "payment_method", "TEXT NOT NULL DEFAULT 'cash'"),
    ("orders", "paid", "INTEGER NOT NULL DEFAULT 0"),
    ("orders", "payment_charge_id", "TEXT"),
]

# awaiting_payment: onlayn to'lov kutilmoqda (adminga hali ko'rsatilmaydi)
ORDER_STATUSES = ("awaiting_payment", "new", "confirmed", "delivered", "cancelled")
FINAL_STATUSES = ("delivered", "cancelled")


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
    delivery_fee: int = 0
    payment_method: str = "cash"
    paid: int = 0
    payment_charge_id: str | None = None


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat(timespec="seconds")


def calc_delivery(subtotal: int, fee: int, free_from: int) -> int:
    return 0 if free_from and subtotal >= free_from else fee


class Database:
    def __init__(self, path: str) -> None:
        self.path = path
        self._conn: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        self._conn = await aiosqlite.connect(self.path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.execute("PRAGMA journal_mode=WAL")
        await self._conn.executescript(SCHEMA)
        for table, column, ddl in MIGRATIONS:
            cur = await self._conn.execute(f"PRAGMA table_info({table})")
            if column not in {r["name"] for r in await cur.fetchall()}:
                await self._conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")
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
    async def ensure_user(self, user_id: int, name: str | None, source: str | None = None,
                          referrer_id: int | None = None) -> bool:
        """Foydalanuvchini yaratadi yoki ismini yangilaydi. Yangi bo'lsa True.

        Manba (bloger havolasi) va taklif qilgan odam faqat birinchi marta yoziladi.
        """
        is_new = not await self.user_exists(user_id)
        if is_new:
            if referrer_id == user_id or (referrer_id and not await self.user_exists(referrer_id)):
                referrer_id = None
            await self.conn.execute(
                "INSERT INTO users(user_id, name, source, referrer_id, created_at) VALUES (?, ?, ?, ?, ?)",
                (user_id, name, source, referrer_id, _iso(_now())),
            )
        else:
            await self.conn.execute(
                "UPDATE users SET name = ?, blocked = 0 WHERE user_id = ?", (name, user_id)
            )
        await self.conn.commit()
        return is_new

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
            (user_id, lang, _iso(_now())),
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

    async def add_bonus(self, user_id: int, amount: int) -> None:
        await self.conn.execute("UPDATE users SET bonus = bonus + ? WHERE user_id = ?", (amount, user_id))
        await self.conn.commit()

    async def mark_blocked(self, user_id: int) -> None:
        await self.conn.execute("UPDATE users SET blocked = 1 WHERE user_id = ?", (user_id,))
        await self.conn.commit()

    async def active_user_ids(self) -> list[int]:
        cur = await self.conn.execute("SELECT user_id FROM users WHERE blocked = 0 ORDER BY user_id")
        return [int(r["user_id"]) for r in await cur.fetchall()]

    async def referral_count(self, user_id: int) -> int:
        cur = await self.conn.execute("SELECT COUNT(*) AS n FROM users WHERE referrer_id = ?", (user_id,))
        return int((await cur.fetchone())["n"])

    async def delete_user(self, user_id: int) -> None:
        for table in ("cart", "ai_usage", "orders", "events", "reminders", "users"):
            await self.conn.execute(f"DELETE FROM {table} WHERE user_id = ?", (user_id,))
        await self.conn.execute("DELETE FROM fsm WHERE key LIKE ?", (f"%:{user_id}:{user_id}:%",))
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

    # --- Hodisalar (statistika) ------------------------------------------------
    async def log_event(self, user_id: int, kind: str, data: str | None = None) -> None:
        await self.conn.execute(
            "INSERT INTO events(user_id, kind, data, created_at) VALUES (?, ?, ?, ?)",
            (user_id, kind, data, _iso(_now())),
        )
        await self.conn.commit()

    async def stats(self, days: int) -> dict:
        since = _iso(_now() - timedelta(days=days))

        async def one(sql: str, *args) -> int:
            cur = await self.conn.execute(sql, args)
            row = await cur.fetchone()
            return int(row[0] or 0)

        cur = await self.conn.execute(
            "SELECT kind, COUNT(*) AS n, COUNT(DISTINCT user_id) AS u FROM events "
            "WHERE created_at >= ? GROUP BY kind ORDER BY n DESC", (since,)
        )
        events = {r["kind"]: (int(r["n"]), int(r["u"])) for r in await cur.fetchall()}
        cur = await self.conn.execute(
            "SELECT COALESCE(source, '—') AS s, COUNT(*) AS n FROM users WHERE created_at >= ? "
            "GROUP BY s ORDER BY n DESC LIMIT 10", (since,)
        )
        sources = [(r["s"], int(r["n"])) for r in await cur.fetchall()]
        cur = await self.conn.execute(
            "SELECT pid, COUNT(*) AS n FROM (SELECT data AS pid FROM events WHERE kind = 'add_ai' "
            "AND created_at >= ?) GROUP BY pid ORDER BY n DESC LIMIT 5", (since,)
        )
        top_ai_products = [(r["pid"], int(r["n"])) for r in await cur.fetchall()]
        ai_users = await one(
            "SELECT COUNT(DISTINCT user_id) FROM events WHERE kind IN ('skin','look','makeup','perfume') "
            "AND created_at >= ?", since)
        buyers_after_ai = await one(
            "SELECT COUNT(DISTINCT o.user_id) FROM orders o WHERE o.created_at >= ? AND o.status NOT IN "
            "('awaiting_payment','cancelled') AND EXISTS (SELECT 1 FROM events e WHERE e.user_id = o.user_id "
            "AND e.kind IN ('skin','look','makeup','perfume'))", since)
        return {
            "users_total": await one("SELECT COUNT(*) FROM users"),
            "users_new": await one("SELECT COUNT(*) FROM users WHERE created_at >= ?", since),
            "users_blocked": await one("SELECT COUNT(*) FROM users WHERE blocked = 1"),
            "orders": await one(
                "SELECT COUNT(*) FROM orders WHERE created_at >= ? AND status NOT IN ('awaiting_payment','cancelled')", since),
            "orders_delivered": await one(
                "SELECT COUNT(*) FROM orders WHERE created_at >= ? AND status = 'delivered'", since),
            "revenue_delivered": await one(
                "SELECT SUM(total) FROM orders WHERE created_at >= ? AND status = 'delivered'", since),
            "revenue_open": await one(
                "SELECT SUM(total) FROM orders WHERE created_at >= ? AND status IN ('new','confirmed')", since),
            "paid_online": await one("SELECT COUNT(*) FROM orders WHERE created_at >= ? AND paid = 1", since),
            "events": events,
            "sources": sources,
            "top_ai_products": top_ai_products,
            "ai_users": ai_users,
            "buyers_after_ai": buyers_after_ai,
        }

    # --- Eslatmalar ------------------------------------------------------------
    async def schedule_reminder(self, user_id: int, kind: str, due_at: datetime) -> None:
        await self.conn.execute(
            "INSERT INTO reminders(user_id, kind, due_at) VALUES (?, ?, ?) "
            "ON CONFLICT(user_id, kind) DO UPDATE SET due_at = excluded.due_at",
            (user_id, kind, _iso(due_at)),
        )
        await self.conn.commit()

    async def pop_due_reminders(self, now: datetime | None = None, limit: int = 50) -> list[tuple[int, str]]:
        now_s = _iso(now or _now())
        cur = await self.conn.execute(
            "SELECT user_id, kind FROM reminders WHERE due_at <= ? ORDER BY due_at LIMIT ?", (now_s, limit)
        )
        rows = [(int(r["user_id"]), r["kind"]) for r in await cur.fetchall()]
        for user_id, kind in rows:
            await self.conn.execute("DELETE FROM reminders WHERE user_id = ? AND kind = ?", (user_id, kind))
        await self.conn.commit()
        return rows

    # --- Katalog o'zgartirishlari ----------------------------------------------
    async def set_override(self, product_id: str, price: int | None = None, in_stock: bool | None = None) -> None:
        await self.conn.execute(
            "INSERT INTO product_overrides(product_id, price, in_stock) VALUES (?, ?, ?) "
            "ON CONFLICT(product_id) DO UPDATE SET "
            "price = COALESCE(excluded.price, price), in_stock = COALESCE(excluded.in_stock, in_stock)",
            (product_id, price, None if in_stock is None else int(in_stock)),
        )
        await self.conn.commit()

    async def overrides(self) -> dict[str, dict]:
        cur = await self.conn.execute("SELECT product_id, price, in_stock FROM product_overrides")
        out: dict[str, dict] = {}
        for r in await cur.fetchall():
            item: dict = {}
            if r["price"] is not None:
                item["price"] = int(r["price"])
            if r["in_stock"] is not None:
                item["in_stock"] = bool(r["in_stock"])
            out[r["product_id"]] = item
        return out

    # --- Savat -------------------------------------------------------------
    async def cart_add(self, user_id: int, product_id: str, qty: int = 1) -> None:
        await self.conn.execute(
            "INSERT INTO cart(user_id, product_id, qty) VALUES (?, ?, ?) "
            "ON CONFLICT(user_id, product_id) DO UPDATE SET qty = MIN(qty + excluded.qty, 99)",
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
        delivery_fee: int = 0,
        payment_method: str = "cash",
    ) -> Order:
        """Buyurtma yaratadi. Naqd to'lovda savat darhol tozalanadi, onlaynda esa to'lovdan keyin."""
        bonus_used = max(0, min(bonus_used, subtotal, await self.get_bonus(user_id)))
        goods = subtotal - bonus_used
        total = goods + delivery_fee
        bonus_earned = goods * bonus_percent // 100
        online = payment_method == "online" and total > 0
        status = "awaiting_payment" if online else "new"
        cur = await self.conn.execute(
            "INSERT INTO orders(user_id, items, subtotal, bonus_used, total, phone, address, comment, "
            "status, bonus_earned, created_at, delivery_fee, payment_method) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (user_id, json.dumps(items, ensure_ascii=False), subtotal, bonus_used, total, phone, address,
             comment, status, bonus_earned, _iso(_now()), delivery_fee, "online" if online else "cash"),
        )
        order_id = int(cur.lastrowid)
        if bonus_used:
            await self.conn.execute(
                "UPDATE users SET bonus = bonus - ? WHERE user_id = ?", (bonus_used, user_id)
            )
        if not online:
            await self.conn.execute("DELETE FROM cart WHERE user_id = ?", (user_id,))
        await self.conn.commit()
        order = await self.get_order(order_id)
        assert order is not None
        return order

    async def mark_paid(self, order_id: int, charge_id: str) -> Order | None:
        """Onlayn to'lov muvaffaqiyatli: buyurtma adminga 'new' bo'lib o'tadi, savat tozalanadi."""
        order = await self.get_order(order_id)
        if order is None or order.paid:
            return order
        await self.conn.execute(
            "UPDATE orders SET paid = 1, payment_charge_id = ?, "
            "status = CASE WHEN status = 'awaiting_payment' THEN 'new' ELSE status END WHERE id = ?",
            (charge_id, order_id),
        )
        await self.conn.execute("DELETE FROM cart WHERE user_id = ?", (order.user_id,))
        await self.conn.commit()
        return await self.get_order(order_id)

    async def expire_unpaid(self, older_than: timedelta, now: datetime | None = None) -> list[Order]:
        """Uzoq vaqt to'lanmagan onlayn buyurtmalarni bekor qiladi (ishlatilgan bonus qaytadi)."""
        cutoff = _iso((now or _now()) - older_than)
        cur = await self.conn.execute(
            "SELECT id FROM orders WHERE status = 'awaiting_payment' AND created_at <= ?", (cutoff,)
        )
        expired = []
        for r in await cur.fetchall():
            order = await self.set_order_status(int(r["id"]), "cancelled")
            if order:
                expired.append(order)
        return expired

    async def get_order(self, order_id: int) -> Order | None:
        cur = await self.conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
        row = await cur.fetchone()
        return _order(row) if row else None

    async def user_orders(self, user_id: int, limit: int = 10) -> list[Order]:
        cur = await self.conn.execute(
            "SELECT * FROM orders WHERE user_id = ? AND status != 'awaiting_payment' ORDER BY id DESC LIMIT ?",
            (user_id, limit),
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
        if order.status in FINAL_STATUSES:
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

    async def reward_referrer(self, user_id: int, amount: int) -> int | None:
        """Taklif qilingan dugona birinchi buyurtmasini olganda taklif qilganga bonus (bir marta)."""
        if amount <= 0:
            return None
        cur = await self.conn.execute(
            "SELECT referrer_id, ref_rewarded FROM users WHERE user_id = ?", (user_id,)
        )
        row = await cur.fetchone()
        if not row or not row["referrer_id"] or row["ref_rewarded"]:
            return None
        referrer = int(row["referrer_id"])
        if not await self.user_exists(referrer):
            return None
        await self.conn.execute("UPDATE users SET ref_rewarded = 1 WHERE user_id = ?", (user_id,))
        await self.conn.execute("UPDATE users SET bonus = bonus + ? WHERE user_id = ?", (amount, referrer))
        await self.conn.commit()
        return referrer

    # --- FSM holati ------------------------------------------------------------
    async def fsm_get(self, key: str) -> tuple[str | None, dict]:
        cur = await self.conn.execute("SELECT state, data FROM fsm WHERE key = ?", (key,))
        row = await cur.fetchone()
        if not row:
            return None, {}
        return row["state"], json.loads(row["data"] or "{}")

    async def fsm_set_state(self, key: str, state: str | None) -> None:
        await self.conn.execute(
            "INSERT INTO fsm(key, state) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET state = excluded.state",
            (key, state),
        )
        await self.conn.execute("DELETE FROM fsm WHERE key = ? AND state IS NULL AND data = '{}'", (key,))
        await self.conn.commit()

    async def fsm_set_data(self, key: str, data: dict) -> None:
        payload = json.dumps(data, ensure_ascii=False)
        await self.conn.execute(
            "INSERT INTO fsm(key, data) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET data = excluded.data",
            (key, payload),
        )
        await self.conn.execute("DELETE FROM fsm WHERE key = ? AND state IS NULL AND data = '{}'", (key,))
        await self.conn.commit()


def _order(row: aiosqlite.Row) -> Order:
    data = dict(row)
    data["items"] = json.loads(data["items"])
    return Order(**data)
