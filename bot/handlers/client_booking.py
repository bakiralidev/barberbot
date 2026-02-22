# bot/handlers/client_booking.py
from datetime import date, datetime, time
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from bot.states import BookingState
from bot.keyboards.client import services_kb, dates_kb, slots_kb, confirm_kb, phone_req_kb, main_menu_kb
from services.admin import get_all_services, get_setting
from services.schedule import get_slots
from services.booking import create_booking, SlotOccupiedError, get_user_bookings
from db.models import User, Service, Appointment, AppointmentStatus
from sqlalchemy import select

router = Router()

@router.callback_query(F.data.startswith("taken_"))
async def slot_taken(callback: CallbackQuery):
    await callback.answer("⚠️ Bu vaqt band, iltimos boshqasini tanlang!", show_alert=True)

@router.message(F.text == "✂️ Band qilish")
async def start_booking(message: Message, session: AsyncSession, state: FSMContext):
    # Check for existing active bookings
    user_stmt = select(User).where(User.telegram_user_id == message.from_user.id)
    user = (await session.execute(user_stmt)).scalar_one_or_none()
    
    if user:
        active_bookings = await get_user_bookings(session, user.id)
        if active_bookings:
            phone = await get_setting(session, "barber_phone", "+998 90 123 45 67")
            await message.answer(
                f"⚠️ Sizda allaqachon faol buyurtma mavjud.\n"
                f"Yana bir bor band qilish uchun sartarosh bilan bog'laning:\n"
                f"📞 {phone}"
            )
            return

    services = await get_all_services(session)
    if not services:
        await message.answer("Hozirda hech qanday xizmat mavjud emas. Iltimos, keyinroq qayta urinib ko'ring.")
        return
    
    await state.set_state(BookingState.selecting_service)
    await message.answer("Xizmatni tanlang:", reply_markup=services_kb(services))

