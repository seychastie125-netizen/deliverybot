from aiogram import Bot
from config import config
from database.db import db
from texts.messages import Msg
import json
import logging

logger = logging.getLogger(__name__)


def _payment_text(method: str) -> str:
    return {"cash": "💵 Наличными", "card": "💳 Картой"}.get(method, method)


def _safe_get(row, key, default=None):
    """Безопасное получение значения из sqlite3.Row"""
    try:
        return row[key]
    except (IndexError, KeyError):
        return default


async def notify_managers(bot: Bot, order_id: int):
    order = await db.get_order(order_id)
    if not order:
        return
    items = json.loads(order['items_json'])
    lines = []
    for i in items:
        line = f"  • {i['name']} x{i['quantity']} = {i['sum']:.0f}₽"
        mods = i.get('modifiers', '')
        if mods:
            line += f"\n    <i>({mods})</i>"
        lines.append(line)
    items_text = "\n".join(lines)

    delivery_text = "🚗 Доставка" if order['delivery_type'] == 'delivery' else "🏃 Самовывоз"
    payment_text = _payment_text(order['payment_method'])

    text = (
        f"🆕 <b>Новый заказ #{order['id']}</b>\n\n"
        f"👤 {order['user_fullname']}\n"
        f"📱 {order['phone']}\n"
        f"{delivery_text}\n"
        f"{payment_text}\n"
    )
    if order['delivery_type'] == 'delivery' and order['address']:
        address = order['address']
        # Генерируем ссылку на Яндекс.Карты
        from handlers.geolocation import get_maps_link
        maps_url = await get_maps_link(address)
        text += f"📍 {address}\n"
        text += f'🗺 <a href="{maps_url}">Открыть на Яндекс.Картах</a>\n'

    if order['delivery_type'] == 'pickup' and _safe_get(order, 'pickup_time'):
        text += f"🕐 Время: <b>{order['pickup_time']}</b>\n"
    text += f"\n📋 <b>Состав:</b>\n{items_text}\n"

    # Скидка по акции
    promo_disc = _safe_get(order, 'promotion_discount', 0) or 0
    if promo_disc > 0:
        text += f"\n🔥 Скидка по акции: -{promo_disc:.0f}₽"

    # Промокод
    discount = _safe_get(order, 'discount', 0) or 0
    if discount > 0:
        text += f"\n🏷 Промокод: -{discount:.0f}₽"
        promo_code = _safe_get(order, 'promo_code', '')
        if promo_code:
            text += f" ({promo_code})"

    text += f"\n\n💰 <b>Итого: {order['total_price']:.0f}₽</b>"

    comment = _safe_get(order, 'comment', '')
    if comment:
        text += f"\n\n💬 {comment}"

    from keyboards.manager_kb import manager_order_kb
    kb = manager_order_kb(order['id'], 'new', order['delivery_type'])

    for mid in config.MANAGER_IDS + config.ADMIN_IDS:
        try:
            await bot.send_message(mid, text, reply_markup=kb, parse_mode="HTML",
                                   disable_web_page_preview=True)
        except Exception as e:
            logger.error(f"notify manager {mid}: {e}")


async def notify_client(bot: Bot, user_id: int, text: str):
    try:
        await bot.send_message(user_id, text, parse_mode="HTML")
    except Exception as e:
        logger.error(f"notify client {user_id}: {e}")


async def notify_courier(bot: Bot, courier_id: int, order_id: int):
    order = await db.get_order(order_id)
    if not order:
        return
    payment_text = _payment_text(order['payment_method'])

    address = order['address']
    # Ссылка на карту для курьера
    from handlers.geolocation import get_maps_link
    maps_url = await get_maps_link(address)

    text = (
        f"📦 <b>Вам назначен заказ #{order['id']}</b>\n\n"
        f"📍 Адрес: {address}\n"
        f'🗺 <a href="{maps_url}">Открыть на Яндекс.Картах</a>\n'
        f"📱 Телефон: {order['phone']}\n"
        f"👤 Клиент: {order['user_fullname']}\n"
        f"💰 Сумма: {order['total_price']:.0f}₽\n"
        f"{payment_text}"
    )
    if order['payment_method'] == 'cash':
        text += "\n\n⚠️ <b>Клиент платит наличными!</b>"
    comment = _safe_get(order, 'comment', '')
    if comment:
        text += f"\n💬 {comment}"
    try:
        await bot.send_message(courier_id, text, parse_mode="HTML",
                               disable_web_page_preview=True)
    except Exception as e:
        logger.error(f"notify courier {courier_id}: {e}")