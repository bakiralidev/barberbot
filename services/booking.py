
# services/booking.py
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from db.models import Appointment, AppointmentStatus, User, Service
from utils.time import to_utc

class SlotOccupiedError(Exception):
    pass

async def create_booking(
    session: AsyncSession,
    user_id: int,
    service_id: int,
    start_time: datetime,
    customer_phone: str,
    customer_name: str,
    created_by: str = "client"
) -> Appointment:
    service = await session.get(Service, service_id)
    if not service:
        raise ValueError("Service not found")
    
    start_utc = to_utc(start_time)
    duration = service.duration_min + service.buffer_min
    end_utc = start_utc + timedelta(minutes=duration)

    appointment = Appointment(
        user_id=user_id,
        service_id=service_id,
        status=AppointmentStatus.PENDING,
        starts_at=start_utc,
        ends_at=end_utc,
        customer_phone=customer_phone,
        customer_name=customer_name,
        created_by=created_by
    )
    
    session.add(appointment)
    try:
        await session.commit()
        await session.refresh(appointment)
        return appointment
    except IntegrityError as e:
        await session.rollback()
        if "no_overlap" in str(e):
            raise SlotOccupiedError("This slot is already taken.")
        raise e

async def get_user_bookings(session: AsyncSession, user_id: int):
    query = select(Appointment).options(selectinload(Appointment.service)).where(
        Appointment.user_id == user_id,
        Appointment.status.in_([AppointmentStatus.PENDING, AppointmentStatus.CONFIRMED])
    ).order_by(Appointment.starts_at)
    res = await session.execute(query)
    return res.scalars().all()

async def cancel_booking(session: AsyncSession, booking_id: int):
    appointment = await session.get(Appointment, booking_id)
    if appointment:
        appointment.status = AppointmentStatus.CANCELLED
        await session.commit()
    return appointment

async def reschedule_booking(
    session: AsyncSession, 
    booking_id: int, 
    new_start_time: datetime
) -> Appointment:
    appointment = await session.get(Appointment, booking_id)
    if not appointment:
        raise ValueError("Booking not found")

    service = await session.get(Service, appointment.service_id)
    duration = service.duration_min + service.buffer_min
    
    new_start_utc = to_utc(new_start_time)
    new_end_utc = new_start_utc + timedelta(minutes=duration)
    
    appointment.starts_at = new_start_utc
    appointment.ends_at = new_end_utc

    try:
        await session.commit()
        await session.refresh(appointment)
        return appointment
    except IntegrityError as e:
        await session.rollback()
        if "no_overlap" in str(e):
            raise SlotOccupiedError("This slot is already taken.")
        raise e
