from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from db.models import User
from bot.keyboards.client import main_menu_kb
from bot.keyboards.admin import admin_menu_kb
from core.config import settings
from services.admin import get_setting

router = Router()

@router.message(CommandStart())
async def cmd_start(message: Message, session: AsyncSession, state: FSMContext):
    await state.clear()
    
    telegram_id = message.from_user.id
    
    # Sync User
    stmt = select(User).where(User.telegram_user_id == telegram_id)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()
    
    is_super_in_env = telegram_id in settings.superadmin_ids
    
    if not user:
        user = User(
            telegram_user_id=telegram_id,
            first_name=message.from_user.first_name,
            last_name=message.from_user.last_name,
            username=message.from_user.username,
            is_superadmin=is_super_in_env
        )
        session.add(user)
    else:
        # Only promote if found in env list; do not auto-demote
        if is_super_in_env and not user.is_superadmin:
            user.is_superadmin = True
            
        # Update info if changed (optional improvement, good for fresh data)
        if user.first_name != message.from_user.first_name:
            user.first_name = message.from_user.first_name
        if user.last_name != message.from_user.last_name:
            user.last_name = message.from_user.last_name
        if user.username != message.from_user.username:
            user.username = message.from_user.username

    await session.commit()
    
    if user.is_superadmin or user.admin_type:
        await message.answer("👋 Xush kelibsiz, Admin! Admin panel ishga tushdi:", reply_markup=admin_menu_kb(user.is_superadmin))
    else:
        await message.answer("👋 BarberBotga xush kelibsiz! Variantni tanlang:", reply_markup=main_menu_kb())

@router.message(F.text == "ℹ️ Ma'lumot")
async def cmd_info(message: Message, session: AsyncSession):
    name = await get_setting(session, "barber_name", "Sartarosh")
    phone = await get_setting(session, "barber_phone", "+998 90 123 45 67")
    addr = await get_setting(session, "barber_address", "Toshkent")
    loc = await get_setting(session, "barber_location", "https://maps.google.com")
    
    msg = (
        f"💈 **{name}**\n\n"
        f"📍 Manzil: {addr}\n"
        f"📞 Telefon: {phone}\n\n"
        f"📍 [Xaritada ko'rish]({loc})"
    )
    await message.answer(msg, parse_mode="Markdown")
