from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from keyboards.callbacks import (
    AdminCatCB, AdminProdCB, AdminPromoCB, AdminPromotionCB,
    AdminCourierCB, AdminSettingCB, AdminOrdersCB,
    NewProdCatCB, EditFieldCB, PromoTypeCB
)


def admin_main_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📁 Категории", callback_data="adm_categories"),
            InlineKeyboardButton(text="🍕 Товары", callback_data="adm_products")
        ],
        [
            InlineKeyboardButton(text="📦 Заказы", callback_data="adm_orders"),
            InlineKeyboardButton(text="👥 Клиенты", callback_data="adm_users")
        ],
        [
            InlineKeyboardButton(text="🏷 Промокоды", callback_data="adm_promos"),
            InlineKeyboardButton(text="🔥 Акции", callback_data="adm_promotions")
        ],
        [
            InlineKeyboardButton(text="🚴 Курьеры", callback_data="adm_couriers"),
            InlineKeyboardButton(text="⚙️ Настройки", callback_data="adm_settings")
        ],
        [
            InlineKeyboardButton(text="📊 Аналитика", callback_data="adm_analytics"),
            InlineKeyboardButton(text="📢 Рассылка", callback_data="adm_broadcast")
        ],
        [
            InlineKeyboardButton(text="❤️ Избранное", callback_data="adm_favorites_settings"),
            InlineKeyboardButton(text="📍 Геолокация", callback_data="adm_geo_settings")
        ],
    ])


def admin_categories_kb(categories):
    builder = InlineKeyboardBuilder()
    for c in categories:
        st = "✅" if c['is_active'] else "❌"
        builder.button(
            text=f"{st} {c['emoji']} {c['name']}",
            callback_data=AdminCatCB(action="detail", id=c['id']).pack()
        )
    builder.adjust(1)
    builder.row(InlineKeyboardButton(
        text="➕ Добавить категорию",
        callback_data=AdminCatCB(action="add").pack()
    ))
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="adm_back"))
    return builder.as_markup()


def admin_category_actions_kb(cat_id: int, is_active: bool):
    toggle = "Скрыть" if is_active else "Показать"
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=f"👁 {toggle}",
                callback_data=AdminCatCB(action="toggle", id=cat_id).pack()
            ),
            InlineKeyboardButton(
                text="🗑 Удалить",
                callback_data=AdminCatCB(action="del", id=cat_id).pack()
            )
        ],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="adm_categories")]
    ])


def admin_category_del_confirm_kb(cat_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="🗑 Да, удалить",
            callback_data=AdminCatCB(action="del_yes", id=cat_id).pack()
        )],
        [InlineKeyboardButton(
            text="❌ Отмена",
            callback_data=AdminCatCB(action="detail", id=cat_id).pack()
        )]
    ])


def admin_products_kb(products):
    builder = InlineKeyboardBuilder()
    for p in products:
        st = "✅" if p['is_available'] else "❌"
        builder.button(
            text=f"{st} {p['name']} — {p['price']:.0f}₽",
            callback_data=AdminProdCB(action="detail", id=p['id']).pack()
        )
    builder.adjust(1)
    builder.row(InlineKeyboardButton(
        text="➕ Добавить товар",
        callback_data=AdminProdCB(action="add").pack()
    ))
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="adm_back"))
    return builder.as_markup()


def admin_product_actions_kb(prod_id: int, is_available: bool):
    toggle = "Скрыть" if is_available else "Показать"
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=f"👁 {toggle}",
                callback_data=AdminProdCB(action="toggle", id=prod_id).pack()
            ),
            InlineKeyboardButton(
                text="✏️ Редактировать",
                callback_data=AdminProdCB(action="edit", id=prod_id).pack()
            )
        ],
        [
            InlineKeyboardButton(
                text="⚙️ Модификаторы",
                callback_data=AdminProdCB(action="mods", id=prod_id).pack()
            )
        ],
        [InlineKeyboardButton(
            text="🗑 Удалить",
            callback_data=AdminProdCB(action="del", id=prod_id).pack()
        )],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="adm_products")]
    ])


def admin_product_del_confirm_kb(prod_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="🗑 Да, удалить",
            callback_data=AdminProdCB(action="del_yes", id=prod_id).pack()
        )],
        [InlineKeyboardButton(
            text="❌ Отмена",
            callback_data=AdminProdCB(action="detail", id=prod_id).pack()
        )]
    ])


def admin_product_edit_kb(prod_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Название", callback_data=EditFieldCB(field="name").pack())],
        [InlineKeyboardButton(text="📄 Описание", callback_data=EditFieldCB(field="description").pack())],
        [InlineKeyboardButton(text="💰 Цена", callback_data=EditFieldCB(field="price").pack())],
        [InlineKeyboardButton(text="🖼 Фото", callback_data=EditFieldCB(field="image_url").pack())],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="adm_products")]
    ])


