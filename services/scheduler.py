# services/scheduler.py
import logging
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from db.models import Appointment, User, AppointmentStatus
from db.session import async_session
from utils.time import from_utc
from aiogram import Bot

logger = logging.getLogger(__name__)

async def send_reminders(bot: Bot):
    """Navbatga 1 soat qolganda eslatma yuborish"""
    async with async_session() as session:
        # Hozirgi vaqtdan 1 soat keyingi vaqtni hisoblaymiz
        target_time = datetime.now() + timedelta(hours=1)
        
        # 1 soatdan kam vaqt qolgan, tasdiqlangan va eslatma yuborilmaganlarni qidiramiz
        stmt = (
            select(Appointment)
            .where(
                Appointment.status == AppointmentStatus.CONFIRMED.value,
                Appointment.starts_at <= target_time,
                Appointment.reminder_sent == False
            )
        )
        res = await session.execute(stmt)
        appointments = res.scalars().all()
        
        for app in appointments:
            try:
                user_stmt = select(User).where(User.id == app.user_id)
                user = (await session.execute(user_stmt)).scalar_one()
                
                local_time = from_utc(app.starts_at)
                msg = (
                    f"⏰ **Eslatma!**\n"
                    f"Sizning bookingingizga 1 soatdan kam vaqt qoldi.\n"
                    f"Vaqt: {local_time.strftime('%H:%M')}\nXizmat: {app.service.name if app.service else ''}"
                )
                
                await bot.send_message(user.telegram_user_id, msg, parse_mode="Markdown")
                app.reminder_sent = True
                logger.info(f"Reminder sent to user {user.telegram_user_id} for appointment {app.id}")
            except Exception as e:
                logger.error(f"Error sending reminder for app {app.id}: {e}")
        
        await session.commit()

def setup_scheduler(bot: Bot):
    scheduler = AsyncIOScheduler()
    # Har 15 daqiqada tekshirib turadi
    scheduler.add_job(send_reminders, "interval", minutes=15, args=[bot])
    scheduler.start()
    logger.info("Scheduler started.")
    return scheduler
