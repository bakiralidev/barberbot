
# bot/handlers/admin.py
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import time, datetime
import re

from db.models import Appointment, AppointmentStatus, Service, WorkSchedule, User
from services.booking import cancel_booking
from services.admin import (
    get_all_services, toggle_service_active, create_service, 
    get_work_schedule, update_work_schedule_day, get_admins, set_admin_role,
    delete_service, update_service, get_setting, set_setting
)
from services.booking import reschedule_booking, SlotOccupiedError
from bot.keyboards.admin import (
    admin_booking_action_kb, admin_menu_kb, admin_services_kb, 
    admin_service_edit_kb, admin_schedule_kb, admins_list_kb, admin_role_kb, manage_admin_kb,
    admin_settings_kb, edit_info_kb, manual_services_kb
)
from bot.keyboards.client import main_menu_kb
from bot.states import AdminState
from core.config import settings
from utils.time import from_utc

router = Router()

@router.callback_query(F.data.startswith("taken_"))
async def slot_taken_admin(callback: CallbackQuery):
    await callback.answer("⚠️ Bu vaqt band bo'lib qoladi, iltimos boshqasini tanlang!", show_alert=True)

async def ensure_admin_user(telegram_id: int, session: AsyncSession):
    stmt = select(User).where(User.telegram_user_id == telegram_id)
    res = await session.execute(stmt)
    return res.scalar_one_or_none()

def can_access_admin_panel(user: User) -> bool:
    if not user: return False
    return user.is_superadmin or (user.admin_type is not None)

def can_manage_admins(user: User) -> bool:
    # Superadmin only - requirement
    if not user: return False
    return user.is_superadmin

@router.message(Command("admin"))
async def admin_start(message: Message, session: AsyncSession):
    import logging
    logging.info(f"Admin start command received from {message.from_user.id}")
    user = await ensure_admin_user(message.from_user.id, session)
    if not user:
        logging.info(f"User {message.from_user.id} not found in DB")
    else:
        logging.info(f"User {message.from_user.id} found in DB, is_superadmin: {user.is_superadmin}")
    
    if not can_access_admin_panel(user):
        logging.warning(f"Access denied for user {message.from_user.id}")
        return
    await message.answer("Boshqaruv Paneli", reply_markup=admin_menu_kb(user.is_superadmin))

@router.message(F.text == "👤 Mijoz paneli")
async def admin_switch_to_client(message: Message, session: AsyncSession):
    user = await ensure_admin_user(message.from_user.id, session)
    if not can_access_admin_panel(user): return
    await message.answer("Mijoz paneli ishga tushdi:", reply_markup=main_menu_kb())

# --- BOOKINGS ---
@router.message(F.text == "📅 Buyurtmalar")
async def admin_list_bookings(message: Message, session: AsyncSession):
    user = await ensure_admin_user(message.from_user.id, session)
    if not can_access_admin_panel(user): return
    
    query = select(Appointment).order_by(Appointment.starts_at.desc()).limit(10)
    res = await session.execute(query)
    bookings = res.scalars().all()
    
    if not bookings:
        await message.answer("Bookinglar topilmadi.")
        return

    text = "So'nggi buyurtmalar:\n"
    for b in bookings:
        status_icon = {
            AppointmentStatus.CONFIRMED: "✅",
            AppointmentStatus.PENDING: "⏳",
            AppointmentStatus.CANCELLED: "❌"
        }.get(b.status, "❓")
        
        local_start = from_utc(b.starts_at)
        text += f"{status_icon} ID: {b.id} | {local_start.strftime('%m-%d %H:%M')}\n"
        text += f"Mijoz: {b.customer_name} ({b.customer_phone})\nKo'rish: /adm_view_{b.id}\n\n"
    
    await message.answer(text)

@router.message(F.text.regexp(r"^/adm_view_(\d+)$").as_("match"))
async def view_booking_details(message: Message, session: AsyncSession, match: re.Match):
    user = await ensure_admin_user(message.from_user.id, session)
    if not can_access_admin_panel(user): return

    try:
        b_id = int(match.group(1))
        b = await session.get(Appointment, b_id)
        if b:
            local_start = from_utc(b.starts_at)
            await message.answer(
                f"Booking #{b.id}\nHolat: {b.status}\nVaqt: {local_start.strftime('%Y-%m-%d %H:%M')}\nMijoz: {b.customer_name} {b.customer_phone}",
                reply_markup=admin_booking_action_kb(b.id, b.status)
            )
    except:
        pass

