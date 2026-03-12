"""
Feature H: Аналитика и экспорт
Графики выручки по дням, топ-товары, топ-клиенты, экспорт в CSV.
Авто-отчёт в настраиваемое время через планировщик.
"""
import io
from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, Message, BufferedInputFile
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton

from database.db import db
from filters.role import IsAdmin
from utils.helpers import format_price

router = Router()
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())


def analytics_kb():
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📊 7 дней", callback_data="analytics_7"),
        InlineKeyboardButton(text="📊 30 дней", callback_data="analytics_30"),
    )
    builder.row(
        InlineKeyboardButton(text="🏆 Топ товары", callback_data="analytics_top_products"),
        InlineKeyboardButton(text="👑 Топ клиенты", callback_data="analytics_top_clients"),
    )
    builder.row(
        InlineKeyboardButton(text="📥 Экспорт CSV (30д)", callback_data="analytics_export_30"),
        InlineKeyboardButton(text="📥 Экспорт CSV (7д)", callback_data="analytics_export_7"),
    )
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="adm_back"))
    return builder.as_markup()


@router.callback_query(F.data == "adm_analytics")
async def adm_analytics(callback: CallbackQuery):
    data = await db.get_full_analytics(7)
    total_orders = data["all_time_orders"]
    total_revenue = data["all_time_revenue"]
    text = (
        "📊 <b>Аналитика</b>\n\n"
        f"📦 Всего заказов: <b>{total_orders}</b>\n"
        f"💰 Общая выручка: <b>{format_price(total_revenue)}</b>\n\n"
        "Выберите отчёт:"
    )
    await callback.message.edit_text(text, reply_markup=analytics_kb(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.in_({"analytics_7", "analytics_30"}))
async def analytics_revenue(callback: CallbackQuery):
    days = 7 if callback.data == "analytics_7" else 30
    stats = await db.get_analytics_stats(days)

    if not stats:
        await callback.answer("Нет данных за период", show_alert=True)
        return

    lines = []
    total_rev = 0
    total_ord = 0
    for row in stats:
        lines.append(f"📅 {row['day']}: {row['orders_count']} заказов — {format_price(row['revenue'])}")
        total_rev += row['revenue']
        total_ord += row['orders_count']

    text = (
        f"📈 <b>Выручка за {days} дней</b>\n\n"
        + "\n".join(lines) +
        f"\n\n<b>Итого: {total_ord} заказов | {format_price(total_rev)}</b>"
    )
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="⬅️ К аналитике", callback_data="adm_analytics"))
    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "analytics_top_products")
async def analytics_top_products(callback: CallbackQuery):
    products = await db.get_top_products(10)
    if not products:
        await callback.answer("Нет данных", show_alert=True)
        return
    lines = []
    for i, p in enumerate(products, 1):
        name = p['name'] if 'name' in p.keys() else str(p[0])
        count = p['order_count'] if 'order_count' in p.keys() else str(p[-1])
        lines.append(f"{i}. {name} — {count} раз(а)")

    text = "🏆 <b>Топ-10 товаров по заказам:</b>\n\n" + "\n".join(lines)
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="⬅️ К аналитике", callback_data="adm_analytics"))
    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "analytics_top_clients")
async def analytics_top_clients(callback: CallbackQuery):
    clients = await db.get_top_clients(10)
    if not clients:
        await callback.answer("Нет данных", show_alert=True)
        return
    lines = []
    for i, c in enumerate(clients, 1):
        name = c['full_name'] or f"ID {c['user_id']}"
        username = f" (@{c['username']})" if c['username'] else ""
        lines.append(
            f"{i}. {name}{username}\n"
            f"   📦 {c['total_orders']} заказов | 💰 {format_price(c['total_spent'])}"
        )
    text = "👑 <b>Топ-10 клиентов по выручке:</b>\n\n" + "\n".join(lines)
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="⬅️ К аналитике", callback_data="adm_analytics"))
    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.in_({"analytics_export_30", "analytics_export_7"}))
async def analytics_export(callback: CallbackQuery, bot: Bot):
    days = 30 if "30" in callback.data else 7
    await callback.answer(f"⏳ Генерирую CSV за {days} дней...")
    csv_data = await db.export_orders_csv(days)
    file_bytes = csv_data.encode("utf-8-sig")  # BOM для Excel
    filename = f"orders_{days}days.csv"
    doc = BufferedInputFile(file_bytes, filename=filename)
    await bot.send_document(
        callback.from_user.id,
        document=doc,
        caption=f"📥 Экспорт заказов за последние {days} дней"
    )


async def send_daily_analytics_report(bot: Bot):
    """Авто-отчёт. Вызывается планировщиком."""
    enabled = await db.get_setting("analytics_daily_report")
    if enabled != "1":
        return
    from config import config
    data = await db.get_full_analytics(1)
    stats = data["daily_stats"]
    if not stats:
        return
    today = stats[-1] if stats else None
    if not today:
        return
    text = (
        "📊 <b>Ежедневный отчёт</b>\n\n"
        f"📅 {today['day']}\n"
        f"📦 Заказов: <b>{today['orders_count']}</b>\n"
        f"💰 Выручка: <b>{format_price(today['revenue'])}</b>\n\n"
        f"📦 Всего за всё время: {data['all_time_orders']}\n"
        f"💰 Общая выручка: {format_price(data['all_time_revenue'])}"
    )
    for admin_id in config.ADMIN_IDS:
        try:
            await bot.send_message(admin_id, text, parse_mode="HTML")
        except Exception:
            pass
