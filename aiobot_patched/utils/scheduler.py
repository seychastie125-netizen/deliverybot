import logging
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import pytz

from config import config
from database.db import db

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler(timezone=config.TIMEZONE)


async def check_pickup_reminders(bot: Bot):
    try:
        orders = await db.get_pending_pickup_orders()
        if not orders:
            return
        tz = pytz.timezone(config.TIMEZONE)
        now = datetime.now(tz)
        reminder_minutes = int(await db.get_setting("pickup_reminder_minutes") or 15)

        for order in orders:
            pickup_time_str = order['pickup_time']
            if not pickup_time_str:
                continue
            try:
                pickup_h, pickup_m = map(int, pickup_time_str.split(":"))
                created_str = order['created_at']
                if isinstance(created_str, str):
                    created_dt = datetime.fromisoformat(created_str)
                else:
                    created_dt = created_str

                pickup_dt = created_dt.replace(
                    hour=pickup_h, minute=pickup_m, second=0, microsecond=0
                )
                if pickup_dt < created_dt:
                    pickup_dt += timedelta(days=1)

                now_naive = now.replace(tzinfo=None)
                pickup_naive = pickup_dt.replace(tzinfo=None) if pickup_dt.tzinfo else pickup_dt
                minutes_until = (pickup_naive - now_naive).total_seconds() / 60

                if 0 <= minutes_until <= reminder_minutes:
                    await _send_reminder(bot, order, pickup_time_str, int(minutes_until))
                    await db.mark_pickup_reminded(order['id'])
                    logger.info(f"Reminder sent: order #{order['id']} in {int(minutes_until)}m")
                elif minutes_until < 0:
                    await db.mark_pickup_reminded(order['id'])
            except Exception as e:
                logger.error(f"Reminder error order #{order['id']}: {e}")
    except Exception as e:
        logger.error(f"check_pickup_reminders error: {e}")


async def _send_reminder(bot: Bot, order, pickup_time: str, minutes_left: int):
    payment_labels = {"cash": "💵 Наличными", "card": "💳 Картой"}
    payment = payment_labels.get(order['payment_method'], order['payment_method'] or '')

    text = (
        f"⏰🔔 <b>НАПОМИНАНИЕ О САМОВЫВОЗЕ</b>\n\n"
        f"📦 Заказ <b>#{order['id']}</b>\n"
        f"👤 {order['user_fullname']}\n"
        f"📱 {order['user_phone'] or order['phone']}\n"
        f"🕐 Время: <b>{pickup_time}</b>\n"
        f"⏳ Осталось: <b>~{minutes_left} мин</b>\n"
        f"💰 Сумма: {order['total_price']:.0f}₽\n"
        f"💳 Оплата: {payment}\n"
    )
    if order['comment']:
        text += f"💬 {order['comment']}\n"
    text += "\n⚠️ <b>Подготовьте заказ к выдаче!</b>"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="✅ Готов к выдаче",
            callback_data=f"mgr_ready_pickup_{order['id']}"
        )]
    ])
    for mid in config.MANAGER_IDS + config.ADMIN_IDS:
        try:
            await bot.send_message(mid, text, reply_markup=kb, parse_mode="HTML")
        except Exception as e:
            logger.error(f"Reminder to {mid}: {e}")


def setup_scheduler(bot: Bot):
    scheduler.add_job(
        check_pickup_reminders,
        trigger=IntervalTrigger(minutes=1),
        args=[bot],
        id="pickup_reminder",
        replace_existing=True,
        max_instances=1
    )

    # Feature H: ежедневный отчёт аналитики
    from apscheduler.triggers.cron import CronTrigger
    from handlers.analytics import send_daily_analytics_report
    scheduler.add_job(
        send_daily_analytics_report,
        trigger=CronTrigger(hour=23, minute=0, timezone=config.TIMEZONE),
        args=[bot],
        id="daily_analytics",
        replace_existing=True,
        max_instances=1
    )

    scheduler.start()
    logger.info("Scheduler started")


def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")