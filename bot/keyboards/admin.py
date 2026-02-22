# bot/keyboards/admin.py
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from db.models import AppointmentStatus

def admin_menu_kb(is_superadmin: bool) -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardBuilder()
    kb.button(text="📅 Buyurtmalar")
    kb.button(text="📝 Manual Band qilish")
    kb.button(text="🛠 Xizmatlar")
    kb.button(text="⏰ Jadval")
    kb.button(text="👤 Mijoz paneli")
    kb.button(text="⚙️ Sozlamalar")
    if is_superadmin:
        kb.button(text="👥 Adminlar")
        kb.button(text="📊 Statistika")
    kb.adjust(1, 1, 2, 1, 2)
    return kb.as_markup(resize_keyboard=True)

def admin_booking_action_kb(booking_id: int, status: str = None) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if status == AppointmentStatus.PENDING.value:
        builder.button(text="✅ Tasdiqlash", callback_data=f"adm_confirm_{booking_id}")
    
    if status == AppointmentStatus.CONFIRMED.value:
        builder.button(text="🏁 Tugatildi (Keldi)", callback_data=f"adm_complete_{booking_id}")
        
    builder.button(text="🔄 Ko'chirish", callback_data=f"adm_resched_{booking_id}")
    builder.button(text="❌ Bekor qilish", callback_data=f"adm_cancel_{booking_id}")
    builder.adjust(1)
    return builder.as_markup()
def admin_services_kb(services) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for s in services:
        status = "✅" if s.is_active else "❌"
        builder.button(text=f"{status} {s.name} ({s.price})", callback_data=f"srv_menu_{s.id}")
    builder.button(text="➕ Xizmat qo'shish", callback_data="adm_srv_add")
    builder.adjust(1)
    builder.row(InlineKeyboardButton(text="⬅️ Orqaga", callback_data="adm_main_menu"))
    return builder.as_markup()

def manual_services_kb(services) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for s in services:
        if s.is_active:
            builder.button(text=f"{s.name} ({s.price})", callback_data=f"man_srv_{s.id}")
    builder.adjust(1)
    builder.row(InlineKeyboardButton(text="⬅️ Orqaga", callback_data="adm_main_menu"))
    return builder.as_markup()

def admin_service_edit_kb(service_id: int, is_active: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    toggle_text = "O'chirish" if is_active else "Yoqish"
    builder.button(text=f"🔄 {toggle_text}", callback_data=f"srv_toggle_{service_id}")
    builder.button(text="💰 Narxni o'zgartirish", callback_data=f"srv_edprc_{service_id}")
    builder.button(text="⏱ Davomiylikni o'zgartirish", callback_data=f"srv_eddur_{service_id}")
    builder.button(text="⏳ Buferni o'zgartirish", callback_data=f"srv_edbuf_{service_id}")
    builder.button(text="🗑 O'chirish", callback_data=f"srv_del_{service_id}")
    builder.button(text="⬅️ Orqaga", callback_data="srv_back")
    builder.adjust(1)
    return builder.as_markup()

def admin_schedule_kb(days) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    weekdays = ["Dush", "Sesh", "Chor", "Pay", "Jum", "Shan", "Yak"]
    days_map = {d.weekday: d for d in days}
    
    for i in range(7):
        day = days_map.get(i)
        status = "🔴" if not day or day.is_day_off else "🟢"
        builder.button(text=f"{weekdays[i]} {status}", callback_data=f"adm_sch_edit_{i}")
    
    builder.adjust(2) # Days in pairs
    
    # Append footer buttons as separate rows
    builder.row(InlineKeyboardButton(text="🔄 Yangilash", callback_data="adm_sch_refresh"))
    builder.row(InlineKeyboardButton(text="⬅️ Orqaga", callback_data="adm_main_menu"))
    
    return builder.as_markup()

def admins_list_kb(admins) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for a in admins:
        name = a.first_name or a.username or str(a.telegram_user_id)
        if a.is_superadmin:
            role = "Superadmin"
        else:
            role = a.admin_type.capitalize() if a.admin_type else 'Cheklangan'
        builder.button(text=f"{name} ({role})", callback_data=f"adm_manage_{a.id}")
    builder.button(text="➕ Admin qo'shish", callback_data="adm_add")
    builder.adjust(1)
    return builder.as_markup()

def admin_role_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="To'liq Admin", callback_data="role_full")
    builder.button(text="Cheklangan Admin", callback_data="role_limited")
    return builder.as_markup()

def manage_admin_kb(admin_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="❌ Adminni olib tashlash", callback_data=f"adm_revoke_{admin_id}")
    builder.button(text="⬅️ Orqaga", callback_data="back_admins")
    return builder.as_markup()

def admin_settings_kb(deposit_enabled: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="💳 Karta raqamini o'zgartirish", callback_data="set_card_number")
    
    dep_text = "✅ Depozit (10%): Yoqilgan" if deposit_enabled else "❌ Depozit (10%): O'chirilgan"
    builder.button(text=dep_text, callback_data="toggle_deposit")
    
    builder.button(text="📸 Portfoliya kanali (ID)", callback_data="set_portfolio_channel")
    builder.button(text="🔗 Portfoliya linki (t.me/...)", callback_data="set_portfolio_link")
    builder.button(text="➕ Portfoliyaga rasm qo'shish", callback_data="add_portfolio_works")
    builder.button(text="ℹ️ Ma'lumotlarni tahrirlash", callback_data="edit_shop_info")
    builder.button(text="⬅️ Orqaga", callback_data="adm_main_menu")
    builder.adjust(1)
    return builder.as_markup()

def edit_info_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="👤 Sartarosh ismi", callback_data="set_inf_name")
    builder.button(text="📞 Telefon raqami", callback_data="set_inf_phone")
    builder.button(text="📍 Manzil nomi", callback_data="set_inf_addr")
    builder.button(text="🗺 Lokatsiya (link)", callback_data="set_inf_loc")
    builder.button(text="⬅️ Orqaga", callback_data="toggle_deposit") # Go back to settings
    builder.adjust(1)
    return builder.as_markup()
