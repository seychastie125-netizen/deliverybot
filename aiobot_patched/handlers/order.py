from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from database.db import db
from states.states import OrderStates
from keyboards.client_kb import (
    delivery_type_kb, payment_method_kb, pickup_time_kb,
    phone_kb, confirm_order_kb, skip_kb, main_menu_kb,
    payment_method_text
)
from keyboards.callbacks import DeliveryTypeCB, PaymentCB, PickupTimeCB
from services.order_service import OrderData, create_order, calculate_total, validate_cart
from utils.promocodes import validate_promo, calculate_discount
from utils.notifications import notify_managers
from utils.helpers import format_price, is_within_work_hours
from utils.modifiers import parse_modifiers_price, format_modifiers_inline
from texts.messages import Msg
from config import config
import json
import re

router = Router()


@router.callback_query(F.data == "checkout")
async def checkout_start(callback: CallbackQuery, state: FSMContext):
    valid, error = await validate_cart(callback.from_user.id)
    if not valid:
        await callback.answer(error, show_alert=True)
        return

    if not await is_within_work_hours():
        start = await db.get_setting("work_hours_start") or "09:00"
        end = await db.get_setting("work_hours_end") or "23:00"
        await callback.answer(
            f"⏰ Мы работаем с {start} до {end}", show_alert=True
        )
        return

    # Сохраняем данные промокода если они были введены ранее
    current_data = await state.get_data()
    promo_code = current_data.get('promo_code')
    discount = current_data.get('discount', 0)
    promo_id = current_data.get('promo_id')

    await state.update_data(
        promo_code=promo_code,
        discount=discount,
        promo_id=promo_id,
        pickup_time=None
    )

    await callback.message.edit_text(
        Msg.CHOOSE_DELIVERY, reply_markup=delivery_type_kb(), parse_mode="HTML"
    )
    await state.set_state(OrderStates.choosing_delivery_type)
    await callback.answer()


@router.callback_query(DeliveryTypeCB.filter(), OrderStates.choosing_delivery_type)
async def set_delivery_type(callback: CallbackQuery, callback_data: DeliveryTypeCB,
                            state: FSMContext):
    dt = callback_data.type
    await state.update_data(delivery_type=dt)

    if dt == "pickup":
        ws = await db.get_setting("work_hours_start") or "09:00"
        we = await db.get_setting("work_hours_end") or "23:00"
        step = int(await db.get_setting("pickup_time_step") or 15)
        mw = int(await db.get_setting("pickup_min_wait") or 30)
        pa = await db.get_setting("pickup_address") or "наш адрес"
        kb, has = pickup_time_kb(config.TIMEZONE, ws, we, step, mw)
        if not has:
            await callback.message.edit_text(
                Msg.NO_SLOTS, reply_markup=delivery_type_kb()
            )
            await callback.answer()
            return
        await callback.message.edit_text(
            f"🏃 <b>Самовывоз</b>\n\n📍 {pa}\n\n"
            f"🕐 Выберите время (мин. {mw} мин):",
            reply_markup=kb, parse_mode="HTML"
        )
        await state.set_state(OrderStates.choosing_pickup_time)
    else:
        await callback.message.edit_text(
            Msg.CHOOSE_PAYMENT, reply_markup=payment_method_kb(), parse_mode="HTML"
        )
        await state.set_state(OrderStates.choosing_payment)
    await callback.answer()


@router.callback_query(PickupTimeCB.filter(), OrderStates.choosing_pickup_time)
async def set_pickup_time(callback: CallbackQuery, callback_data: PickupTimeCB,
                          state: FSMContext):
    raw = callback_data.time.replace(":", "")  # strip colon if somehow present
    time_display = f"{raw[:2]}:{raw[2:]}" if len(raw) == 4 else raw
    await state.update_data(pickup_time=time_display, address="Самовывоз")
    await callback.message.edit_text(
        f"✅ Время: <b>{time_display}</b>\n\n{Msg.CHOOSE_PAYMENT}",
        reply_markup=payment_method_kb(), parse_mode="HTML"
    )
    await state.set_state(OrderStates.choosing_payment)
    await callback.answer()


