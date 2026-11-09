"""Har bir yangilanishga foydalanuvchi tilini qo'shadi."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, User

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
