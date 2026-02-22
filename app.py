import logging
import sys
from aiohttp import web

from aiogram import Bot, Dispatcher
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

from core.config import settings
from core.logger import setup_logger
from bot.middlewares.db_session import DbSessionMiddleware
from bot.handlers import common, client_booking, client_my_bookings, admin, portfolio
from services.scheduler import setup_scheduler

# Loglarni sozlash
setup_logger()
logger = logging.getLogger(__name__)

async def on_startup(bot: Bot):
    # Webhook-ni o'rnatish
    webhook_url = settings.webhook_url
    logger.info(f"Setting webhook: {webhook_url}")
    await bot.set_webhook(
        url=webhook_url,
        secret_token=settings.WEBHOOK_SECRET
    )
    
    # Scheduler ishga tushirish
    setup_scheduler(bot)
    logger.info("Bot started successfully in webhook mode")

def create_app():
    # Bot va Dispatcher yaratish
    bot = Bot(token=settings.BOT_TOKEN)
    dp = Dispatcher()
    
    # Middleware-larni qo'shish
    dp.update.middleware(DbSessionMiddleware())
    
    # Routerlarni qo'shish
    dp.include_router(common.router)
    dp.include_router(client_booking.router)
    dp.include_router(client_my_bookings.router)
    dp.include_router(admin.router)
    dp.include_router(portfolio.router)
    
    # Register self-startup task
    dp.startup.register(on_startup)
    
    # aiohttp application yaratish
    app = web.Application()
    
    # Webhook handler-ni sozlash
    webhook_requests_handler = SimpleRequestHandler(
        dispatcher=dp,
        bot=bot,
        secret_token=settings.WEBHOOK_SECRET,
    )
    
    # Webhook route-ni ro'yxatdan o'tkazish
    webhook_requests_handler.register(app, path=settings.WEBHOOK_PATH)
    
    # Dispatcher va Bot-ni application bilan bog'lash
    setup_application(app, dp, bot=bot)
    
    return app

if __name__ == "__main__":
    import os
    app = create_app()
    # Alwaysdata PORT o'zgaruvchisini beradi, topsa shuni ishlatadi, aks holda 8080
    port = int(os.environ.get("PORT", 8080))
    logger.info(f"Starting server on port {port}")
    web.run_app(app, host="0.0.0.0", port=port)
