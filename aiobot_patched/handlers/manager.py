from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery
from database.db import db
from keyboards.manager_kb import manager_order_kb, courier_select_kb, cancel_confirm_kb
from keyboards.callbacks import MgrOrderCB, MgrCourierCB, MgrCancelConfirmCB
from utils.notifications import notify_client, notify_courier
from texts.messages import Msg
from filters.role import IsManager

router = Router()
router.callback_query.filter(IsManager())


@router.callback_query(MgrOrderCB.filter(F.action == "confirm"))
async def mgr_confirm(callback: CallbackQuery, callback_data: MgrOrderCB, bot: Bot):
    oid = callback_data.order_id
    await db.update_order_status(oid, "confirmed", callback.from_user.id)
    order = await db.get_order(oid)
    text = Msg.order_status_text(oid, "confirmed")
    if order['delivery_type'] == 'pickup' and order['pickup_time']:
        pa = await db.get_setting("pickup_address") or ""
        text += f"\n🕐 Ждём вас в <b>{order['pickup_time']}</b>\n📍 {pa}"
    await notify_client(bot, order['user_id'], text)
    await callback.message.edit_reply_markup(
        reply_markup=manager_order_kb(oid, "confirmed", order['delivery_type'])
    )
    await callback.answer("✅ Подтверждён")


