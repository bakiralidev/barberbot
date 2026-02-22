# bot/states.py
from aiogram.fsm.state import State, StatesGroup

class BookingState(StatesGroup):
    selecting_service = State()
    selecting_date = State()
    selecting_time = State()
    confirming = State()
    paying = State()
    rescheduling_date = State()
    rescheduling_time = State()

class AdminState(StatesGroup):
    menu = State()
    add_service_name = State()
    add_service_price = State()
    add_service_duration = State()
    edit_service_price = State()
    edit_service_duration = State()
    edit_service_buffer = State()
    edit_schedule_start = State()
    edit_schedule_end = State()
    
    # Admin Management
    add_admin_id = State()
    select_admin_role = State()
    
    # Booking Management
    reschedule_date = State()
    reschedule_time = State()
    
    # Settings Management
    edit_card_number = State()
    edit_portfolio_channel = State()
    edit_portfolio_link = State()
    edit_deposit_val = State() 
    
    # Barber Info Management
    edit_barber_name = State()
    edit_barber_phone = State()
    edit_barber_address = State()
    edit_barber_location = State()
    adding_portfolio = State()

    # Manual Booking Flow (Admin)
    manual_booking_service = State()
    manual_booking_date = State()
    manual_booking_time = State()
    manual_booking_name = State()
    manual_booking_phone = State()
