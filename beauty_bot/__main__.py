"""Botni ishga tushirish: python -m beauty_bot"""

from __future__ import annotations

import asyncio
import contextlib
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand, ErrorEvent

from .ai.gemini import BeautyAI
from .ai.makeup import GeminiImageProvider
from .catalog import Catalog
from .config import Settings
from .db import Database
from .handlers import academy, admin, look, makeup, menu, perfume, shop, skin
from .middlewares import LangMiddleware, ThrottleMiddleware
from .scheduler import scheduler_loop
from .storage import SQLiteStorage
from .texts import DEFAULT_LANG, t

log = logging.getLogger("beauty_bot")


def build_dispatcher(db: Database, catalog: Catalog, ai: BeautyAI, settings: Settings, image_provider,
                     throttle: ThrottleMiddleware | None = None) -> Dispatcher:
    dp = Dispatcher(
        storage=SQLiteStorage(db),
        db=db,
        catalog=catalog,
        ai=ai,
        settings=settings,
        image_provider=image_provider,
    )
    throttle = throttle or ThrottleMiddleware()
    dp.message.outer_middleware(throttle)
    dp.callback_query.outer_middleware(throttle)
    lang_mw = LangMiddleware(db)
    for observer in (dp.message, dp.callback_query, dp.pre_checkout_query):
        observer.outer_middleware(lang_mw)

    @dp.errors()
    async def on_error(event: ErrorEvent) -> bool:
        log.exception("Handler xatosi", exc_info=event.exception)
        update = event.update
        target = update.message or (update.callback_query.message if update.callback_query else None)
        user = update.message.from_user if update.message else (
            update.callback_query.from_user if update.callback_query else None)
        if target is not None and user is not None:
            lang = await db.get_lang(user.id) or DEFAULT_LANG
            with contextlib.suppress(Exception):
                await target.answer(t("error_generic", lang))
        return True

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


async def check_models(ai: BeautyAI, settings: Settings) -> None:
    """Model nomlari to'g'riligini tekshiradi (Google model nomlarini vaqti-vaqti bilan yangilaydi)."""
    try:
        available = await ai.available_models()
    except Exception as e:  # tarmoq yoki kalit muammosi: bot baribir ishga tushadi
        log.warning("Gemini modellar ro'yxatini olib bo'lmadi: %s", e)
        return
    wanted = [settings.gemini_model] + ([settings.gemini_image_model] if settings.makeup_images else [])
    for name in wanted:
        if name not in available:
            similar = sorted(m for m in available if m.startswith("gemini") and ("image" in m) == ("image" in name))
            log.error(
                "Model %r topilmadi. .env da GEMINI_MODEL / GEMINI_IMAGE_MODEL ni tuzating. Mavjudlari: %s",
                name, ", ".join(similar[:15]),
            )


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    settings = Settings.from_env()
    db = Database(settings.db_path)
    await db.connect()
    catalog = Catalog.load(settings.catalog_path)
    catalog.apply_overrides(await db.overrides())  # admin o'zgartirgan narx va mavjudlik
    ai = BeautyAI(catalog, model=settings.gemini_model)
    image_provider = (
        GeminiImageProvider(ai.client, settings.gemini_image_model) if settings.makeup_images else None
    )
    await check_models(ai, settings)
    if not settings.admin_ids:
        log.warning("ADMIN_IDS bo'sh: hech kim buyurtma holatini o'zgartira olmaydi")
    log.info(
        "Katalog: %d mahsulot. Makiyaj rasmi: %s. Onlayn to'lov: %s",
        len(catalog.products),
        "yoqilgan" if image_provider else "o'chirilgan",
        "yoqilgan" if settings.payment_provider_token else "o'chirilgan (faqat kuryerga)",
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
    background = asyncio.create_task(scheduler_loop(bot, db, settings))
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        background.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await background
        await db.close()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
