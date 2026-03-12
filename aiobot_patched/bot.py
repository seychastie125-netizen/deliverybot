import asyncio
import logging
import os
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties

from config import config
from database.db import db
from handlers import client, cart, order, admin, manager
from handlers import admin_modifiers, client_modifiers
from handlers import favorites, analytics
from middlewares.throttling import ThrottlingMiddleware
from middlewares.bot_active import BotActiveMiddleware
from middlewares.register_user import AutoRegisterMiddleware
from utils.scheduler import setup_scheduler, stop_scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    handlers=[
        logging.FileHandler("bot.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


async def on_startup(bot: Bot):
    await db.connect()
    logger.info("Database connected")
    setup_scheduler(bot)
    me = await bot.get_me()
    logger.info(f"Bot started: @{me.username}")
    for aid in config.ADMIN_IDS:
        try:
            await bot.send_message(aid, "🟢 Бот запущен!")
        except Exception:
            pass


async def on_shutdown(bot: Bot):
    stop_scheduler()
    await db.close()
    logger.info("Bot stopped")
    for aid in config.ADMIN_IDS:
        try:
            await bot.send_message(aid, "🔴 Бот остановлен!")
        except Exception:
            pass


async def main():
    os.makedirs(os.path.dirname(config.DB_PATH) or ".", exist_ok=True)

    bot = Bot(
        token=config.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    # ПРИМЕЧАНИЕ: MemoryStorage подходит только для разработки.
    # В продакшене замените на RedisStorage для сохранения состояний
    # при перезапуске бота:
    #   from aiogram.fsm.storage.redis import RedisStorage
    #   storage = RedisStorage.from_url(os.getenv("REDIS_URL", "redis://localhost"))
    dp = Dispatcher(storage=MemoryStorage())

    # Middleware
    dp.message.middleware(ThrottlingMiddleware(rate_limit=0.3))
    dp.callback_query.middleware(ThrottlingMiddleware(rate_limit=0.3))
    dp.message.middleware(AutoRegisterMiddleware())
    dp.message.middleware(BotActiveMiddleware())
    dp.callback_query.middleware(AutoRegisterMiddleware())
    dp.callback_query.middleware(BotActiveMiddleware())

    # Роутеры (порядок важен!)
    dp.include_router(admin.router)
    dp.include_router(admin_modifiers.router)
    dp.include_router(analytics.router)
    dp.include_router(manager.router)
    dp.include_router(client_modifiers.router)
    dp.include_router(order.router)
    dp.include_router(favorites.router)
    dp.include_router(cart.router)
    dp.include_router(client.router)

    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    logger.info("Starting bot...")
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == "__main__":
    asyncio.run(main())