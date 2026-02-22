
# bot/handlers/client_my_bookings.py
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from db.models import User, Appointment
from services.booking import get_user_bookings, cancel_booking as cancel_booking_service, reschedule_booking, SlotOccupiedError
from services.schedule import get_slots
from bot.keyboards.client import dates_kb, slots_kb
from bot.states import BookingState
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from datetime import date, time as time_type, datetime
from utils.time import from_utc

router = Router()

@router.callback_query(F.data.startswith("taken_"))
async def slot_taken_my(callback: CallbackQuery):
    await callback.answer("⚠️ Bu vaqt band, iltimos boshqasini tanlang!", show_alert=True)

@router.message(F.text == "📅 Mening buyurtmalarim")
async def my_bookings(message: Message, session: AsyncSession):
    stmt = select(User).where(User.telegram_user_id == message.from_user.id)
    user = (await session.execute(stmt)).scalar_one_or_none()
    
    if not user:
        return
    
    bookings = await get_user_bookings(session, user.id)
    
    if not bookings:
        await message.answer("Sizda kelgusi buyurtmalar yo'q.")
        return
    
    await message.answer(f"📅 **Sizning buyurtmalaringiz ({len(bookings)}):**", parse_mode="Markdown")
    
    for b in bookings:
        local_start = from_utc(b.starts_at)
        text = (
            f"🔹 **{local_start.strftime('%Y-%m-%d %H:%M')}**\n"
            f"Holat: {b.status}\n"
             f"Xizmat: {b.service.name if b.service else 'Mavjud emas'}"
        )

        builder = InlineKeyboardBuilder()
        if b.status in ['pending', 'confirmed']:
             builder.button(text=f"🔄 Ko'chirish", callback_data=f"resched_me_{b.id}")
             builder.button(text=f"❌ Bekor qilish", callback_data=f"cancel_me_{b.id}")
        builder.adjust(2)
        
        await message.answer(text, parse_mode="Markdown", reply_markup=builder.as_markup())

@router.callback_query(F.data.startswith("cancel_me_"))
async def cancel_my_booking(callback: CallbackQuery, session: AsyncSession):
    b_id = int(callback.data.split("_")[2])
    
    # SECURITY: ownership check
    booking = await session.get(Appointment, b_id)
    if not booking:
        await callback.answer("Booking topilmadi.")
        return

    user_stmt = select(User).where(User.telegram_user_id == callback.from_user.id)
    user = (await session.execute(user_stmt)).scalar_one_or_none()
    
    if not user or booking.user_id != user.id:
        await callback.answer("Kirish rad etildi.", show_alert=True)
        return

    await cancel_booking_service(session, b_id)
    await callback.answer("Booking bekor qilindi.")
    await callback.message.edit_text(f"❌ Booking {b_id} bekor qilindi.")

# --- RESCHEDULE FLOW ---

@router.callback_query(F.data.startswith("resched_me_"))
async def resched_start(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    b_id = int(callback.data.split("_")[2])
    
    # SECURITY: ownership check
    booking = await session.get(Appointment, b_id)
    if not booking:
        await callback.answer("Booking topilmadi.")
        return

    user_stmt = select(User).where(User.telegram_user_id == callback.from_user.id)
    user = (await session.execute(user_stmt)).scalar_one_or_none()
    
    if not user or booking.user_id != user.id:
        await callback.answer("Kirish rad etildi.", show_alert=True)
        return

    await state.update_data(resched_booking_id=b_id)
    await state.set_state(BookingState.rescheduling_date)
    await callback.message.answer("Yangi sana tanlang:", reply_markup=dates_kb())

@router.callback_query(BookingState.rescheduling_date, F.data.startswith("date_"))
async def resched_date(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    date_str = callback.data.split("_")[1]
    selected_date = date.fromisoformat(date_str)
    
    data = await state.get_data()
    b_id = data['resched_booking_id']
    
    booking = await session.get(Appointment, b_id)
    if not booking:
        await callback.answer("Sessiya xatosi.")
        return

    slots = await get_slots(session, booking.service_id, selected_date)
    await state.update_data(resched_date=date_str)
    
    if not slots:
        await callback.answer("Bo'sh vaqt yo'q.", show_alert=True)
        return

    await state.set_state(BookingState.rescheduling_time)
    await callback.message.edit_text(f"{date_str} uchun vaqt tanlang:", reply_markup=slots_kb(slots, selected_date))

@router.callback_query(BookingState.rescheduling_time, F.data.startswith("time_"))
async def resched_time(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    parts = callback.data.split("_")
    date_str = parts[1]
    time_str = parts[2]
    
    data = await state.get_data()
    b_id = data['resched_booking_id']
    
    # SECURITY: ownership check
    booking = await session.get(Appointment, b_id)
    user_stmt = select(User).where(User.telegram_user_id == callback.from_user.id)
    user = (await session.execute(user_stmt)).scalar_one_or_none()
    
    if not user or not booking or booking.user_id != user.id:
        await callback.answer("Kirish rad etildi.")
        return
    
    d = date.fromisoformat(date_str)
    t = time_type.fromisoformat(time_str)
    new_start = datetime.combine(d, t)
    
    try:
        await reschedule_booking(session, b_id, new_start)
        await callback.message.edit_text(f"✅ Booking {date_str} {time_str}ga ko'chirildi")
        await state.clear()
        
        # Notify Admins about reschedule
        admin_query = select(User.telegram_user_id).where((User.is_superadmin == True) | (User.admin_type.is_not(None)))
        res = await session.execute(admin_query)
        admin_ids = res.scalars().all()
        
        for admin_id in admin_ids:
            try:
                await callback.bot.send_message(
                    admin_id, 
                    f"🔄 **Booking ko'chirildi!**\n\nMijoz: {user.first_name}\nYangi vaqt: {date_str} {time_str}",
                    parse_mode="Markdown"
                )
            except: pass
    except SlotOccupiedError:
        await callback.answer("⚠️ Vaqt band!", show_alert=True)
        await callback.message.edit_text("Boshqa sana tanlang:", reply_markup=dates_kb())
        await state.set_state(BookingState.rescheduling_date)
    except Exception as e:
        await callback.message.edit_text(f"Xato: {e}")