@router.callback_query(MgrOrderCB.filter(F.action == "cancel"))
async def mgr_cancel_ask(callback: CallbackQuery, callback_data: MgrOrderCB):
    """Шаг 1: показываем запрос подтверждения."""
    oid = callback_data.order_id
    order = await db.get_order(oid)
    if not order:
        await callback.answer("Заказ не найден", show_alert=True)
        return
    await callback.message.edit_text(
        f"⚠️ <b>Вы уверены, что хотите отменить заказ #{oid}?</b>\n\n"
        f"Клиент получит уведомление об отмене.",
        reply_markup=cancel_confirm_kb(oid),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(MgrCancelConfirmCB.filter())
async def mgr_cancel_confirm(callback: CallbackQuery, callback_data: MgrCancelConfirmCB,
                              bot: Bot):
    """Шаг 2: пользователь нажал «Да, отменить» или «Назад»."""
    oid = callback_data.order_id
    order = await db.get_order(oid)
    if not order:
        await callback.answer("Заказ не найден", show_alert=True)
        return

    if callback_data.confirmed == 0:
        # Назад — восстанавливаем исходное сообщение с кнопками
        await callback.message.edit_text(
            callback.message.text,
            reply_markup=manager_order_kb(oid, order['status'], order['delivery_type']),
            parse_mode="HTML"
        )
        await callback.answer("Отмена отменена 👍")
        return

    # Подтверждено — отменяем заказ
    await db.update_order_status(oid, "cancelled", callback.from_user.id)
    await notify_client(bot, order['user_id'], Msg.order_status_text(oid, "cancelled"))
    try:
        await callback.message.edit_text(
            callback.message.text + "\n\n❌ <b>ОТКЛОНЁН</b>",
            reply_markup=None,
            parse_mode="HTML"
        )
    except Exception:
        await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer("❌ Заказ отменён")


@router.callback_query(MgrOrderCB.filter(F.action == "cooking"))
async def mgr_cooking(callback: CallbackQuery, callback_data: MgrOrderCB, bot: Bot):
    oid = callback_data.order_id
    await db.update_order_status(oid, "cooking", callback.from_user.id)
    order = await db.get_order(oid)
    await notify_client(bot, order['user_id'], Msg.order_status_text(oid, "cooking"))
    await callback.message.edit_reply_markup(
        reply_markup=manager_order_kb(oid, "cooking", order['delivery_type'])
    )
    await callback.answer("👨‍🍳 Готовится")


@router.callback_query(MgrOrderCB.filter(F.action == "ready_pickup"))
async def mgr_ready_pickup(callback: CallbackQuery, callback_data: MgrOrderCB, bot: Bot):
    oid = callback_data.order_id
    await db.update_order_status(oid, "ready_for_pickup", callback.from_user.id)
    order = await db.get_order(oid)
    pa = await db.get_setting("pickup_address") or ""
    text = f"✅ Ваш заказ <b>#{oid}</b> готов!\n🏃 Забирайте:\n📍 <b>{pa}</b>"
    if order['pickup_time']:
        text += f"\n🕐 Время: {order['pickup_time']}"
    await notify_client(bot, order['user_id'], text)
    await callback.message.edit_reply_markup(
        reply_markup=manager_order_kb(oid, "ready_for_pickup", "pickup")
    )
    await callback.answer("✅ Готов к выдаче")


@router.callback_query(F.data.startswith("mgr_ready_pickup_"))
async def mgr_ready_pickup_from_reminder(callback: CallbackQuery, bot: Bot):
    oid = int(callback.data.split("_")[3])
    await db.update_order_status(oid, "ready_for_pickup", callback.from_user.id)
    order = await db.get_order(oid)
    pa = await db.get_setting("pickup_address") or ""
    text = f"✅ Ваш заказ <b>#{oid}</b> готов!\n📍 {pa}"
    await notify_client(bot, order['user_id'], text)
    await callback.message.edit_reply_markup(
        reply_markup=manager_order_kb(oid, "ready_for_pickup", "pickup")
    )
    await callback.answer("✅ Готов к выдаче")


@router.callback_query(MgrOrderCB.filter(F.action == "assign_courier"))
async def mgr_assign(callback: CallbackQuery, callback_data: MgrOrderCB):
    couriers = await db.get_couriers(only_active=True)
    if not couriers:
        await callback.answer("❌ Нет курьеров", show_alert=True)
        return
    await callback.message.edit_reply_markup(
        reply_markup=courier_select_kb(couriers, callback_data.order_id)
    )
    await callback.answer()


@router.callback_query(MgrCourierCB.filter())
async def mgr_set_courier(callback: CallbackQuery, callback_data: MgrCourierCB, bot: Bot):
    oid = callback_data.order_id
    cid = callback_data.courier_id
    await db.assign_courier(oid, cid, callback.from_user.id)
    order = await db.get_order(oid)
    courier = await db.get_courier(cid)
    await notify_client(
        bot, order['user_id'],
        f"🚴 Курьер <b>{courier['full_name']}</b> назначен на заказ #{oid}"
    )
    await notify_courier(bot, cid, oid)
    await callback.message.edit_reply_markup(
        reply_markup=manager_order_kb(oid, "courier_assigned", "delivery")
    )
    await callback.answer(f"✅ Курьер {courier['full_name']}")


@router.callback_query(MgrOrderCB.filter(F.action == "delivering"))
async def mgr_delivering(callback: CallbackQuery, callback_data: MgrOrderCB, bot: Bot):
    oid = callback_data.order_id
    await db.update_order_status(oid, "delivering", callback.from_user.id)
    order = await db.get_order(oid)
    await notify_client(bot, order['user_id'], Msg.order_status_text(oid, "delivering"))
    await callback.message.edit_reply_markup(
        reply_markup=manager_order_kb(oid, "delivering", "delivery")
    )
    await callback.answer("🚴 В пути")


@router.callback_query(MgrOrderCB.filter(F.action == "delivered"))
async def mgr_delivered(callback: CallbackQuery, callback_data: MgrOrderCB, bot: Bot):
    oid = callback_data.order_id
    await db.update_order_status(oid, "delivered", callback.from_user.id)
    order = await db.get_order(oid)
    await notify_client(bot, order['user_id'], Msg.order_status_text(oid, "delivered"))
    await callback.message.edit_reply_markup(
        reply_markup=manager_order_kb(oid, "delivered", "delivery")
    )
    await callback.answer("📦 Доставлен")


@router.callback_query(MgrOrderCB.filter(F.action == "complete"))
async def mgr_complete(callback: CallbackQuery, callback_data: MgrOrderCB, bot: Bot):
    oid = callback_data.order_id
    await db.update_order_status(oid, "completed", callback.from_user.id)
    order = await db.get_order(oid)
    await notify_client(bot, order['user_id'], Msg.order_status_text(oid, "completed"))
    await callback.message.edit_reply_markup(reply_markup=None)
    try:
        await callback.message.edit_text(
            callback.message.text + "\n\n✅ <b>ЗАВЕРШЁН</b>", parse_mode="HTML"
        )
    except Exception:
        pass
    await callback.answer("✅ Завершён")