@router.callback_query(F.data == "back_main")
async def back_main(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.delete()
    await callback.message.answer("🏠 Asosiy menyu", reply_markup=main_menu_kb())

@router.callback_query(F.data == "back_date")
async def back_date(callback: CallbackQuery, state: FSMContext):
    await state.set_state(BookingState.selecting_date)
    await callback.message.edit_text("Sana tanlang:", reply_markup=dates_kb())

@router.callback_query(BookingState.selecting_service, F.data.startswith("srv_"))
async def service_selected(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    service_id = int(callback.data.split("_")[1])
    await state.update_data(service_id=service_id)
    await state.set_state(BookingState.selecting_date)
    await callback.message.edit_text("Sana tanlang:", reply_markup=dates_kb())

@router.callback_query(BookingState.selecting_date, F.data.startswith("date_"))
async def date_selected(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    date_str = callback.data.split("_")[1]
    selected_date = date.fromisoformat(date_str)
    
    data = await state.get_data()
    service_id = data['service_id']
    slots = await get_slots(session, service_id, selected_date)
    await state.update_data(selected_date=date_str)
    
    if not slots:
        await callback.answer("Bu sana uchun vaqt mavjud emas", show_alert=True)
        return

    await state.set_state(BookingState.selecting_time)
    await callback.message.edit_text(f"Vaqt tanlang {date_str}:", reply_markup=slots_kb(slots, selected_date))

@router.callback_query(BookingState.selecting_time, F.data.startswith("time_"))
async def time_selected(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")
    date_str = parts[1]
    time_str = parts[2]
    await state.update_data(selected_date=date_str, selected_time=time_str)
    await state.set_state(BookingState.confirming)
    await callback.message.delete()
    await callback.message.answer("Iltimos, identifikatsiyangizni tasdiqlash uchun telefon raqamingizni ulashing:", reply_markup=phone_req_kb())

@router.message(BookingState.confirming, F.contact)
async def phone_shared(message: Message, state: FSMContext, session: AsyncSession):
    if message.contact.user_id and message.contact.user_id != message.from_user.id:
        await message.answer("⚠️ Quyidagi tugmadan foydalanib, o'z telefon raqamingizni ulashing.", reply_markup=phone_req_kb())
        return

    phone = message.contact.phone_number
    await state.update_data(phone=phone)
    data = await state.get_data()
    service_id = data['service_id']
    service = await session.get(Service, service_id)
    
    summary = (
        f"📝 **Bookingni tasdiqlang**\n"
        f"Xizmat: {service.name}\n"
        f"Sana: {data['selected_date']}\n"
        f"Vaqt: {data['selected_time']}\n"
        f"Telefon: {phone}"
    )
    await message.answer(summary, parse_mode="Markdown", reply_markup=confirm_kb())

@router.callback_query(BookingState.confirming, F.data == "confirm_booking")
async def finalize_booking(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    data = await state.get_data()
    service = await session.get(Service, data['service_id'])
    
    deposit_enabled = (await get_setting(session, "deposit_enabled", "false")) == "true"
    
    if deposit_enabled:
        card_num = await get_setting(session, "card_number", "Kiritilmagan")
        deposit_amount = float(service.price) * 0.1
        await state.update_data(payment_amount=deposit_amount)
        
        msg = (
            f"💳 **To'lov qilish**\n\n"
            f"Band qilishni yakunlash uchun xizmat narxining 10% ({deposit_amount:,.0f} so'm) miqdorida to'lov qiling.\n\n"
            f"Karta: `{card_num}`\n\n"
            f"To'lovni amalga oshirgach, **to'lov cheki (rasmi)ni yuboring**."
        )
        await callback.message.edit_text(msg, parse_mode="Markdown")
        await state.set_state(BookingState.paying)
    else:
        await process_final_booking(callback, state, session)

@router.message(BookingState.paying, F.photo)
async def receipt_received(message: Message, state: FSMContext, session: AsyncSession):
    photo = message.photo[-1].file_id
    await state.update_data(payment_receipt_url=photo)
    await process_final_booking(message, state, session)

async def process_final_booking(event, state: FSMContext, session: AsyncSession):
    data = await state.get_data()
    d = date.fromisoformat(data['selected_date'])
    t = time.fromisoformat(data['selected_time'])
    start_dt = datetime.combine(d, t)
    
    user_id = event.from_user.id
    stmt = select(User).where(User.telegram_user_id == user_id)
    user = (await session.execute(stmt)).scalar_one()

    is_callback = isinstance(event, CallbackQuery)
    bot = event.bot
    chat_id = event.message.chat.id if is_callback else event.chat.id

    try:
        booking = await create_booking(
            session=session,
            user_id=user.id,
            service_id=data['service_id'],
            start_time=start_dt,
            customer_phone=data['phone'],
            customer_name=user.first_name
        )
        
        if 'payment_amount' in data:
            booking.payment_amount = data['payment_amount']
            booking.payment_receipt_url = data.get('payment_receipt_url')

        await session.commit()
        
        success_msg = "✅ Booking so'rovi qabul qilindi! Admin tasdiqlashini kuting."
        if is_callback:
            await event.message.edit_text(success_msg)
        else:
            await event.answer(success_msg)

        service = await session.get(Service, data['service_id'])
        check_text = (
            f"🎫 **ELEKTRON CHEK**\n"
            f"------------------\n"
            f"ID: #{booking.id}\n"
            f"Mijoz: {user.first_name}\n"
            f"Xizmat: {service.name}\n"
            f"Vaqt: {data['selected_date']} {data['selected_time']}\n"
            f"Telefon: {data['phone']}\n"
            f"Status: ⏳ Kutilmoqda\n"
            f"------------------\n"
            f"Sartaroshga borganda ushbu chekni ko'rsating."
        )
        await bot.send_message(chat_id, check_text, parse_mode="Markdown")
        await bot.send_message(chat_id, "🏠 Asosiy menyu", reply_markup=main_menu_kb())
        await state.clear()
        
        from bot.keyboards.admin import admin_booking_action_kb
        msg_text = (
            f"🆕 **Yangi Booking So'rovi**\n"
            f"Mijoz: {user.first_name} (@{user.username})\n"
            f"Telefon: {data['phone']}\n"
            f"Vaqt: {data['selected_date']} {data['selected_time']}\n"
            f"To'lov: {f'{data.get('payment_amount'):,.0f} so\'m' if 'payment_amount' in data else 'Yo\'q'}"
        )
        
        admin_query = select(User.telegram_user_id).where((User.is_superadmin == True) | (User.admin_type.is_not(None)))
        res = await session.execute(admin_query)
        admin_ids = res.scalars().all()
        for admin_id in admin_ids:
            try:
                if 'payment_receipt_url' in data:
                    await bot.send_photo(
                        admin_id, photo=data['payment_receipt_url'], 
                        caption=msg_text, parse_mode="Markdown", 
                        reply_markup=admin_booking_action_kb(booking.id, AppointmentStatus.PENDING.value)
                    )
                else:
                    await bot.send_message(
                        admin_id, msg_text, parse_mode="Markdown", 
                        reply_markup=admin_booking_action_kb(booking.id, AppointmentStatus.PENDING.value)
                    )
            except: pass

    except SlotOccupiedError:
        err_msg = "⚠️ Slot allaqachon band!"
        if is_callback:
            await event.answer(err_msg, show_alert=True)
            await event.message.edit_text("Bu slot allaqachon band. Sana tanlang:", reply_markup=dates_kb())
        else:
            await event.answer(err_msg)
            await event.answer("Bu slot allaqachon band. Sana tanlang:", reply_markup=dates_kb())
        await state.set_state(BookingState.selecting_date)
    except Exception as e:
        final_err = f"Yakunlash xatosi: {str(e)}"
        if is_callback:
            await event.message.edit_text(final_err)
        else:
            await event.answer(final_err)
        await state.clear()
