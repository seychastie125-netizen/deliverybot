from config import config
from datetime import datetime
import pytz


def is_admin(user_id: int) -> bool:
    return user_id in config.ADMIN_IDS


def is_manager(user_id: int) -> bool:
    return user_id in config.MANAGER_IDS or user_id in config.ADMIN_IDS


def format_price(price: float) -> str:
    return f"{price:.0f}₽"


async def is_within_work_hours() -> bool:
    from database.db import db
    tz = pytz.timezone(config.TIMEZONE)
    now = datetime.now(tz)
    start_str = await db.get_setting("work_hours_start") or "00:00"
    end_str = await db.get_setting("work_hours_end") or "23:59"
    start_h, start_m = map(int, start_str.split(":"))
    end_h, end_m = map(int, end_str.split(":"))
    start_minutes = start_h * 60 + start_m
    end_minutes = end_h * 60 + end_m
    now_minutes = now.hour * 60 + now.minute
    if start_minutes <= end_minutes:
        return start_minutes <= now_minutes <= end_minutes
    else:
        return now_minutes >= start_minutes or now_minutes <= end_minutes