@router.callback_query(PaymentCB.filter(), OrderStates.choosing_payment)
async def set_payment(callback: CallbackQuery, callback_data: PaymentCB,
                      state: FSMContext):
    await state.update_data(payment_method=callback_data.method)
    data = await state.get_data()
    if data['delivery_type'] == 'delivery':
        user = await db.get_user(callback.from_user.id)
        saved = user['address'] if user and user['address'] else None
        text = Msg.ENTER_ADDRESS
        if saved:
            text += f"\n\nПоследний: <i>{saved}</i>"
        await callback.message.edit_text(text, parse_mode="HTML")
        await state.set_state(OrderStates.entering_address)
    else:
        await callback.message.edit_text(Msg.ENTER_PHONE, parse_mode="HTML")
        await callback.message.answer("👇", reply_markup=phone_kb())
        await state.set_state(OrderStates.entering_phone)
    await callback.answer()


@router.message(OrderStates.entering_address)
async def process_address(message: Message, state: FSMContext):
    addr = message.text.strip()
    if len(addr) < 5:
        await message.answer(Msg.ADDRESS_SHORT)
        return
    await state.update_data(address=addr)
    await db.update_user(message.from_user.id, address=addr)
    await message.answer(Msg.ENTER_PHONE, reply_markup=phone_kb())
    await state.set_state(OrderStates.entering_phone)


@router.message(OrderStates.entering_phone, F.contact)
async def process_phone_contact(message: Message, state: FSMContext):
    phone = message.contact.phone_number
    await state.update_data(phone=phone)
    await db.update_user(message.from_user.id, phone=phone)
    cnt = await db.get_cart_count(message.from_user.id)
    await message.answer(Msg.ENTER_COMMENT, reply_markup=main_menu_kb(cnt))
    await message.answer("👇", reply_markup=skip_kb("skip_comment"))
    await state.set_state(OrderStates.entering_comment)


