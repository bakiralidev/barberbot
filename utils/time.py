
# utils/time.py
from datetime import datetime, time, date, timedelta
import pytz
from core.config import settings

TZ = pytz.timezone(settings.TZ)

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
