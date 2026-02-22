import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InputMediaPhoto
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from db.models import PortfolioItem
from bot.states import AdminState

logger = logging.getLogger(__name__)
from services.admin import get_setting

router = Router()

@router.callback_query(F.data == "add_portfolio_works")
async def admin_add_portfolio_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AdminState.adding_portfolio)
    await callback.message.answer(
        "📸 Portfoliyaga rasm qo'shish rejimi yoqildi.\n\n"
        "Iltimos, kanaldan o'zingizga yoqqan rasmlarni shu yerga yuboring (Forward qiling).\n"
        "Tugatgandan so'ng xohlagan boshqa buyruqni bosing yoki /start yozing.",
        reply_markup=None
    )
    await callback.answer()

@router.message(AdminState.adding_portfolio, F.photo)
async def admin_save_manual_portfolio(message: Message, session: AsyncSession):
    item = PortfolioItem(
        message_id=message.message_id,
        photo_file_id=message.photo[-1].file_id,
        caption=message.caption
    )
    session.add(item)
    await session.commit()
    await message.reply("✅ Saqlandi! Yana yuborishingiz mumkin.")

@router.message(F.text == "📸 Portfolio")
async def show_portfolio(message: Message, session: AsyncSession):
    logger.info(f"Show portfolio requested by {message.from_user.id}")
    # Oxirgi 5 ta rasmni olish
    stmt = select(PortfolioItem).order_by(PortfolioItem.created_at.desc()).limit(5)
    res = await session.execute(stmt)
    items = res.scalars().all()
    
    if not items:
        await message.answer("Hozircha portfoliyada ishlar mavjud emas.")
        return
    
    # Media group tayyorlash
    media = []
    for i, item in enumerate(items):
        media.append(InputMediaPhoto(
            media=item.photo_file_id, 
            caption=item.caption if i == 0 else "" # Faqat birinchi rasmga caption qo'yamiz (Telegram qoidasi)
        ))
    
    await message.answer_media_group(media=media)
    
    # Kanal linki bilan tugma yuborish
    channel_link = await get_setting(session, "portfolio_channel_link", "https://t.me/telegram")
    
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    builder.button(text="👁 Barchasini ko'rish (Kanalda)", url=channel_link)
    
    await message.answer(
        "Eng so'nggi ishlarimizni yuqorida ko'rishingiz mumkin. Barcha ishlar bilan kanalimizda tanishing:",
        reply_markup=builder.as_markup()
    )
