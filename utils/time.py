
# utils/time.py
from datetime import datetime, time, date, timedelta
import pytz
from core.config import settings

TZ = pytz.timezone(settings.timezone_name)

def now() -> datetime:
    return datetime.now(TZ)

def to_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return TZ.localize(dt).astimezone(pytz.UTC)
    return dt.astimezone(pytz.UTC)

def from_utc(dt: datetime) -> datetime:
    return dt.astimezone(TZ)

def get_today() -> date:
    return now().date()

def combine_date_time(d: date, t: time) -> datetime:
    return TZ.localize(datetime.combine(d, t))

# Uzbek weekday names, 0=Monday
UZ_WEEKDAYS = [
    "Dushanba",
    "Seshanba",
    "Chorshanba",
    "Payshanba",
    "Juma",
    "Shanba",
    "Yakshanba"
]

def format_date_uz(dt: date) -> str:
    """
    (hafta nomi)/kun/oy/yil formatda o'zbek tilida qaytaradi.
    dt: datetime.date yoki datetime.datetime
    """
    weekday = UZ_WEEKDAYS[dt.weekday()]
    return f"{weekday}/{dt.day:02}/{dt.month:02}/{dt.year}"
