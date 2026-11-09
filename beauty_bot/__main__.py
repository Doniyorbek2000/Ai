"""Botni ishga tushirish: python -m beauty_bot"""

from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand

from .ai.claude import BeautyAI
from .ai.makeup import make_provider
from .catalog import Catalog
from .config import Settings
from .db import Database
from .handlers import academy, admin, look, makeup, menu, perfume, shop, skin
from .middlewares import LangMiddleware

log = logging.getLogger("beauty_bot")


def build_dispatcher(db: Database, catalog: Catalog, ai: BeautyAI, settings: Settings, image_provider) -> Dispatcher:
    dp = Dispatcher(
        db=db,
        catalog=catalog,
        ai=ai,
        settings=settings,
        image_provider=image_provider,
    )
    lang_mw = LangMiddleware(db)
    dp.message.outer_middleware(lang_mw)
    dp.callback_query.outer_middleware(lang_mw)
    # Tartib muhim: menyu tugmalari har qanday holatda birinchi tekshiriladi
    dp.include_routers(
        menu.router,
        admin.router,
        shop.router,
        skin.router,
        makeup.router,
        look.router,
        perfume.router,
        academy.router,
    )
    return dp


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    settings = Settings.from_env()
    catalog = Catalog.load(settings.catalog_path)
    db = Database(settings.db_path)
    await db.connect()
    ai = BeautyAI(catalog, model=settings.claude_model)
    image_provider = make_provider(
        settings.makeup_image_provider, settings.openai_api_key, settings.openai_image_model
    )
    log.info(
        "Katalog: %d mahsulot. Makiyaj rasmi: %s",
        len(catalog.products),
        "yoqilgan" if image_provider else "o'chirilgan (faqat matnli reja)",
    )

    bot = Bot(settings.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    await bot.set_my_commands([
        BotCommand(command="start", description="Boshlash / Начать"),
        BotCommand(command="menu", description="Menyu / Меню"),
        BotCommand(command="skin", description="Teri tahlili / Анализ кожи"),
        BotCommand(command="makeup", description="AI makiyaj / AI макияж"),
        BotCommand(command="shop", description="Do'kon / Магазин"),
        BotCommand(command="privacy", description="Maxfiylik / Конфиденциальность"),
        BotCommand(command="delete_me", description="Ma'lumotlarni o'chirish / Удалить данные"),
    ])
    dp = build_dispatcher(db, catalog, ai, settings, image_provider)
    try:
        await dp.start_polling(bot)
    finally:
        await db.close()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