@router.message(OrderStates.entering_phone, F.text)
async def process_phone_text(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        cnt = await db.get_cart_count(message.from_user.id)
        await message.answer(Msg.ORDER_CANCELLED, reply_markup=main_menu_kb(cnt))
        return
    # FIX: нормализация и regex-валидация номера телефона
    phone_raw = message.text.strip()
    phone_clean = re.sub(r'[^\d+]', '', phone_raw)
    if not re.match(r'^\+?\d{7,15}$', phone_clean):
        await message.answer(Msg.PHONE_INVALID)
        return
    phone = phone_clean
    await state.update_data(phone=phone)
    await db.update_user(message.from_user.id, phone=phone)
    cnt = await db.get_cart_count(message.from_user.id)
    await message.answer(Msg.ENTER_COMMENT, reply_markup=main_menu_kb(cnt))
    await message.answer("👇", reply_markup=skip_kb("skip_comment"))
    await state.set_state(OrderStates.entering_comment)


@router.callback_query(F.data == "skip_comment", OrderStates.entering_comment)
async def skip_comment(callback: CallbackQuery, state: FSMContext):
    await state.update_data(comment="")
    await _show_summary(callback, state)
    await callback.answer()


@router.message(OrderStates.entering_comment)
async def process_comment(message: Message, state: FSMContext):
    await state.update_data(comment=message.text.strip())
    await _show_summary(message, state)


async def _show_summary(event, state: FSMContext):
    uid = event.from_user.id
    data = await state.get_data()
    items = await db.get_cart(uid)

    promo_discount = data.get('discount', 0)
    totals = await calculate_total(uid, promo_discount, data['delivery_type'])

    lines = []
    for i in items:
        base = i['price']
        mods_extra = parse_modifiers_price(i['modifiers_json'])
        item_price = base + mods_extra
        item_sum = item_price * i['quantity']
        mods_text = format_modifiers_inline(i['modifiers_json'])
        lines.append(
            f"  • {i['name']}{mods_text} x{i['quantity']} = {format_price(item_sum)}"
        )

    items_text = "\n".join(lines)

    dl = "🚗 Доставка" if data['delivery_type'] == 'delivery' else "🏃 Самовывоз"
    pm = payment_method_text(data.get('payment_method', 'cash'))

    text = f"📋 <b>Подтверждение заказа</b>\n\n{dl}\n{pm}\n"

    if data['delivery_type'] == 'delivery':
        text += f"📍 {data.get('address', '')}\n"
    else:
        pa = await db.get_setting("pickup_address") or ""
        text += f"📍 Самовывоз: {pa}\n"
        if data.get('pickup_time'):
            text += f"🕐 Время: <b>{data['pickup_time']}</b>\n"

    text += f"📱 {data.get('phone', '')}\n"
    if data.get('comment'):
        text += f"💬 {data['comment']}\n"
    text += f"\n{items_text}\n"

    if totals['delivery_price'] > 0:
        text += f"\n🚗 Доставка: {format_price(totals['delivery_price'])}"
    elif data['delivery_type'] == 'delivery':
        text += "\n🚗 Доставка: <b>бесплатно</b>"

    # Акционная скидка
    if totals['promotion_discount'] > 0:
        text += f"\n\n🔥 <b>Скидка по акции: -{format_price(totals['promotion_discount'])}</b>"
        for detail in totals.get('promotion_details', []):
            text += f"\n  {detail}"

    # Промокод
    if promo_discount > 0:
        text += f"\n🏷 Промокод: -{format_price(promo_discount)}"
        if data.get('promo_code'):
            text += f" ({data['promo_code']})"

    text += f"\n\n💰 <b>Итого: {format_price(totals['total'])}</b>"

    if data.get('payment_method') == 'cash':
        text += Msg.CASH_HINT
    elif data.get('payment_method') == 'card':
        if data['delivery_type'] == 'delivery':
            text += Msg.CARD_DELIVERY_HINT
        else:
            text += Msg.CARD_PICKUP_HINT

    await state.update_data(final_total=totals['total'])

    if isinstance(event, CallbackQuery):
        await event.message.edit_text(text, reply_markup=confirm_order_kb(), parse_mode="HTML")
    else:
        await event.answer(text, reply_markup=confirm_order_kb(), parse_mode="HTML")

    await state.set_state(OrderStates.confirming)


# === ПРОМОКОД — НЕ ОЧИЩАЕМ STATE ===
@router.callback_query(F.data == "enter_promo")
async def enter_promo(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer(Msg.ENTER_PROMO)
    await state.set_state(OrderStates.entering_promo)
    await callback.answer()


@router.message(OrderStates.entering_promo)
async def process_promo(message: Message, state: FSMContext):
    code = message.text.strip()
    uid = message.from_user.id
    total = await db.get_cart_total(uid)
    promo, error = await validate_promo(code, uid, total)
    cnt = await db.get_cart_count(uid)
    if error:
        await message.answer(error)
        await message.answer("🛒 Вернитесь в корзину для оформления",
                             reply_markup=main_menu_kb(cnt))
        await state.set_state(None)
        return

    disc = calculate_discount(promo, total)
    await state.update_data(
        promo_code=code.upper(),
        discount=disc,
        promo_id=promo['id']
    )
    await message.answer(
        f"✅ Промокод <b>{code.upper()}</b> применён!\n"
        f"💰 Скидка: {format_price(disc)}\n\n"
        f"🛒 Вернитесь в корзину для оформления",
        parse_mode="HTML",
        reply_markup=main_menu_kb(cnt)
    )
    await state.set_state(None)


@router.callback_query(F.data == "confirm_order", OrderStates.confirming)
async def confirm_order_handler(callback: CallbackQuery, state: FSMContext, bot: Bot):
    data = await state.get_data()
    od = OrderData(
        user_id=callback.from_user.id,
        delivery_type=data.get('delivery_type', 'delivery'),
        payment_method=data.get('payment_method', 'cash'),
        address=data.get('address', ''),
        phone=data.get('phone', ''),
        comment=data.get('comment', ''),
        pickup_time=data.get('pickup_time'),
        promo_code=data.get('promo_code'),
        promo_id=data.get('promo_id'),
        discount=data.get('discount', 0)
    )

    result = await create_order(od)
    if not result.success:
        await callback.message.edit_text(result.error)
        await state.clear()
        await callback.answer()
        return

    await notify_managers(bot, result.order_id)

    cm = await db.get_setting("order_confirmation_msg")
    if cm:
        cm = cm.replace("{order_id}", str(result.order_id))
    else:
        cm = f"✅ Заказ #{result.order_id} оформлен!"

    pm = payment_method_text(data.get('payment_method', 'cash'))
    extra = ""
    if data.get('delivery_type') == 'pickup' and data.get('pickup_time'):
        pa = await db.get_setting("pickup_address") or ""
        extra = f"\n\n🏃 Самовывоз\n🕐 {data['pickup_time']}\n📍 {pa}"

    await callback.message.edit_text(
        f"🎉 {cm}\n{pm}{extra}\n\nМы уведомим вас о статусе.",
        parse_mode="HTML"
    )
    await state.clear()
    await callback.answer("✅ Заказ оформлен!")


@router.callback_query(F.data == "cancel_order")
async def cancel_order(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(Msg.ORDER_CANCELLED)
    await callback.answer()