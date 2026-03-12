from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton
)
from aiogram.utils.keyboard import InlineKeyboardBuilder
from datetime import datetime, timedelta
import pytz

from keyboards.callbacks import (
    CategoryCB, ProductCB, ProductPageCB, CartActionCB,
    DeliveryTypeCB, PaymentCB, PickupTimeCB
)
from texts.buttons import Btn
from utils.pagination import Paginator


def main_menu_kb(cart_count: int = 0):
    cart_label = f"🛒 Корзина ({cart_count})" if cart_count > 0 else Btn.CART
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=Btn.MENU), KeyboardButton(text=cart_label)],
            [KeyboardButton(text=Btn.PROMOS), KeyboardButton(text=Btn.MY_ORDERS)],
            [KeyboardButton(text=Btn.FAVORITES), KeyboardButton(text=Btn.CONTACTS)],
            [KeyboardButton(text=Btn.ABOUT)],
        ],
        resize_keyboard=True,
        input_field_placeholder="Выберите действие"
    )


def categories_kb(categories):
    builder = InlineKeyboardBuilder()
    for c in categories:
        builder.button(
            text=f"{c['emoji']} {c['name']}",
            callback_data=CategoryCB(id=c['id']).pack()
        )
    builder.adjust(2)
    return builder.as_markup()


def products_kb(products, category_id: int, page: int = 1):
    paginator = Paginator(
        products, page=page, per_page=8,
        callback_prefix=f"prodpage_{category_id}"
    )
    builder = InlineKeyboardBuilder()
    for p in paginator.current_items:
        name = p['name']
        price_str = f"{p['price']:.0f}₽"
        builder.button(
            text=f"{name} — {price_str}",
            callback_data=ProductCB(id=p['id']).pack()
        )
    builder.adjust(1)
    if paginator.has_pages:
        nav = []
        if paginator.page > 1:
            nav.append(InlineKeyboardButton(
                text="◀️",
                callback_data=ProductPageCB(cat_id=category_id, page=paginator.page - 1).pack()
            ))
        nav.append(InlineKeyboardButton(
            text=f"{paginator.page}/{paginator.total_pages}",
            callback_data="noop"
        ))
        if paginator.page < paginator.total_pages:
            nav.append(InlineKeyboardButton(
                text="▶️",
                callback_data=ProductPageCB(cat_id=category_id, page=paginator.page + 1).pack()
            ))
        builder.row(*nav)
    builder.row(InlineKeyboardButton(text="⬅️ Категории", callback_data="back_categories"))
    return builder.as_markup()


def product_detail_kb(product_id: int, category_id: int):
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="➖",
            callback_data=CartActionCB(action="minus", product_id=product_id).pack()
        ),
        InlineKeyboardButton(
            text="🛒 В корзину",
            callback_data=CartActionCB(action="add", product_id=product_id).pack()
        ),
        InlineKeyboardButton(
            text="➕",
            callback_data=CartActionCB(action="plus", product_id=product_id).pack()
        )
    )
    builder.row(InlineKeyboardButton(
        text=Btn.BACK,
        callback_data=CategoryCB(id=category_id).pack()
    ))
    return builder.as_markup()


def cart_kb(cart_items):
    builder = InlineKeyboardBuilder()
    for item in cart_items:
        builder.row(
            InlineKeyboardButton(
                text=f"❌ {item['name']} x{item['quantity']}",
                callback_data=CartActionCB(action="remove", item_id=item['id']).pack()
            ),
            InlineKeyboardButton(
                text="➖",
                callback_data=CartActionCB(action="dec", item_id=item['id']).pack()
            ),
            InlineKeyboardButton(
                text="➕",
                callback_data=CartActionCB(action="inc", item_id=item['id']).pack()
            )
        )
    builder.row(
        InlineKeyboardButton(
            text=Btn.CLEAR_CART,
            callback_data=CartActionCB(action="clear").pack()
        ),
        InlineKeyboardButton(
            text=Btn.CHECKOUT,
            callback_data="checkout"
        )
    )
    builder.row(InlineKeyboardButton(
        text=Btn.PROMO_CODE,
        callback_data="enter_promo"
    ))
    return builder.as_markup()


