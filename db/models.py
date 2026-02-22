# db/models.py
import enum
from datetime import datetime, time
from typing import Optional
from sqlalchemy import BigInteger, String, Boolean, Integer, Numeric, Time, ForeignKey, DateTime, func, Identity
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import ExcludeConstraint

class Base(DeclarativeBase):
    pass

class AppointmentStatus(str, enum.Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    COMPLETED = "completed"

class User(Base):
    __tablename__ = "users"
    
    id: Mapped[int] = mapped_column(BigInteger, Identity(always=False), primary_key=True)
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    first_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    last_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    username: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    
    # Auth Logic
    is_superadmin: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    admin_type: Mapped[Optional[str]] = mapped_column(String, nullable=True) # 'full', 'limited' or None
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class Service(Base):
    __tablename__ = "services"
    
    id: Mapped[int] = mapped_column(Integer, Identity(always=False), primary_key=True)
    name: Mapped[str] = mapped_column(String)
    duration_min: Mapped[int] = mapped_column(Integer)
    price: Mapped[float] = mapped_column(Numeric(10, 2))
    buffer_min: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class WorkSchedule(Base):
    __tablename__ = "work_schedule"
    
    id: Mapped[int] = mapped_column(Integer, Identity(always=False), primary_key=True)
    weekday: Mapped[int] = mapped_column(Integer, unique=True) # 0=Monday, 6=Sunday
    start_time: Mapped[time] = mapped_column(Time)
    end_time: Mapped[time] = mapped_column(Time)
    break_start: Mapped[Optional[time]] = mapped_column(Time, nullable=True)
    break_end: Mapped[Optional[time]] = mapped_column(Time, nullable=True)
    is_day_off: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

class Appointment(Base):
    __tablename__ = "appointments"
    
    id: Mapped[int] = mapped_column(BigInteger, Identity(always=False), primary_key=True)
    service_id: Mapped[int] = mapped_column(ForeignKey("services.id"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    
    status: Mapped[str] = mapped_column(String, default=AppointmentStatus.PENDING.value, server_default=AppointmentStatus.PENDING.value)
    
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    
    customer_phone: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    customer_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_by: Mapped[str] = mapped_column(String) # client/admin
    
    # Payment fields
    payment_amount: Mapped[Optional[float]] = mapped_column(Numeric(10, 2), nullable=True)
    payment_receipt_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    is_paid: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    payment_confirmed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Reminder fields
    reminder_sent: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    service: Mapped["Service"] = relationship()
    user: Mapped["User"] = relationship()
    
    __table_args__ = (
        ExcludeConstraint(
            (func.tstzrange(starts_at, ends_at, '[)'), '&&'),
            where=(status.in_(('pending', 'confirmed'))),
            name='no_overlap'
        ),
    )

class Settings(Base):
    __tablename__ = "settings"
    key: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[str] = mapped_column(String)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class PortfolioItem(Base):
    __tablename__ = "portfolio_items"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    message_id: Mapped[int] = mapped_column(Integer)
    photo_file_id: Mapped[str] = mapped_column(String)
    caption: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
