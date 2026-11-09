"""Middleware'lar: foydalanuvchi tili, spamdan himoya va albomlarni (media group) bir marta ishlash."""

from __future__ import annotations

import time
from collections import deque
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject, User

from .db import Database
from .texts import DEFAULT_LANG


class LangMiddleware(BaseMiddleware):
    def __init__(self, db: Database) -> None:
        self.db = db

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user: User | None = data.get("event_from_user")
        lang = await self.db.get_lang(user.id) if user else None
        data["lang"] = lang or DEFAULT_LANG
        data["lang_set"] = lang is not None
        return await handler(event, data)


class ThrottleMiddleware(BaseMiddleware):
    """Bir foydalanuvchidan juda ko'p xabar kelsa (flood), ortiqchasini jimgina tashlaydi.

    Albom bo'lib kelgan rasmlardan faqat birinchisi ishlanadi, aks holda har biri alohida
    AI so'roviga aylanib ketardi.
    """

    def __init__(self, limit: int = 20, window: float = 10.0, clock: Callable[[], float] = time.monotonic) -> None:
        self.limit = limit
        self.window = window
        self.clock = clock
        self._hits: dict[int, deque[float]] = {}
        self._albums: dict[str, float] = {}

    def _allowed(self, user_id: int) -> bool:
        now = self.clock()
        hits = self._hits.setdefault(user_id, deque())
        while hits and now - hits[0] > self.window:
            hits.popleft()
        if len(hits) >= self.limit:
            return False
        hits.append(now)
        if len(self._hits) > 10_000:  # xotirani tozalash
            self._hits = {u: h for u, h in self._hits.items() if h and now - h[-1] <= self.window}
        return True

    def _first_in_album(self, message: Message) -> bool:
        group = message.media_group_id
        if not group:
            return True
        now = self.clock()
        if len(self._albums) > 5_000:
            self._albums = {g: t for g, t in self._albums.items() if now - t < 120}
        if group in self._albums:
            return False
        self._albums[group] = now
        return True

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user: User | None = data.get("event_from_user")
        if user is not None and not self._allowed(user.id):
            if isinstance(event, CallbackQuery):
                await event.answer()
            return None
        if isinstance(event, Message) and not self._first_in_album(event):
            return None
        return await handler(event, data)