def empty_cart_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=Btn.TO_MENU, callback_data="back_categories")]
    ])


def delivery_type_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=Btn.DELIVERY,
                callback_data=DeliveryTypeCB(type="delivery").pack()
            ),
            InlineKeyboardButton(
                text=Btn.PICKUP,
                callback_data=DeliveryTypeCB(type="pickup").pack()
            )
        ],
        [InlineKeyboardButton(text=Btn.CANCEL, callback_data="cancel_order")]
    ])


def payment_method_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=Btn.PAY_CASH,
                callback_data=PaymentCB(method="cash").pack()
            ),
            InlineKeyboardButton(
                text=Btn.PAY_CARD,
                callback_data=PaymentCB(method="card").pack()
            )
        ],
        [InlineKeyboardButton(text=Btn.CANCEL, callback_data="cancel_order")]
    ])


def pickup_time_kb(timezone_str: str = "Europe/Moscow",
                   work_start: str = "09:00", work_end: str = "23:00",
                   step_minutes: int = 15, min_wait_minutes: int = 30):
    tz = pytz.timezone(timezone_str)
    now = datetime.now(tz)
    start_h, start_m = map(int, work_start.split(":"))
    end_h, end_m = map(int, work_end.split(":"))
    work_start_dt = now.replace(hour=start_h, minute=start_m, second=0, microsecond=0)
    work_end_dt = now.replace(hour=end_h, minute=end_m, second=0, microsecond=0)
    earliest = now + timedelta(minutes=min_wait_minutes)
    mins = earliest.hour * 60 + earliest.minute
    rem = mins % step_minutes
    if rem != 0:
        earliest += timedelta(minutes=step_minutes - rem)
    earliest = earliest.replace(second=0, microsecond=0)
    if earliest < work_start_dt:
        earliest = work_start_dt

    builder = InlineKeyboardBuilder()
    slots = []
    current = earliest
    while current <= work_end_dt and len(slots) < 20:
        time_str = current.strftime("%H:%M")
        time_key = current.strftime("%H%M")  # HHMM — no colon, safe for callback_data
        slots.append(time_str)
        builder.button(
            text=f"🕐 {time_str}",
            callback_data=PickupTimeCB(time=time_key).pack()
        )
        current += timedelta(minutes=step_minutes)
    builder.adjust(4)
    builder.row(InlineKeyboardButton(text=Btn.CANCEL, callback_data="cancel_order"))
    return builder.as_markup(), len(slots) > 0


def phone_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=Btn.SEND_PHONE, request_contact=True)],
            [KeyboardButton(text=Btn.CANCEL)]
        ],
        resize_keyboard=True, one_time_keyboard=True
    )


def confirm_order_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=Btn.CONFIRM, callback_data="confirm_order"),
            InlineKeyboardButton(text=Btn.CANCEL, callback_data="cancel_order")
        ]
    ])


def skip_kb(callback_data: str = "skip"):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=Btn.SKIP, callback_data=callback_data)]
    ])


def reorder_kb(order_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Повторить заказ", callback_data=f"reorder_{order_id}")]
    ])


def order_status_emoji(status: str) -> str:
    m = {
        "new": "🆕 Новый", "confirmed": "✅ Подтверждён",
        "cooking": "👨‍🍳 Готовится", "courier_assigned": "🚗 Курьер назначен",
        "delivering": "🚴 В пути", "ready_for_pickup": "✅ Готов к выдаче",
        "delivered": "📦 Доставлен", "completed": "✅ Завершён",
        "cancelled": "❌ Отменён",
    }
    return m.get(status, status)


def payment_method_text(method: str) -> str:
    return {"cash": "💵 Наличными", "card": "💳 Картой"}.get(method, method)