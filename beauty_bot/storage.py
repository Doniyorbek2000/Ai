"""FSM holatini SQLite'da saqlash: bot qayta ishga tushsa ham foydalanuvchi qadami yo'qolmaydi."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from aiogram.fsm.state import State
from aiogram.fsm.storage.base import BaseStorage, StorageKey

from .db import Database


def storage_key(key: StorageKey) -> str:
    return ":".join(
        str(part) if part is not None else ""
        for part in (key.bot_id, key.chat_id, key.user_id, key.thread_id, key.business_connection_id, key.destiny)
    )


class SQLiteStorage(BaseStorage):
    def __init__(self, db: Database) -> None:
        self.db = db

    async def set_state(self, key: StorageKey, state: str | State | None = None) -> None:
        value = state.state if isinstance(state, State) else state
        await self.db.fsm_set_state(storage_key(key), value)

    async def get_state(self, key: StorageKey) -> str | None:
        state, _ = await self.db.fsm_get(storage_key(key))
        return state

    async def set_data(self, key: StorageKey, data: Mapping[str, Any]) -> None:
        await self.db.fsm_set_data(storage_key(key), dict(data))

    async def get_data(self, key: StorageKey) -> dict[str, Any]:
        _, data = await self.db.fsm_get(storage_key(key))
        return data

    async def close(self) -> None:  # baza ulanishi asosiy kodda yopiladi
        pass
