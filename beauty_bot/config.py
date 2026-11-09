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
    gemini_model: str = "gemini-3.5-flash"
    gemini_image_model: str = "gemini-3.1-flash-image"
    makeup_images: bool = True
    daily_ai_limit: int = 15
    bonus_percent: int = 3
    # Onlayn to'lov: BotFather -> Payments orqali olingan Click yoki Payme provider tokeni
    payment_provider_token: str = ""
    delivery_fee: int = 25_000
    free_delivery_from: int = 300_000
    referral_bonus: int = 20_000
    reminder_days: int = 14
    payment_ttl_hours: int = 24
    db_path: str = "beauty_bot.db"
    catalog_path: str = "data/products.json"

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv()
        token = os.getenv("BOT_TOKEN", "").strip()
        if not token:
            raise RuntimeError("BOT_TOKEN o'rnatilmagan (.env faylini tekshiring)")
        if not (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")):
            raise RuntimeError("GEMINI_API_KEY o'rnatilmagan (.env faylini tekshiring)")
        admin_chat = os.getenv("ADMIN_CHAT_ID", "").strip()
        return cls(
            bot_token=token,
            admin_chat_id=int(admin_chat) if admin_chat else None,
            admin_ids=_int_list(os.getenv("ADMIN_IDS", "")),
            gemini_model=os.getenv("GEMINI_MODEL", cls.gemini_model).strip(),
            gemini_image_model=os.getenv("GEMINI_IMAGE_MODEL", cls.gemini_image_model).strip(),
            makeup_images=os.getenv("MAKEUP_IMAGES", "1").strip().lower() not in ("0", "false", "no", ""),
            daily_ai_limit=int(os.getenv("DAILY_AI_LIMIT", "15")),
            bonus_percent=int(os.getenv("BONUS_PERCENT", "3")),
            payment_provider_token=os.getenv("PAYMENT_PROVIDER_TOKEN", "").strip(),
            delivery_fee=int(os.getenv("DELIVERY_FEE", "25000")),
            free_delivery_from=int(os.getenv("FREE_DELIVERY_FROM", "300000")),
            referral_bonus=int(os.getenv("REFERRAL_BONUS", "20000")),
            reminder_days=int(os.getenv("REMINDER_DAYS", "14")),
            payment_ttl_hours=int(os.getenv("PAYMENT_TTL_HOURS", "24")),
            db_path=os.getenv("DB_PATH", "beauty_bot.db"),
            catalog_path=os.getenv("CATALOG_PATH", "data/products.json"),
        )
