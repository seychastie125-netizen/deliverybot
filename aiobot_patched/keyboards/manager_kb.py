from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from keyboards.callbacks import MgrOrderCB, MgrCourierCB, MgrCancelConfirmCB


def cancel_confirm_kb(order_id: int) -> InlineKeyboardMarkup:
    """Клавиатура подтверждения отмены заказа."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="✅ Да, отменить",
                callback_data=MgrCancelConfirmCB(order_id=order_id, confirmed=1).pack()
            ),
            InlineKeyboardButton(
                text="◀️ Назад",
                callback_data=MgrCancelConfirmCB(order_id=order_id, confirmed=0).pack()
            ),
        ]
    ])


def manager_order_kb(order_id: int, status: str, delivery_type: str = "delivery"):
    builder = InlineKeyboardBuilder()
    if status == "new":
        builder.row(
            InlineKeyboardButton(
                text="✅ Подтвердить",
                callback_data=MgrOrderCB(action="confirm", order_id=order_id).pack()
            ),
            InlineKeyboardButton(
                text="❌ Отклонить",
                callback_data=MgrOrderCB(action="cancel", order_id=order_id).pack()
            )
        )
    elif status == "confirmed":
        builder.row(InlineKeyboardButton(
            text="👨‍🍳 Готовится",
            callback_data=MgrOrderCB(action="cooking", order_id=order_id).pack()
        ))
    elif status == "cooking":
        if delivery_type == "delivery":
            builder.row(InlineKeyboardButton(
                text="🚴 Назначить курьера",
                callback_data=MgrOrderCB(action="assign_courier", order_id=order_id).pack()
            ))
        else:
            builder.row(InlineKeyboardButton(
                text="✅ Готов к выдаче",
                callback_data=MgrOrderCB(action="ready_pickup", order_id=order_id).pack()
            ))
    elif status == "courier_assigned":
        builder.row(InlineKeyboardButton(
            text="🚴 В пути",
            callback_data=MgrOrderCB(action="delivering", order_id=order_id).pack()
        ))
    elif status == "delivering":
        builder.row(InlineKeyboardButton(
            text="📦 Доставлен",
            callback_data=MgrOrderCB(action="delivered", order_id=order_id).pack()
        ))
    elif status == "delivered":
        builder.row(InlineKeyboardButton(
            text="✅ Завершить",
            callback_data=MgrOrderCB(action="complete", order_id=order_id).pack()
        ))
    elif status == "ready_for_pickup":
        builder.row(InlineKeyboardButton(
            text="✅ Выдан клиенту",
            callback_data=MgrOrderCB(action="complete", order_id=order_id).pack()
        ))
    return builder.as_markup()


def courier_select_kb(couriers, order_id: int):
    builder = InlineKeyboardBuilder()
    for c in couriers:
        builder.button(
            text=f"🚴 {c['full_name']}",
            callback_data=MgrCourierCB(
                order_id=order_id, courier_id=c['user_id']
            ).pack()
        )
    builder.adjust(1)
    builder.row(InlineKeyboardButton(
        text="❌ Отмена",
        callback_data=MgrOrderCB(action="back", order_id=order_id).pack()
    ))
    return builder.as_markup()