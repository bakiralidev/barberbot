
# services/admin.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, or_
from db.models import Service, WorkSchedule, User
from datetime import time

async def get_all_services(session: AsyncSession):
    query = select(Service).order_by(Service.sort_order)
    res = await session.execute(query)
    return res.scalars().all()

async def get_service(session: AsyncSession, service_id: int):
    return await session.get(Service, service_id)

async def create_service(session: AsyncSession, name: str, price: float, duration: int):
    service = Service(
        name=name, 
        price=price, 
        duration_min=duration,
        buffer_min=0,
        is_active=True,
        sort_order=0
    )
    session.add(service)
    await session.commit()
    await session.refresh(service)
    return service

async def update_service(session: AsyncSession, service_id: int, **kwargs):
    stmt = update(Service).where(Service.id == service_id).values(**kwargs)
    await session.execute(stmt)
    await session.commit()

async def delete_service(session: AsyncSession, service_id: int):
    stmt = delete(Service).where(Service.id == service_id)
    await session.execute(stmt)
    await session.commit()

async def toggle_service_active(session: AsyncSession, service_id: int):
    service = await session.get(Service, service_id)
    if service:
        service.is_active = not service.is_active
        await session.commit()
    return service

async def get_work_schedule(session: AsyncSession):
    query = select(WorkSchedule).order_by(WorkSchedule.weekday)
    res = await session.execute(query)
    return res.scalars().all()

async def update_work_schedule_day(session: AsyncSession, weekday: int, is_day_off: bool, start: time, end: time):
    query = select(WorkSchedule).where(WorkSchedule.weekday == weekday)
    res = await session.execute(query)
    day = res.scalar_one_or_none()
    
    if day:
        day.is_day_off = is_day_off
        day.start_time = start
        day.end_time = end
    else:
        day = WorkSchedule(weekday=weekday, is_day_off=is_day_off, start_time=start, end_time=end)
        session.add(day)
    
    await session.commit()

# --- User Management ---
async def get_admins(session: AsyncSession):
    # Requirement: include superadmins in the list
    query = select(User).where(or_(User.is_superadmin == True, User.admin_type.is_not(None)))
    res = await session.execute(query)
    return res.scalars().all()

async def ensure_user(session: AsyncSession, telegram_id: int, first_name: str=None, username: str=None):
    query = select(User).where(User.telegram_user_id == telegram_id)
    user = (await session.execute(query)).scalar_one_or_none()
    if not user:
        user = User(telegram_user_id=telegram_id, first_name=first_name, username=username)
        session.add(user)
        await session.commit()
        await session.refresh(user) # Refresh added per requirement
    return user

async def set_admin_role(session: AsyncSession, telegram_id: int, role: str): 
    # Role validation added
    if role not in ('full', 'limited', None):
        raise ValueError(f"Invalid admin role: {role}")
        
    user = await ensure_user(session, telegram_id)
    user.admin_type = role
    await session.commit()
    return user

async def get_setting(session: AsyncSession, key: str, default: str = None):
    from db.models import Settings
    setting = await session.get(Settings, key)
    return setting.value if setting else default

async def set_setting(session: AsyncSession, key: str, value: str):
    from db.models import Settings
    setting = await session.get(Settings, key)
    if setting:
        setting.value = value
    else:
        setting = Settings(key=key, value=value)
        session.add(setting)
    await session.commit()
