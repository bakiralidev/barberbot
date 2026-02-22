# bot/main.py
import asyncio
import logging
from aiogram import Bot, Dispatcher
from core.config import settings
from bot.middlewares.db_session import DbSessionMiddleware
from bot.handlers import common, client_booking, client_my_bookings, admin

bot = Bot(token=settings.BOT_TOKEN)

async def main():
    dp = Dispatcher()
    dp.update.middleware(DbSessionMiddleware())
    
    dp.include_router(common.router)
    dp.include_router(client_booking.router)
    dp.include_router(client_my_bookings.router)
    dp.include_router(admin.router)
    from bot.handlers import portfolio
    dp.include_router(portfolio.router)
    
    # Scheduler ishga tushirish
    from services.scheduler import setup_scheduler
    setup_scheduler(bot)
    
    logging.info("Starting bot...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    from core.logger import setup_logger
    setup_logger()
    asyncio.run(main())
