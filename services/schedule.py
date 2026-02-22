# services/schedule.py
from datetime import date, datetime, timedelta, time
from typing import List, Optional
from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from db.models import WorkSchedule, Appointment, AppointmentStatus, Service
from utils.time import combine_date_time, get_today, now, to_utc, from_utc

SLOT_STEP_MINUTES = 15

async def get_slots(session: AsyncSession, service_id: int, target_date: date) -> List[dict]:
    """Returns a list of slots with their availability: [{'time': datetime, 'available': bool}]"""
    service = await session.get(Service, service_id)
    if not service or not service.is_active:
        return []
    
    total_duration = service.duration_min + service.buffer_min

    weekday = target_date.weekday()
    query = select(WorkSchedule).where(WorkSchedule.weekday == weekday)
    schedule_res = await session.execute(query)
    schedule = schedule_res.scalar_one_or_none()

    if not schedule or schedule.is_day_off:
        return []

    slots: List[datetime] = []
    
    start_dt = combine_date_time(target_date, schedule.start_time)
    end_dt = combine_date_time(target_date, schedule.end_time)
    
    current_time = now()
    if target_date == current_time.date():
        if start_dt < current_time:
            next_quarter = (current_time.minute // 15 + 1) * 15
            start_dt = current_time.replace(minute=0, second=0, microsecond=0) + timedelta(minutes=next_quarter)

    current_slot = start_dt
    # Jadval qadamini xizmat davomiyligiga qarab belgilaymiz
    step = total_duration
    
    while current_slot + timedelta(minutes=total_duration) <= end_dt:
        in_break = False
        if schedule.break_start and schedule.break_end:
            break_start_dt = combine_date_time(target_date, schedule.break_start)
            break_end_dt = combine_date_time(target_date, schedule.break_end)
            slot_end = current_slot + timedelta(minutes=total_duration)
            if (current_slot < break_end_dt) and (slot_end > break_start_dt):
                in_break = True
        
        if not in_break:
            slots.append(current_slot)
        
        current_slot += timedelta(minutes=step)

    if not slots:
        return []

    day_start_utc = to_utc(combine_date_time(target_date, time(0, 0)))
    day_end_utc = to_utc(combine_date_time(target_date, time(23, 59, 59)))

    # Fetch appointments that overlap the day window
    # Correct overlap logic: App.ends > Window.start AND App.starts < Window.end
    appointments_query = select(Appointment).where(
        and_(
            Appointment.ends_at > day_start_utc,
            Appointment.starts_at < day_end_utc,
            Appointment.status.in_([
                AppointmentStatus.PENDING.value, 
                AppointmentStatus.CONFIRMED.value,
                AppointmentStatus.COMPLETED.value
            ])
        )
    )
    res = await session.execute(appointments_query)
    appointments = res.scalars().all()

    all_slots = []
    for slot in slots:
        slot_end = slot + timedelta(minutes=total_duration)
        slot_utc = to_utc(slot)
        slot_end_utc = to_utc(slot_end)
        
        is_taken = False
        for app in appointments:
            if (slot_utc < app.ends_at) and (slot_end_utc > app.starts_at):
                is_taken = True
                break
        
        all_slots.append({
            "time": slot,
            "available": not is_taken
        })

    return all_slots
