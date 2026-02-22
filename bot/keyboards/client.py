
# bot/keyboards/client.py
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, KeyboardButton, ReplyKeyboardMarkup
from datetime import date, timedelta
from utils.time import get_today

def main_menu_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="✂️ Band qilish")],
            [KeyboardButton(text="📅 Mening buyurtmalarim")],
            [KeyboardButton(text="📸 Portfolio"), KeyboardButton(text="ℹ️ Ma'lumot")]
        ],
        resize_keyboard=True
    )

def services_kb(services) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for s in services:
        builder.button(text=f"{s.name} - {s.price}", callback_data=f"srv_{s.id}")
    builder.adjust(1)
    return builder.as_markup()

def dates_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    today = get_today()
    for i in range(7):
        d = today + timedelta(days=i)
        builder.button(text=d.strftime("%Y-%m-%d (%a)"), callback_data=f"date_{d.isoformat()}")
    builder.adjust(2)
    builder.row(InlineKeyboardButton(text="⬅️ Orqaga", callback_data="back_main"))
    return builder.as_markup()

def slots_kb(slots, date_obj: date) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    date_str = date_obj.isoformat()
    for s in slots:
        slot_time = s['time']
        display_text = slot_time.strftime("%H:%M")
        
        if s['available']:
            callback_data = f"time_{date_str}_{display_text}"
        else:
            display_text += " ❌"
            callback_data = f"taken_{date_str}_{display_text}" # For alert handling
            
        builder.button(text=display_text, callback_data=callback_data)
    builder.adjust(4)
    builder.row(InlineKeyboardButton(text="⬅️ Orqaga", callback_data="back_date"))
    return builder.as_markup()

def confirm_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Bookingni tasdiqlash", callback_data="confirm_booking")
    builder.button(text="❌ Bekor qilish", callback_data="back_main")
    builder.adjust(1)
    return builder.as_markup()

def phone_req_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📱 Telefon raqamini ulashing", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True
    )
