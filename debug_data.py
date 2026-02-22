
import asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from db.models import Service, Appointment, AppointmentStatus
import os
from datetime import datetime

DATABASE_URL = "postgresql+asyncpg://postgres:postgrespw@db:5432/barberbot"

async def analyze():
    engine = create_async_engine(DATABASE_URL)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        # Get services
        svc_res = await session.execute(select(Service))
        services = svc_res.scalars().all()
        print("\n--- SERVICES ---")
        for s in services:
            print(f"ID: {s.id} | Name: {s.name} | Duration: {s.duration_min} + Buffer: {s.buffer_min} = {s.duration_min + s.buffer_min} min")

        # Get active appointments
        app_res = await session.execute(
            select(Appointment).where(
                Appointment.status.in_([
                    AppointmentStatus.PENDING, 
                    AppointmentStatus.CONFIRMED, 
                    AppointmentStatus.COMPLETED
                ])
            ).order_by(Appointment.starts_at)
        )
        apps = app_res.scalars().all()
        print("\n--- ACTIVE APPOINTMENTS ---")
        for a in apps:
            print(f"ID: {a.id} | Starts: {a.starts_at} | Ends: {a.ends_at} | Status: {a.status} | Service_ID: {a.service_id}")

if __name__ == "__main__":
    asyncio.run(analyze())