def admin_newprod_categories_kb(categories):
    builder = InlineKeyboardBuilder()
    for c in categories:
        builder.button(
            text=f"{c['emoji']} {c['name']}",
            callback_data=NewProdCatCB(cat_id=c['id']).pack()
        )
    builder.adjust(2)
    return builder.as_markup()


def admin_promos_kb(promos):
    builder = InlineKeyboardBuilder()
    for p in promos:
        st = "✅" if p['is_active'] else "❌"
        sym = "%" if p['discount_type'] == 'percent' else '₽'
        builder.button(
            text=f"{st} {p['code']} (-{p['discount_value']}{sym})",
            callback_data=AdminPromoCB(action="detail", id=p['id']).pack()
        )
    builder.adjust(1)
    builder.row(InlineKeyboardButton(
        text="➕ Добавить промокод",
        callback_data=AdminPromoCB(action="add").pack()
    ))
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="adm_back"))
    return builder.as_markup()


def admin_promo_actions_kb(promo_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="🗑 Удалить",
            callback_data=AdminPromoCB(action="del", id=promo_id).pack()
        )],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="adm_promos")]
    ])


def admin_promo_type_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="📊 Процент (%)",
                callback_data=PromoTypeCB(discount_type="percent").pack()
            ),
            InlineKeyboardButton(
                text="💰 Фикс. сумма (₽)",
                callback_data=PromoTypeCB(discount_type="fixed").pack()
            )
        ]
    ])


def admin_promotions_kb(promotions):
    builder = InlineKeyboardBuilder()
    for p in promotions:
        st = "✅" if p['is_active'] else "❌"
        builder.button(
            text=f"{st} {p['title']}",
            callback_data=AdminPromotionCB(action="detail", id=p['id']).pack()
        )
    builder.adjust(1)
    builder.row(InlineKeyboardButton(
        text="➕ Добавить акцию",
        callback_data=AdminPromotionCB(action="add").pack()
    ))
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="adm_back"))
    return builder.as_markup()


def admin_promotion_actions_kb(pid: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="🗑 Удалить",
            callback_data=AdminPromotionCB(action="del", id=pid).pack()
        )],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="adm_promotions")]
    ])


def admin_couriers_kb(couriers):
    builder = InlineKeyboardBuilder()
    for c in couriers:
        st = "✅" if c['is_active'] else "❌"
        builder.button(
            text=f"{st} {c['full_name']}",
            callback_data=AdminCourierCB(action="detail", id=c['user_id']).pack()
        )
    builder.adjust(1)
    builder.row(InlineKeyboardButton(
        text="➕ Добавить курьера",
        callback_data=AdminCourierCB(action="add").pack()
    ))
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="adm_back"))
    return builder.as_markup()


def admin_courier_actions_kb(cid: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="🗑 Удалить",
            callback_data=AdminCourierCB(action="del", id=cid).pack()
        )],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="adm_couriers")]
    ])


def admin_settings_kb(settings: dict):
    builder = InlineKeyboardBuilder()
    labels = {
        "min_order_amount": "💰 Мин. заказ",
        "delivery_price": "🚗 Цена доставки",
        "free_delivery_from": "🆓 Беспл. от",
        "work_hours_start": "🕐 Начало",
        "work_hours_end": "🕐 Конец",
        "pickup_address": "📍 Адрес самовыв.",
        "pickup_reminder_minutes": "⏰ Напомин. (мин)",
        "pickup_time_step": "🕐 Шаг (мин)",
        "pickup_min_wait": "⏳ Ожидание (мин)",
        "welcome_message": "👋 Приветствие",
        "bot_is_active": "🟢 Бот активен",
        "currency_symbol": "💱 Валюта",
    }
    for key, label in labels.items():
        val = settings.get(key, "—")
        dv = val if len(str(val)) <= 15 else str(val)[:12] + "..."
        builder.button(
            text=f"{label}: {dv}",
            callback_data=AdminSettingCB(key=key).pack()
        )
    builder.adjust(1)
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="adm_back"))
    return builder.as_markup()


def admin_orders_filter_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="🆕 Новые",
                callback_data=AdminOrdersCB(status="new").pack()
            ),
            InlineKeyboardButton(
                text="✅ Подтв.",
                callback_data=AdminOrdersCB(status="confirmed").pack()
            )
        ],
        [
            InlineKeyboardButton(
                text="👨‍🍳 Готовятся",
                callback_data=AdminOrdersCB(status="cooking").pack()
            ),
            InlineKeyboardButton(
                text="🚴 В пути",
                callback_data=AdminOrdersCB(status="delivering").pack()
            )
        ],
        [InlineKeyboardButton(
            text="📦 Все",
            callback_data=AdminOrdersCB(status="all").pack()
        )],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="adm_back")]
    ])


def admin_broadcast_confirm_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Отправить", callback_data="adm_broadcast_yes"),
            InlineKeyboardButton(text="❌ Отмена", callback_data="adm_broadcast_no")
        ]
    ])


def back_kb(callback_data: str = "adm_back"):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Назад", callback_data=callback_data)]
    ])