@router.callback_query(F.data.startswith("adm_confirm_"))
async def admin_confirm(callback: CallbackQuery, session: AsyncSession):
    user = await ensure_admin_user(callback.from_user.id, session)
    if not can_access_admin_panel(user): 
        await callback.answer("Kirish rad etildi", show_alert=True)
        return

    booking_id = int(callback.data.split("_")[2])
    booking = await session.get(Appointment, booking_id)
    
    if booking:
        booking.status = AppointmentStatus.CONFIRMED
        if booking.payment_receipt_url:
            booking.is_paid = True
            booking.payment_confirmed_at = datetime.now()
        await session.commit()
        
        success_txt = f"✅ Booking {booking_id} tasdiqlandi."
        if callback.message.photo:
            await callback.message.edit_caption(caption=success_txt)
        else:
            await callback.message.edit_text(success_txt)
        
        try:
             user_q = await session.get(User, booking.user_id)
             if user_q:
                local_start = from_utc(booking.starts_at)
                await callback.bot.send_message(user_q.telegram_user_id, f"✅ Sizning {local_start.strftime('%m-%d %H:%M')} vaqtidagi uchrashuvingiz tasdiqlandi!")
        except:
             pass

@router.callback_query(F.data.startswith("adm_complete_"))
async def admin_complete(callback: CallbackQuery, session: AsyncSession):
    user = await ensure_admin_user(callback.from_user.id, session)
    if not can_access_admin_panel(user): return

    booking_id = int(callback.data.split("_")[2])
    booking = await session.get(Appointment, booking_id)
    
    if booking:
        booking.status = AppointmentStatus.COMPLETED
        await session.commit()
        
        complete_txt = f"🏁 Booking {booking_id} tugallandi deb belgilandi."
        if callback.message.photo:
            await callback.message.edit_caption(caption=complete_txt)
        else:
            await callback.message.edit_text(complete_txt)
        
        try:
             client = await session.get(User, booking.user_id)
             if client:
                await callback.bot.send_message(
                    client.telegram_user_id, 
                    f"✅ Buyurtmangiz yakunlandi. Tashrifingiz uchun rahmat! 😊"
                )
        except:
             pass

@router.callback_query(F.data.startswith("adm_cancel_"))
async def admin_cancel(callback: CallbackQuery, session: AsyncSession):
    user = await ensure_admin_user(callback.from_user.id, session)
    if not can_access_admin_panel(user): 
        await callback.answer("Kirish rad etildi", show_alert=True)
        return

    booking_id = int(callback.data.split("_")[2])
    await cancel_booking(session, booking_id)
    cancel_txt = f"❌ Booking {booking_id} bekor qilindi."
    if callback.message.photo:
        await callback.message.edit_caption(caption=cancel_txt)
    else:
        await callback.message.edit_text(cancel_txt)

