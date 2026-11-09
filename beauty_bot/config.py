"""Bot sozlamalari: hammasi muhit o'zgaruvchilaridan (.env) o'qiladi."""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv


def _int_list(raw: str) -> list[int]:
    return [int(x) for x in raw.replace(" ", "").split(",") if x]


@dataclass(frozen=True)
class Settings:
    bot_token: str
    admin_chat_id: int | None
    admin_ids: list[int] = field(default_factory=list)
    claude_model: str = "claude-opus-5-5"
    makeup_image_provider: str = ""
    openai_api_key: str = ""
    openai_image_model: str = "gpt-image-1"
    daily_ai_limit: int = 15
    bonus_percent: int = 3
    db_path: str = "beauty_bot.db"
    catalog_path: str = "data/products.json"

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv()
        token = os.getenv("BOT_TOKEN", "").strip()
        if not token:
            raise RuntimeError("BOT_TOKEN o'rnatilmagan (.env faylini tekshiring)")
        admin_chat = os.getenv("ADMIN_CHAT_ID", "").strip()
        return cls(
            bot_token=token,
            admin_chat_id=int(admin_chat) if admin_chat else None,
            admin_ids=_int_list(os.getenv("ADMIN_IDS", "")),
            claude_model=os.getenv("CLAUDE_MODEL", "claude-opus-5-5").strip(),
            makeup_image_provider=os.getenv("MAKEUP_IMAGE_PROVIDER", "").strip().lower(),
            openai_api_key=os.getenv("OPENAI_API_KEY", "").strip(),
            openai_image_model=os.getenv("OPENAI_IMAGE_MODEL", "gpt-image-1").strip(),
            daily_ai_limit=int(os.getenv("DAILY_AI_LIMIT", "15")),
            bonus_percent=int(os.getenv("BONUS_PERCENT", "3")),
            db_path=os.getenv("DB_PATH", "beauty_bot.db"),
            catalog_path=os.getenv("CATALOG_PATH", "data/products.json"),
        )