# --- ADMIN RESCHEDULE ---
@router.callback_query(F.data.startswith("adm_resched_"))
async def admin_resched_start(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    user = await ensure_admin_user(callback.from_user.id, session)
    if not can_access_admin_panel(user): 
        await callback.answer("Kirish rad etildi", show_alert=True)
        return
    
    b_id = int(callback.data.split("_")[2])
    await state.update_data(resched_booking_id=b_id)
    await state.set_state(AdminState.reschedule_date)
    from bot.keyboards.client import dates_kb
    await callback.message.answer("Mijoz uchun YANGI sana tanlang:", reply_markup=dates_kb())

@router.callback_query(AdminState.reschedule_date, F.data.startswith("date_"))
async def admin_resched_date(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    user = await ensure_admin_user(callback.from_user.id, session)
    if not can_access_admin_panel(user): return
    
    date_str = callback.data.split("_")[1]
    selected_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    
    data = await state.get_data()
    b_id = data['resched_booking_id']
    booking = await session.get(Appointment, b_id)
    
    from services.schedule import get_slots
    from bot.keyboards.client import slots_kb
    slots = await get_slots(session, booking.service_id, selected_date)
    
    await state.update_data(resched_date=date_str)
    await state.set_state(AdminState.reschedule_time)
    await callback.message.edit_text(f"{date_str} uchun vaqt tanlang:", reply_markup=slots_kb(slots, selected_date))

@router.callback_query(AdminState.reschedule_time, F.data.startswith("time_"))
async def admin_resched_time(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    user = await ensure_admin_user(callback.from_user.id, session)
    if not can_access_admin_panel(user): return
    
    parts = callback.data.split("_")
    date_str = parts[1]
    time_str = parts[2]
    
    data = await state.get_data()
    b_id = data['resched_booking_id']
    
    new_start = datetime.combine(
        datetime.strptime(date_str, "%Y-%m-%d").date(),
        datetime.strptime(time_str, "%H:%M").time()
    )
    
    try:
        await reschedule_booking(session, b_id, new_start)
        await callback.message.edit_text(f"✅ Booking #{b_id} {date_str} {time_str}ga ko'chirildi")
        await state.clear()
        
        # Notify client
        booking = await session.get(Appointment, b_id)
        if booking:
            client = await session.get(User, booking.user_id)
            if client:
                 try:
                     await callback.bot.send_message(
                         client.telegram_user_id, 
                         f"🔄 Sizning bookingingiz admin tomonidan quyidagi vaqtga ko'chirildi: {date_str} {time_str}"
                     )
                 except: pass
    except SlotOccupiedError:
        await callback.answer("⚠️ Vaqt band!", show_alert=True)
    except Exception as e:
        await callback.message.edit_text(f"Ko'chirish xatosi: {e}")

# --- SERVICES ---
@router.message(F.text == "🛠 Xizmatlar")
async def admin_services(message: Message, session: AsyncSession):
    user = await ensure_admin_user(message.from_user.id, session)
    if not can_access_admin_panel(user): return
    services = await get_all_services(session)
    await message.answer("Xizmatlarni boshqarish:", reply_markup=admin_services_kb(services))

@router.callback_query(F.data == "adm_srv_add")
async def admin_srv_add_start(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    user = await ensure_admin_user(callback.from_user.id, session)
    if not can_access_admin_panel(user): 
        await callback.answer("Kirish rad etildi", show_alert=True)
        return

    await state.set_state(AdminState.add_service_name)
    await callback.message.answer("Xizmat nomini kiriting:")

@router.message(AdminState.add_service_name)
async def admin_srv_add_name(message: Message, state: FSMContext, session: AsyncSession):
    user = await ensure_admin_user(message.from_user.id, session)
    if not can_access_admin_panel(user): return
    await state.update_data(name=message.text)
    await state.set_state(AdminState.add_service_price)
    await message.answer("Narxni kiriting:")

@router.message(AdminState.add_service_price)
async def admin_srv_add_price(message: Message, state: FSMContext, session: AsyncSession):
    user = await ensure_admin_user(message.from_user.id, session)
    if not can_access_admin_panel(user): return
    try:
        price = float(message.text)
        await state.update_data(price=price)
        await state.set_state(AdminState.add_service_duration)
        await message.answer("Davomiylikni kiriting (daqiqa):")
    except:
        await message.answer("Noto'g'ri narx. Iltimos, raqam kiriting.")

@router.message(AdminState.add_service_duration)
async def admin_srv_add_duration(message: Message, state: FSMContext, session: AsyncSession):
    user = await ensure_admin_user(message.from_user.id, session)
    if not can_access_admin_panel(user): return
    try:
        duration = int(message.text)
        data = await state.get_data()
        await create_service(session, data['name'], data['price'], duration)
        await message.answer("✅ Xizmat yaratildi!")
        await state.clear()
        services = await get_all_services(session)
        await message.answer("Xizmatlarni boshqarish:", reply_markup=admin_services_kb(services))
    except:
        await message.answer("Noto'g'ri davomiylik. Iltimos, daqiqalarda raqam kiriting.")

@router.callback_query(F.data.startswith("srv_menu_"))
async def admin_srv_edit_menu(callback: CallbackQuery, session: AsyncSession):
    user = await ensure_admin_user(callback.from_user.id, session)
    if not can_access_admin_panel(user): 
        await callback.answer("Kirish rad etildi", show_alert=True)
        return
    
    try:
        s_id = int(callback.data.split("_")[2])
        service = await session.get(Service, s_id)
        if service:
            await callback.message.edit_text(
                f"Tahrirlash: {service.name}\nNarx: {service.price}\nDavomiylik: {service.duration_min}daq\nBufer: {service.buffer_min}daq",
                reply_markup=admin_service_edit_kb(service.id, service.is_active)
            )
        else:
            await callback.answer("Xizmat topilmadi")
    except (ValueError, IndexError):
        await callback.answer("Xato callback ma'lumoti")

# --- SERVICE EDITING (SUB-FIELDS) ---
@router.callback_query(F.data.startswith("srv_edprc_"))
async def admin_srv_edit_price_start(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    try:
        s_id = int(callback.data.split("_")[2])
        await state.update_data(edit_service_id=s_id)
        await state.set_state(AdminState.edit_service_price)
        await callback.message.answer("Yangi narxni kiriting:")
    except:
        await callback.answer("Xato")

@router.message(AdminState.edit_service_price)
async def admin_srv_edit_price_finish(message: Message, state: FSMContext, session: AsyncSession):
    try:
        price = float(message.text)
        data = await state.get_data()
        s_id = data['edit_service_id']
        await update_service(session, s_id, price=price)
        await message.answer(f"✅ Narx {price}ga o'zgartirildi.")
        await state.clear()
        
        service = await session.get(Service, s_id)
        await message.answer(
            f"Tahrirlash: {service.name}\nNarx: {service.price}\nDavomiylik: {service.duration_min}daq",
            reply_markup=admin_service_edit_kb(service.id, service.is_active)
        )
    except ValueError:
        await message.answer("Noto'g'ri narx. Raqam kiriting.")

@router.callback_query(F.data.startswith("srv_eddur_"))
async def admin_srv_edit_dur_start(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    try:
        s_id = int(callback.data.split("_")[2])
        await state.update_data(edit_service_id=s_id)
        await state.set_state(AdminState.edit_service_duration)
        await callback.message.answer("Yangi davomiylikni kiriting (daqiqa):")
    except:
        await callback.answer("Xato")

@router.message(AdminState.edit_service_duration)
async def admin_srv_edit_dur_finish(message: Message, state: FSMContext, session: AsyncSession):
    try:
        duration = int(message.text)
        data = await state.get_data()
        s_id = data['edit_service_id']
        await update_service(session, s_id, duration_min=duration)
        await message.answer(f"✅ Davomiylik {duration} daqiqaga o'zgartirildi.")
        await state.clear()
        
        service = await session.get(Service, s_id)
        await message.answer(
            f"Tahrirlash: {service.name}\nNarx: {service.price}\nDavomiylik: {service.duration_min}daq",
            reply_markup=admin_service_edit_kb(service.id, service.is_active)
        )
    except ValueError:
        await message.answer("Noto'g'ri raqam. Butun son kiriting.")

@router.callback_query(F.data.startswith("srv_edbuf_"))
async def admin_srv_edit_buf_start(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    try:
        s_id = int(callback.data.split("_")[2])
        await state.update_data(edit_service_id=s_id)
        await state.set_state(AdminState.edit_service_buffer)
        await callback.message.answer("Yangi bufer vaqtini kiriting (daqiqa):")
    except:
        await callback.answer("Xato")

@router.message(AdminState.edit_service_buffer)
async def admin_srv_edit_buf_finish(message: Message, state: FSMContext, session: AsyncSession):
    try:
        buffer = int(message.text)
        data = await state.get_data()
        s_id = data['edit_service_id']
        await update_service(session, s_id, buffer_min=buffer)
        await message.answer(f"✅ Bufer vaqti {buffer} daqiqaga o'zgartirildi.")
        await state.clear()
        
        service = await session.get(Service, s_id)
        await message.answer(
            f"Tahrirlash: {service.name}\nNarx: {service.price}\nDavomiylik: {service.duration_min}daq",
            reply_markup=admin_service_edit_kb(service.id, service.is_active)
        )
    except ValueError:
        await message.answer("Noto'g'ri raqam. Butun son kiriting.")

@router.callback_query(F.data.startswith("srv_toggle_"))
async def admin_srv_toggle(callback: CallbackQuery, session: AsyncSession):
    user = await ensure_admin_user(callback.from_user.id, session)
    if not can_access_admin_panel(user): 
        await callback.answer("Kirish rad etildi", show_alert=True)
        return
    try:
        s_id = int(callback.data.split("_")[2])
        await toggle_service_active(session, s_id)
        service = await session.get(Service, s_id)
        await callback.message.edit_text(
            f"Tahrirlash: {service.name}\nNarx: {service.price}\nDavomiylik: {service.duration_min}daq",
            reply_markup=admin_service_edit_kb(service.id, service.is_active)
        )
    except:
        await callback.answer("Xato")

@router.callback_query(F.data.startswith("srv_del_"))
async def admin_srv_del(callback: CallbackQuery, session: AsyncSession):
    user = await ensure_admin_user(callback.from_user.id, session)
    if not can_access_admin_panel(user): 
        await callback.answer("Kirish rad etildi", show_alert=True)
        return
    try:
        s_id = int(callback.data.split("_")[2])
        await delete_service(session, s_id)
        await callback.message.edit_text("Xizmat o'chirildi.")
        services = await get_all_services(session)
        await callback.message.answer("Xizmatlarni boshqarish:", reply_markup=admin_services_kb(services))
    except:
        await callback.answer("Xato")

@router.callback_query(F.data == "srv_back")
async def admin_srv_back(callback: CallbackQuery, session: AsyncSession):
    user = await ensure_admin_user(callback.from_user.id, session)
    if not can_access_admin_panel(user): return
    services = await get_all_services(session)
    await callback.message.edit_text("Xizmatlarni boshqarish:", reply_markup=admin_services_kb(services))

# --- SCHEDULE ---
@router.message(F.text == "⏰ Jadval")
async def admin_schedule(message: Message, session: AsyncSession):
    user = await ensure_admin_user(message.from_user.id, session)
    if not can_access_admin_panel(user): return
    days = await get_work_schedule(session)
    # Ensure default schedule exists is handled inside the template logic or implicitly if empty
    await message.answer("Jadval (Yashil=Ochiq, Qizil=Yopiq):", reply_markup=admin_schedule_kb(days))

@router.callback_query(F.data.startswith("adm_sch_edit_"))
async def admin_sch_std_toggle(callback: CallbackQuery, session: AsyncSession):
    user = await ensure_admin_user(callback.from_user.id, session)
    if not can_access_admin_panel(user): 
        await callback.answer("Kirish rad etildi", show_alert=True)
        return
        
    weekday = int(callback.data.split("_")[3])
    query = select(WorkSchedule).where(WorkSchedule.weekday == weekday)
    res = await session.execute(query)
    day = res.scalar_one_or_none()
    
    is_off = not day.is_day_off if day else False # Toggle state
    # Requirement: Fix day IS NONE case (defaults 09-18)
    cur_start = day.start_time if day else time(9, 0)
    cur_end = day.end_time if day else time(18, 0)
    
    await update_work_schedule_day(session, weekday, is_off, cur_start, cur_end)
    
    days = await get_work_schedule(session)
    await callback.message.edit_reply_markup(reply_markup=admin_schedule_kb(days))

# --- ADMINS MANAGEMENT (SUPERADMIN ONLY) ---
@router.message(F.text == "👥 Adminlar")
async def admin_list_admins_cmd(message: Message, session: AsyncSession):
    user = await ensure_admin_user(message.from_user.id, session)
    if not can_manage_admins(user): return
    admins = await get_admins(session)
    await message.answer("Adminlarni boshqarish:", reply_markup=admins_list_kb(admins))

@router.callback_query(F.data == "adm_add")
async def adm_add_start(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    user = await ensure_admin_user(callback.from_user.id, session)
    if not can_manage_admins(user): 
        await callback.answer("Kirish rad etildi", show_alert=True)
        return
    await state.set_state(AdminState.add_admin_id)
    await callback.message.answer("Foydalanuvchi xabarini ulashing yoki Telegram ID raqamini yuboring:")

@router.message(AdminState.add_admin_id)
async def adm_add_id(message: Message, state: FSMContext, session: AsyncSession):
    user = await ensure_admin_user(message.from_user.id, session)
    if not can_manage_admins(user): return
    uid = None
    if message.forward_from:
        uid = message.forward_from.id
    elif message.text.isdigit():
        uid = int(message.text)
    if not uid:
        await message.answer("Noto'g'ri kiritilgan. Xabarni ulashing yoki raqamli ID yuboring.")
        return
    await state.update_data(new_admin_id=uid)
    await state.set_state(AdminState.select_admin_role)
    await message.answer(f"{uid} ID uchun admin o'rnatilmoqda. Rol tanlang:", reply_markup=admin_role_kb())

@router.callback_query(AdminState.select_admin_role, F.data.startswith("role_"))
async def adm_set_role(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    user = await ensure_admin_user(callback.from_user.id, session)
    if not can_manage_admins(user): 
        await callback.answer("Kirish rad etildi", show_alert=True)
        return
    role = callback.data.split("_")[1]
    data = await state.get_data()
    uid = data['new_admin_id']
    await set_admin_role(session, uid, role)
    await callback.message.answer(f"✅ {uid} foydalanuvchi {role} admin sifatida o'rnatildi.")
    await state.clear()

@router.callback_query(F.data.startswith("adm_manage_"))
async def adm_manage(callback: CallbackQuery, session: AsyncSession):
    user = await ensure_admin_user(callback.from_user.id, session)
    if not can_manage_admins(user): 
        await callback.answer("Kirish rad etildi", show_alert=True)
        return
    aid = int(callback.data.split("_")[2])
    admin_user = await session.get(User, aid)
    if admin_user:
        await callback.message.edit_text(
            f"Admin Profili: {admin_user.first_name}\nRol: {admin_user.admin_type or 'Superadmin'}", 
            reply_markup=manage_admin_kb(aid)
        )
    else:
        await callback.answer("Foydalanuvchi topilmadi.")

@router.callback_query(F.data.startswith("adm_revoke_"))
async def adm_revoke(callback: CallbackQuery, session: AsyncSession):
    user = await ensure_admin_user(callback.from_user.id, session)
    if not can_manage_admins(user): 
        await callback.answer("Kirish rad etildi", show_alert=True)
        return
    aid = int(callback.data.split("_")[2])
    admin_user = await session.get(User, aid)
    if admin_user:
        await set_admin_role(session, admin_user.telegram_user_id, None)
        await callback.message.edit_text(f"❌ {admin_user.first_name} admin huquqi bekor qilindi.")
        
        # Sobiq adminga xabar yuborish va klaviaturani mijoznikiga o'zgartirish
        try:
            from bot.keyboards.client import main_menu_kb
            await callback.bot.send_message(
                admin_user.telegram_user_id, 
                "⚠️ Sizning adminlik huquqingiz bekor qilindi.",
                reply_markup=main_menu_kb()
            )
        except:
            pass
    else:
        await callback.answer("Foydalanuvchi topilmadi.")
    
@router.callback_query(F.data == "back_admins")
async def back_admins(callback: CallbackQuery, session: AsyncSession):
    user = await ensure_admin_user(callback.from_user.id, session)
    if not can_manage_admins(user): return
    admins = await get_admins(session)
    await callback.message.edit_text("Adminlarni boshqarish:", reply_markup=admins_list_kb(admins))

# --- SETTINGS ---
@router.message(F.text == "⚙️ Sozlamalar")
async def admin_settings(message: Message, session: AsyncSession):
    user = await ensure_admin_user(message.from_user.id, session)
    if not can_access_admin_panel(user): return
    
    dep_enabled = (await get_setting(session, "deposit_enabled", "false")) == "true"
    card_num = await get_setting(session, "card_number", "Kiritilmagan")
    channel = await get_setting(session, "portfolio_channel_id", "Kiritilmagan")
    
    msg = (
        f"⚙️ **Sozlamalar**\n\n"
        f"💳 Karta: `{card_num}`\n"
        f"💰 Depozit (10%): {'Yoqilgan ✅' if dep_enabled else 'Ochirilgan ❌'}\n"
        f"📸 Kanal: `{channel}`"
    )
    await message.answer(msg, reply_markup=admin_settings_kb(dep_enabled), parse_mode="Markdown")

@router.callback_query(F.data == "set_card_number")
async def admin_set_card_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AdminState.edit_card_number)
    await callback.message.answer("Karta raqamini kiriting (masalan: 8600...):")
    await callback.answer()

@router.message(AdminState.edit_card_number)
async def admin_set_card_finish(message: Message, state: FSMContext, session: AsyncSession):
    await set_setting(session, "card_number", message.text)
    await message.answer(f"✅ Karta raqami saqlandi: `{message.text}`", parse_mode="Markdown")
    await state.clear()
    await admin_settings(message, session)

@router.callback_query(F.data == "toggle_deposit")
async def admin_toggle_deposit(callback: CallbackQuery, session: AsyncSession):
    current = (await get_setting(session, "deposit_enabled", "false")) == "true"
    new_val = "false" if current else "true"
    await set_setting(session, "deposit_enabled", new_val)
    
    await callback.answer(f"Depozit {'yoqildi' if new_val == 'true' else 'ochirildi'}")
    # Refresh settings view
    dep_enabled = new_val == "true"
    card_num = await get_setting(session, "card_number", "Kiritilmagan")
    channel = await get_setting(session, "portfolio_channel_id", "Kiritilmagan")
    
    msg = (
        f"⚙️ **Sozlamalar**\n\n"
        f"💳 Karta: `{card_num}`\n"
        f"💰 Depozit (10%): {'Yoqilgan ✅' if dep_enabled else 'Ochirilgan ❌'}\n"
        f"📸 Kanal: `{channel}`"
    )
    await callback.message.edit_text(msg, reply_markup=admin_settings_kb(dep_enabled), parse_mode="Markdown")

@router.callback_query(F.data == "set_portfolio_channel")
async def admin_set_portfolio_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AdminState.edit_portfolio_channel)
    await callback.message.answer("Portfolio kanali ID sini yoki xabarni ulashing (Forward):\nMasalan: -100123456789")
    await callback.answer()

@router.message(AdminState.edit_portfolio_channel)
async def admin_set_portfolio_finish(message: Message, state: FSMContext, session: AsyncSession):
    channel_id = None
    if message.forward_from_chat:
        channel_id = str(message.forward_from_chat.id)
    else:
        channel_id = message.text
        
    await set_setting(session, "portfolio_channel_id", channel_id)
    await message.answer(f"✅ Portfolio kanali saqlandi: `{channel_id}`", parse_mode="Markdown")
    await state.clear()
    await admin_settings(message, session)

@router.callback_query(F.data == "set_portfolio_link")
async def admin_set_portfolio_link_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AdminState.edit_portfolio_link)
    await callback.message.answer("Portfolio kanali ommaviy linkini kiriting (masalan: https://t.me/kanal_nomi):")
    await callback.answer()

@router.message(AdminState.edit_portfolio_link)
async def admin_set_portfolio_link_finish(message: Message, state: FSMContext, session: AsyncSession):
    link = message.text
    if not link.startswith("http"):
        link = f"https://t.me/{link.replace('@', '')}"
        
    await set_setting(session, "portfolio_channel_link", link)
    await message.answer(f"✅ Portfolio linki saqlandi: `{link}`", parse_mode="Markdown")
    await state.clear()
    await admin_settings(message, session)

# --- STATISTICS ---
@router.message(F.text == "📊 Statistika")
async def admin_statistics(message: Message, session: AsyncSession):
    user = await ensure_admin_user(message.from_user.id, session)
    if not can_manage_admins(user): return # Superadmin only per requirement
    
    from sqlalchemy import func
    # Tasdiqlangan bookinglar bo'yicha tushum
    total_revenue_stmt = select(func.sum(Appointment.payment_amount)).where(Appointment.is_paid == True)
    total_revenue = (await session.execute(total_revenue_stmt)).scalar() or 0
    
    total_bookings_stmt = select(func.count(Appointment.id))
    total_bookings = (await session.execute(total_bookings_stmt)).scalar() or 0
    
    confirmed_bookings_stmt = select(func.count(Appointment.id)).where(Appointment.status == AppointmentStatus.CONFIRMED.value)
    confirmed_bookings = (await session.execute(confirmed_bookings_stmt)).scalar() or 0
    
    msg = (
        f"📊 **Statistika**\n\n"
        f"💰 Umumiy tushum (Depozitlar): {total_revenue:,.0f} so'm\n"
        f"📝 Jami buyurtmalar: {total_bookings}\n"
        f"✅ Tasdiqlanganlar: {confirmed_bookings}"
    )
    await message.answer(msg, parse_mode="Markdown")

@router.callback_query(F.data == "adm_main_menu")
async def admin_main_menu_cb(callback: CallbackQuery, session: AsyncSession):
    user = await ensure_admin_user(callback.from_user.id, session)
    if not can_access_admin_panel(user): return
    await callback.message.delete()
    await callback.message.answer("Boshqaruv Paneli", reply_markup=admin_menu_kb(user.is_superadmin))

# --- INFO EDITING ---
@router.callback_query(F.data == "edit_shop_info")
async def admin_edit_info_menu(callback: CallbackQuery, session: AsyncSession):
    user = await ensure_admin_user(callback.from_user.id, session)
    if not can_access_admin_panel(user): return
    await callback.message.edit_text("Qaysi ma'lumotni o'zgartirmoqchisiz?", reply_markup=edit_info_kb())

@router.callback_query(F.data.startswith("set_inf_"))
async def admin_set_info_start(callback: CallbackQuery, state: FSMContext):
    field = callback.data.split("_")[2]
    states = {
        "name": (AdminState.edit_barber_name, "Sartarosh ismini kiriting:"),
        "phone": (AdminState.edit_barber_phone, "Telefon raqamini kiriting:"),
        "addr": (AdminState.edit_barber_address, "Manzil nomini kiriting:"),
        "loc": (AdminState.edit_barber_location, "Lokatsiya linkini (Google/Yandex maps) yuboring:")
    }
    st, msg = states[field]
    await state.set_state(st)
    await callback.message.answer(msg)
    await callback.answer()

@router.message(AdminState.edit_barber_name)
async def admin_save_barber_name(message: Message, state: FSMContext, session: AsyncSession):
    await set_setting(session, "barber_name", message.text)
    await message.answer(f"✅ Ism saqlandi: {message.text}")
    await state.clear()
    await admin_settings(message, session)

@router.message(AdminState.edit_barber_phone)
async def admin_save_barber_phone(message: Message, state: FSMContext, session: AsyncSession):
    await set_setting(session, "barber_phone", message.text)
    await message.answer(f"✅ Telefon saqlandi: {message.text}")
    await state.clear()
    await admin_settings(message, session)

@router.message(AdminState.edit_barber_address)
async def admin_save_barber_address(message: Message, state: FSMContext, session: AsyncSession):
    await set_setting(session, "barber_address", message.text)
    await message.answer(f"✅ Manzil saqlandi: {message.text}")
    await state.clear()
    await admin_settings(message, session)

@router.message(AdminState.edit_barber_location)
async def admin_save_barber_location(message: Message, state: FSMContext, session: AsyncSession):
    loc_val = None
    if message.location:
        # Convert location pin to a Google Maps link
        lat = message.location.latitude
        lon = message.location.longitude
        loc_val = f"https://www.google.com/maps?q={lat},{lon}"
    elif message.text:
        loc_val = message.text
    
    if not loc_val:
        await message.answer("⚠️ Iltimos, lokatsiya linkini yuboring yoki xaritadan joylashuvni tanlab jo'nating.")
        return

    await set_setting(session, "barber_location", loc_val)
    await message.answer(f"✅ Lokatsiya saqlandi: {loc_val}")
    await state.clear()
    await admin_settings(message, session)

# --- MANUAL BOOKING ---
@router.message(F.text == "📝 Manual Band qilish")
async def admin_manual_booking_start(message: Message, session: AsyncSession, state: FSMContext):
    user = await ensure_admin_user(message.from_user.id, session)
    if not can_access_admin_panel(user): return
    
    services = await get_all_services(session)
    if not services:
        await message.answer("Xizmatlar topilmadi.")
        return
    
    await state.set_state(AdminState.manual_booking_service)
    await message.answer("Xizmatni tanlang (Manual):", reply_markup=manual_services_kb(services))

@router.callback_query(AdminState.manual_booking_service, F.data.startswith("man_srv_"))
async def admin_manual_service_selected(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    s_id = int(callback.data.split("_")[2])
    await state.update_data(service_id=s_id)
    await state.set_state(AdminState.manual_booking_date)
    from bot.keyboards.client import dates_kb
    await callback.message.edit_text("Sana tanlang (Manual):", reply_markup=dates_kb())

@router.callback_query(AdminState.manual_booking_date, F.data.startswith("date_"))
async def admin_manual_date_selected(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    date_str = callback.data.split("_")[1]
    data = await state.get_data()
    from services.schedule import get_slots
    from bot.keyboards.client import slots_kb
    slots = await get_slots(session, data['service_id'], datetime.strptime(date_str, "%Y-%m-%d").date())
    
    await state.update_data(selected_date=date_str)
    await state.set_state(AdminState.manual_booking_time)
    await callback.message.edit_text(f"{date_str} uchun vaqt tanlang:", reply_markup=slots_kb(slots, datetime.strptime(date_str, "%Y-%m-%d").date()))

@router.callback_query(AdminState.manual_booking_time, F.data.startswith("time_"))
async def admin_manual_time_selected(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    parts = callback.data.split("_")
    time_str = parts[2]
    data = await state.get_data()
    
    from services.booking import create_booking
    
    d = datetime.strptime(data['selected_date'], "%Y-%m-%d").date()
    t = datetime.strptime(time_str, "%H:%M").time()
    start_dt = datetime.combine(d, t)
    
    admin_u = await ensure_admin_user(callback.from_user.id, session)

    try:
        booking = await create_booking(
            session=session,
            user_id=admin_u.id, 
            service_id=data['service_id'],
            start_time=start_dt,
            customer_phone="Noma'lum",
            customer_name="Offline Mijoz",
            created_by="admin"
        )
        booking.status = AppointmentStatus.CONFIRMED
        await session.commit()
        await callback.message.edit_text(f"✅ Offline booking muvaffaqiyatli saqlandi!\nVaqt: {data['selected_date']} {time_str}\nID: #{booking.id}")
    except Exception as e:
        await callback.message.edit_text(f"❌ Xato: {str(e)}")
    
    await state.clear()
    await callback.message.answer("Boshqaruv Paneli", reply_markup=admin_menu_kb(admin_u.is_superadmin))
