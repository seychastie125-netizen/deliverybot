from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from database.db import db
from keyboards.admin_kb import (
    admin_main_kb, admin_categories_kb, admin_category_actions_kb,
    admin_category_del_confirm_kb, admin_products_kb, admin_product_actions_kb,
    admin_product_del_confirm_kb, admin_product_edit_kb, admin_newprod_categories_kb,
    admin_promos_kb, admin_promo_actions_kb, admin_promo_type_kb,
    admin_promotions_kb, admin_promotion_actions_kb,
    admin_couriers_kb, admin_courier_actions_kb,
    admin_settings_kb, admin_orders_filter_kb, admin_broadcast_confirm_kb,
    back_kb,
)
from keyboards.callbacks import (
    AdminCatCB, AdminProdCB, AdminPromoCB, AdminPromotionCB,
    AdminCourierCB, AdminSettingCB, AdminOrdersCB,
    NewProdCatCB, EditFieldCB, PromoTypeCB
)
from keyboards.client_kb import order_status_emoji
from states.states import (
    AdminProductStates, AdminCategoryStates, AdminPromoStates,
    AdminPromotionStates, AdminCourierStates, AdminSettingStates,
    AdminBroadcastStates, AdminEditProductStates,
)
from utils.helpers import format_price
from texts.messages import Msg
from filters.role import IsAdmin

router = Router()
# Фильтр на весь роутер — только админы
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())


async def _admin_home_text():
    today = await db.get_today_stats()
    uc = await db.get_users_count()
    return (
        "🔧 <b>Админ-панель</b>\n\n"
        f"📊 Заказов сегодня: {today[0]}\n"
        f"💰 Выручка: {format_price(today[1])}\n"
        f"👥 Клиентов: {uc}"
    )


@router.message(Command("admin"))
async def cmd_admin(message: Message):
    await message.answer(await _admin_home_text(),
                         reply_markup=admin_main_kb(), parse_mode="HTML")


@router.callback_query(F.data == "adm_back")
async def admin_back(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        await _admin_home_text(), reply_markup=admin_main_kb(), parse_mode="HTML"
    )
    await callback.answer()


# ==================== КАТЕГОРИИ ====================
@router.callback_query(F.data == "adm_categories")
async def adm_categories(callback: CallbackQuery):
    cats = await db.get_categories(only_active=False)
    await callback.message.edit_text(
        "📁 <b>Категории:</b>", reply_markup=admin_categories_kb(cats), parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(AdminCatCB.filter(F.action == "detail"))
async def adm_cat_detail(callback: CallbackQuery, callback_data: AdminCatCB):
    cat = await db.get_category(callback_data.id)
    if not cat:
        await callback.answer("Не найдена", show_alert=True)
        return
    prods = await db.get_products(callback_data.id, only_available=False)
    text = (
        f"{cat['emoji']} <b>{cat['name']}</b>\n"
        f"{'✅ Активна' if cat['is_active'] else '❌ Скрыта'}\n"
        f"Товаров: {len(prods)}"
    )
    await callback.message.edit_text(
        text,
        reply_markup=admin_category_actions_kb(callback_data.id, cat['is_active']),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(AdminCatCB.filter(F.action == "toggle"))
async def adm_cat_toggle(callback: CallbackQuery, callback_data: AdminCatCB):
    cat = await db.get_category(callback_data.id)
    await db.update_category(callback_data.id, is_active=0 if cat['is_active'] else 1)
    cats = await db.get_categories(only_active=False)
    await callback.message.edit_text(
        "📁 <b>Категории:</b>", reply_markup=admin_categories_kb(cats), parse_mode="HTML"
    )
    await callback.answer("✅ Обновлено")


@router.callback_query(AdminCatCB.filter(F.action == "del"))
async def adm_cat_del_confirm(callback: CallbackQuery, callback_data: AdminCatCB):
    cat = await db.get_category(callback_data.id)
    prods = await db.get_products(callback_data.id, only_available=False)
    await callback.message.edit_text(
        Msg.DELETE_CONFIRM.format(
            name=cat['name'],
            extra=f"Будет удалено {len(prods)} товаров!"
        ),
        reply_markup=admin_category_del_confirm_kb(callback_data.id),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(AdminCatCB.filter(F.action == "del_yes"))
async def adm_cat_del_exec(callback: CallbackQuery, callback_data: AdminCatCB):
    await db.delete_category(callback_data.id)
    cats = await db.get_categories(only_active=False)
    await callback.message.edit_text(
        "📁 <b>Категории:</b>", reply_markup=admin_categories_kb(cats), parse_mode="HTML"
    )
    await callback.answer("🗑 Удалено")


@router.callback_query(AdminCatCB.filter(F.action == "add"))
async def adm_cat_add(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("📁 Название категории:")
    await state.set_state(AdminCategoryStates.waiting_name)
    await callback.answer()


@router.message(AdminCategoryStates.waiting_name)
async def adm_cat_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text.strip())
    await message.answer("Эмодзи (например 🍕):")
    await state.set_state(AdminCategoryStates.waiting_emoji)


@router.message(AdminCategoryStates.waiting_emoji)
async def adm_cat_emoji(message: Message, state: FSMContext):
    data = await state.get_data()
    emoji = message.text.strip()[:4]
    await db.add_category(data['name'], emoji)
    await message.answer(f"✅ Категория «{emoji} {data['name']}» создана!")
    await state.clear()
    cats = await db.get_categories(only_active=False)
    await message.answer("📁 Категории:", reply_markup=admin_categories_kb(cats))


# ==================== ТОВАРЫ ====================
@router.callback_query(F.data == "adm_products")
async def adm_products(callback: CallbackQuery):
    prods = await db.get_all_products()
    await callback.message.edit_text(
        "🍕 <b>Товары:</b>", reply_markup=admin_products_kb(prods), parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(AdminProdCB.filter(F.action == "detail"))
async def adm_prod_detail(callback: CallbackQuery, callback_data: AdminProdCB):
    p = await db.get_product(callback_data.id)
    if not p:
        await callback.answer("Не найден", show_alert=True)
        return
    text = (
        f"🍕 <b>{p['name']}</b>\n\n"
        f"📄 {p['description'] or '—'}\n"
        f"💰 {format_price(p['price'])}\n"
        f"{'✅ Доступен' if p['is_available'] else '❌ Скрыт'}"
    )
    await callback.message.edit_text(
        text, reply_markup=admin_product_actions_kb(callback_data.id, p['is_available']),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(AdminProdCB.filter(F.action == "toggle"))
async def adm_prod_toggle(callback: CallbackQuery, callback_data: AdminProdCB):
    p = await db.get_product(callback_data.id)
    await db.update_product(callback_data.id, is_available=0 if p['is_available'] else 1)
    prods = await db.get_all_products()
    await callback.message.edit_text(
        "🍕 <b>Товары:</b>", reply_markup=admin_products_kb(prods), parse_mode="HTML"
    )
    await callback.answer("✅")


@router.callback_query(AdminProdCB.filter(F.action == "del"))
async def adm_prod_del_confirm(callback: CallbackQuery, callback_data: AdminProdCB):
    p = await db.get_product(callback_data.id)
    await callback.message.edit_text(
        Msg.DELETE_CONFIRM.format(name=p['name'], extra=""),
        reply_markup=admin_product_del_confirm_kb(callback_data.id),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(AdminProdCB.filter(F.action == "del_yes"))
async def adm_prod_del_exec(callback: CallbackQuery, callback_data: AdminProdCB):
    await db.delete_product(callback_data.id)
    prods = await db.get_all_products()
    await callback.message.edit_text(
        "🍕 <b>Товары:</b>", reply_markup=admin_products_kb(prods), parse_mode="HTML"
    )
    await callback.answer("🗑 Удалено")


@router.callback_query(AdminProdCB.filter(F.action == "edit"))
async def adm_prod_edit(callback: CallbackQuery, callback_data: AdminProdCB, state: FSMContext):
    await state.update_data(edit_prod_id=callback_data.id)
    await callback.message.edit_text(
        "✏️ Что изменить?", reply_markup=admin_product_edit_kb(callback_data.id)
    )
    await callback.answer()


@router.callback_query(EditFieldCB.filter())
async def adm_edit_field(callback: CallbackQuery, callback_data: EditFieldCB, state: FSMContext):
    await state.update_data(edit_field=callback_data.field)
    labels = {"name": "название", "description": "описание",
              "price": "цену", "image_url": "ссылку на фото или отправьте фото"}
    await callback.message.edit_text(f"Введите новое {labels.get(callback_data.field, '')}:")
    await state.set_state(AdminEditProductStates.waiting_value)
    await callback.answer()


@router.message(AdminEditProductStates.waiting_value, F.photo)
async def adm_edit_value_photo(message: Message, state: FSMContext):
    """Редактирование поля image_url — отправка фото напрямую."""
    data = await state.get_data()
    if data.get('edit_field') != 'image_url':
        await message.answer("❌ Ожидается текст, а не фото. Введите значение:")
        return
    file_id = message.photo[-1].file_id
    await db.update_product(data['edit_prod_id'], image_url=file_id)
    await message.answer("✅ Фото обновлено!")
    await state.clear()
    p = await db.get_product(data['edit_prod_id'])
    if p:
        cat = await db.get_category(p['category_id'])
        prods = await db.get_products(p['category_id'], only_available=False)
        await message.answer(
            f"{cat['emoji']} <b>{cat['name']}</b> — {len(prods)} товаров",
            reply_markup=admin_products_in_cat_kb(prods, p['category_id']),
            parse_mode="HTML"
        )


@router.message(AdminEditProductStates.waiting_value, F.text)
async def adm_edit_value(message: Message, state: FSMContext):
    data = await state.get_data()
    field = data['edit_field']
    value = message.text.strip()
    if field == "price":
        try:
            value = float(value.replace(",", "."))
        except ValueError:
            await message.answer("❌ Введите число")
            return
    await db.update_product(data['edit_prod_id'], **{field: value})
    await message.answer("✅ Обновлено!")
    await state.clear()
    prods = await db.get_all_products()
    await message.answer("🍕 Товары:", reply_markup=admin_products_kb(prods))


@router.callback_query(AdminProdCB.filter(F.action == "add"))
async def adm_prod_add(callback: CallbackQuery):
    cats = await db.get_categories(only_active=False)
    if not cats:
        await callback.answer("Сначала создайте категорию!", show_alert=True)
        return
    await callback.message.edit_text(
        "Категория:", reply_markup=admin_newprod_categories_kb(cats)
    )
    await callback.answer()


@router.callback_query(NewProdCatCB.filter())
async def adm_newprod_cat(callback: CallbackQuery, callback_data: NewProdCatCB, state: FSMContext):
    await state.update_data(category_id=callback_data.cat_id)
    await callback.message.edit_text("📝 Название товара:")
    await state.set_state(AdminProductStates.waiting_name)
    await callback.answer()


@router.message(AdminProductStates.waiting_name)
async def adm_prod_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text.strip())
    await message.answer("📄 Описание:")
    await state.set_state(AdminProductStates.waiting_description)


@router.message(AdminProductStates.waiting_description)
async def adm_prod_desc(message: Message, state: FSMContext):
    await state.update_data(description=message.text.strip())
    await message.answer("💰 Цена:")
    await state.set_state(AdminProductStates.waiting_price)


@router.message(AdminProductStates.waiting_price)
async def adm_prod_price(message: Message, state: FSMContext):
    try:
        price = float(message.text.strip().replace(",", "."))
    except ValueError:
        await message.answer("❌ Введите число")
        return
    await state.update_data(price=price)
    await message.answer("🖼 Отправьте фото или введите ссылку (или 'нет'):")
    await state.set_state(AdminProductStates.waiting_image)


@router.message(AdminProductStates.waiting_image)
async def adm_prod_image(message: Message, state: FSMContext):
    data = await state.get_data()
    image_url = None
    if message.photo:
        image_url = message.photo[-1].file_id
    elif message.text and message.text.lower() not in ("нет", "no", "-", "skip"):
        image_url = message.text.strip()
    await db.add_product(data['category_id'], data['name'],
                         data['description'], data['price'], image_url)
    await message.answer(f"✅ Товар «{data['name']}» добавлен!")
    await state.clear()
    cat = await db.get_category(data['category_id'])
    prods = await db.get_products(data['category_id'], only_available=False)
    await message.answer(
        f"{cat['emoji']} <b>{cat['name']}</b> — {len(prods)} товаров",
        reply_markup=admin_products_in_cat_kb(prods, data['category_id']),
        parse_mode="HTML"
    )


# ==================== ПРОМОКОДЫ ====================
@router.callback_query(F.data == "adm_promos")
async def adm_promos(callback: CallbackQuery):
    p = await db.get_all_promocodes()
    await callback.message.edit_text(
        "🏷 <b>Промокоды:</b>", reply_markup=admin_promos_kb(p), parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(AdminPromoCB.filter(F.action == "detail"))
async def adm_promo_detail(callback: CallbackQuery, callback_data: AdminPromoCB):
    promos = await db.get_all_promocodes()
    promo = None
    for p in promos:
        if p['id'] == callback_data.id:
            promo = p
            break
    if not promo:
        await callback.answer("Не найден", show_alert=True)
        return
    sym = "%" if promo['discount_type'] == 'percent' else '₽'
    mx = promo['max_uses'] if promo['max_uses'] != -1 else '∞'
    text = (
        f"🏷 <b>{promo['code']}</b>\n\n"
        f"💰 Скидка: {promo['discount_value']}{sym}\n"
        f"📦 Мин. заказ: {format_price(promo['min_order'])}\n"
        f"🔢 Использований: {promo['used_count']}/{mx}\n"
        f"{'✅ Активен' if promo['is_active'] else '❌ Неактивен'}"
    )
    await callback.message.edit_text(
        text, reply_markup=admin_promo_actions_kb(callback_data.id), parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(AdminPromoCB.filter(F.action == "del"))
async def adm_promo_del(callback: CallbackQuery, callback_data: AdminPromoCB):
    await db.delete_promocode(callback_data.id)
    p = await db.get_all_promocodes()
    await callback.message.edit_text(
        "🏷 <b>Промокоды:</b>", reply_markup=admin_promos_kb(p), parse_mode="HTML"
    )
    await callback.answer("🗑 Удалено")


@router.callback_query(AdminPromoCB.filter(F.action == "add"))
async def adm_promo_add(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("🏷 Код промокода (например SALE20):")
    await state.set_state(AdminPromoStates.waiting_code)
    await callback.answer()


@router.message(AdminPromoStates.waiting_code)
async def adm_promo_code(message: Message, state: FSMContext):
    await state.update_data(code=message.text.strip().upper())
    await message.answer("Тип скидки:", reply_markup=admin_promo_type_kb())
    await state.set_state(AdminPromoStates.waiting_type)


@router.callback_query(PromoTypeCB.filter(), AdminPromoStates.waiting_type)
async def adm_promo_type(callback: CallbackQuery, callback_data: PromoTypeCB, state: FSMContext):
    await state.update_data(discount_type=callback_data.discount_type)
    sym = "%" if callback_data.discount_type == "percent" else "₽"
    await callback.message.edit_text(f"💰 Размер скидки ({sym}):")
    await state.set_state(AdminPromoStates.waiting_value)
    await callback.answer()


@router.message(AdminPromoStates.waiting_value)
async def adm_promo_value(message: Message, state: FSMContext):
    try:
        v = float(message.text.strip())
    except ValueError:
        await message.answer("❌ Введите число")
        return
    await state.update_data(discount_value=v)
    await message.answer("📦 Мин. сумма заказа (0 = без ограничений):")
    await state.set_state(AdminPromoStates.waiting_min_order)


@router.message(AdminPromoStates.waiting_min_order)
async def adm_promo_min(message: Message, state: FSMContext):
    try:
        mo = float(message.text.strip())
    except ValueError:
        mo = 0
    await state.update_data(min_order=mo)
    await message.answer("🔢 Макс. использований (-1 = безлимит):")
    await state.set_state(AdminPromoStates.waiting_max_uses)


@router.message(AdminPromoStates.waiting_max_uses)
async def adm_promo_max(message: Message, state: FSMContext):
    try:
        mu = int(message.text.strip())
    except ValueError:
        mu = -1
    data = await state.get_data()
    await db.add_promocode(data['code'], data['discount_type'],
                           data['discount_value'], data['min_order'], mu)
    await message.answer(f"✅ Промокод <b>{data['code']}</b> создан!", parse_mode="HTML")
    await state.clear()
    p = await db.get_all_promocodes()
    await message.answer("🏷 Промокоды:", reply_markup=admin_promos_kb(p))


# ==================== АКЦИИ ====================
@router.callback_query(F.data == "adm_promotions")
async def adm_promotions(callback: CallbackQuery):
    p = await db.get_all_promotions()
    await callback.message.edit_text(
        "🔥 <b>Акции:</b>", reply_markup=admin_promotions_kb(p), parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(AdminPromotionCB.filter(F.action == "detail"))
async def adm_promotion_detail(callback: CallbackQuery, callback_data: AdminPromotionCB):
    p = await db.get_promotion(callback_data.id)
    if not p:
        await callback.answer("Не найдена", show_alert=True)
        return

    text = f"🔥 <b>{p['title']}</b>\n\n"
    text += f"📄 {p['description'] or '—'}\n"
    text += f"💰 Скидка: {p['discount_percent']:.0f}%\n"
    text += f"{'✅ Активна' if p['is_active'] else '❌ Неактивна'}\n\n"

    apply = p['apply_to'] if p['apply_to'] else 'all'
    if apply == 'all':
        text += "📋 Применяется: <b>ко всему меню</b>"
    elif apply == 'category':
        cat = await db.get_category(p['category_id']) if p['category_id'] else None
        cat_name = f"{cat['emoji']} {cat['name']}" if cat else "?"
        text += f"📋 Применяется: <b>категория {cat_name}</b>"
    elif apply == 'product':
        prod = await db.get_product(p['product_id']) if p['product_id'] else None
        prod_name = prod['name'] if prod else "?"
        text += f"📋 Применяется: <b>товар {prod_name}</b>"

    from keyboards.admin_kb import admin_promotion_actions_kb
    await callback.message.edit_text(
        text, reply_markup=admin_promotion_actions_kb(callback_data.id), parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(AdminPromotionCB.filter(F.action == "add"))
async def adm_promotion_add(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("🔥 Название акции:")
    await state.set_state(AdminPromotionStates.waiting_title)
    await callback.answer()


@router.message(AdminPromotionStates.waiting_title)
async def adm_promotion_title(message: Message, state: FSMContext):
    await state.update_data(promo_title=message.text.strip())
    await message.answer("📄 Описание акции:")
    await state.set_state(AdminPromotionStates.waiting_description)


@router.message(AdminPromotionStates.waiting_description)
async def adm_promotion_desc(message: Message, state: FSMContext):
    await state.update_data(promo_description=message.text.strip())
    await message.answer("💰 Скидка в % (например 15):")
    await state.set_state(AdminPromotionStates.waiting_discount)


@router.message(AdminPromotionStates.waiting_discount)
async def adm_promotion_discount(message: Message, state: FSMContext):
    try:
        d = float(message.text.strip())
    except ValueError:
        d = 0
    await state.update_data(promo_discount=d)

    # Выбор на что применить
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🌐 На всё меню", callback_data="promo_apply_all")],
        [InlineKeyboardButton(text="📁 На категорию", callback_data="promo_apply_category")],
        [InlineKeyboardButton(text="🍕 На товар", callback_data="promo_apply_product")],
    ])
    await message.answer(
        "📋 <b>К чему применить акцию?</b>",
        reply_markup=kb, parse_mode="HTML"
    )


@router.callback_query(F.data == "promo_apply_all")
async def promo_apply_all(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    await db.add_promotion(
        title=data['promo_title'],
        description=data['promo_description'],
        discount_percent=data['promo_discount'],
        apply_to='all'
    )
    await callback.message.edit_text(f"✅ Акция «{data['promo_title']}» создана на всё меню!")
    await state.clear()
    p = await db.get_all_promotions()
    await callback.message.answer("🔥 Акции:", reply_markup=admin_promotions_kb(p))
    await callback.answer()


@router.callback_query(F.data == "promo_apply_category")
async def promo_apply_category(callback: CallbackQuery, state: FSMContext):
    cats = await db.get_categories(only_active=False)
    if not cats:
        await callback.answer("Нет категорий", show_alert=True)
        return

    builder = InlineKeyboardBuilder()
    for c in cats:
        builder.button(
            text=f"{c['emoji']} {c['name']}",
            callback_data=f"promo_set_cat_{c['id']}"
        )
    builder.adjust(2)

    await callback.message.edit_text(
        "📁 Выберите категорию для акции:",
        reply_markup=builder.as_markup()
    )
    await callback.answer()


@router.callback_query(F.data.startswith("promo_set_cat_"))
async def promo_set_category(callback: CallbackQuery, state: FSMContext):
    cat_id = int(callback.data.split("_")[3])
    data = await state.get_data()
    cat = await db.get_category(cat_id)

    await db.add_promotion(
        title=data['promo_title'],
        description=data['promo_description'],
        discount_percent=data['promo_discount'],
        apply_to='category',
        category_id=cat_id
    )
    await callback.message.edit_text(
        f"✅ Акция «{data['promo_title']}» создана на категорию {cat['emoji']} {cat['name']}!"
    )
    await state.clear()
    p = await db.get_all_promotions()
    await callback.message.answer("🔥 Акции:", reply_markup=admin_promotions_kb(p))
    await callback.answer()


@router.callback_query(F.data == "promo_apply_product")
async def promo_apply_product(callback: CallbackQuery, state: FSMContext):
    products = await db.get_all_products()
    if not products:
        await callback.answer("Нет товаров", show_alert=True)
        return

    builder = InlineKeyboardBuilder()
    for p in products[:30]:
        builder.button(
            text=f"{p['name']} ({p['price']:.0f}₽)",
            callback_data=f"promo_set_prod_{p['id']}"
        )
    builder.adjust(1)

    await callback.message.edit_text(
        "🍕 Выберите товар для акции:",
        reply_markup=builder.as_markup()
    )
    await callback.answer()


@router.callback_query(F.data.startswith("promo_set_prod_"))
async def promo_set_product(callback: CallbackQuery, state: FSMContext):
    prod_id = int(callback.data.split("_")[3])
    data = await state.get_data()
    prod = await db.get_product(prod_id)

    await db.add_promotion(
        title=data['promo_title'],
        description=data['promo_description'],
        discount_percent=data['promo_discount'],
        apply_to='product',
        product_id=prod_id
    )
    await callback.message.edit_text(
        f"✅ Акция «{data['promo_title']}» создана на товар {prod['name']}!"
    )
    await state.clear()
    p = await db.get_all_promotions()
    await callback.message.answer("🔥 Акции:", reply_markup=admin_promotions_kb(p))
    await callback.answer()


@router.callback_query(AdminPromotionCB.filter(F.action == "del"))
async def adm_promotion_del(callback: CallbackQuery, callback_data: AdminPromotionCB):
    await db.delete_promotion(callback_data.id)
    p = await db.get_all_promotions()
    await callback.message.edit_text(
        "🔥 <b>Акции:</b>", reply_markup=admin_promotions_kb(p), parse_mode="HTML"
    )
    await callback.answer("🗑 Удалено")


# ==================== КУРЬЕРЫ ====================
@router.callback_query(F.data == "adm_couriers")
async def adm_couriers(callback: CallbackQuery):
    c = await db.get_couriers(only_active=False)
    await callback.message.edit_text(
        "🚴 <b>Курьеры:</b>", reply_markup=admin_couriers_kb(c), parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(AdminCourierCB.filter(F.action == "detail"))
async def adm_courier_detail(callback: CallbackQuery, callback_data: AdminCourierCB):
    c = await db.get_courier(callback_data.id)
    if not c:
        await callback.answer("Не найден", show_alert=True)
        return
    text = f"🚴 <b>{c['full_name']}</b>\n📱 {c['phone']}\nID: {c['user_id']}"
    await callback.message.edit_text(
        text, reply_markup=admin_courier_actions_kb(callback_data.id), parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(AdminCourierCB.filter(F.action == "del"))
async def adm_courier_del(callback: CallbackQuery, callback_data: AdminCourierCB):
    await db.delete_courier(callback_data.id)
    c = await db.get_couriers(only_active=False)
    await callback.message.edit_text(
        "🚴 <b>Курьеры:</b>", reply_markup=admin_couriers_kb(c), parse_mode="HTML"
    )
    await callback.answer("🗑 Удалено")


@router.callback_query(AdminCourierCB.filter(F.action == "add"))
async def adm_courier_add(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("🚴 Telegram ID курьера:")
    await state.set_state(AdminCourierStates.waiting_user_id)
    await callback.answer()


@router.message(AdminCourierStates.waiting_user_id)
async def adm_courier_uid(message: Message, state: FSMContext):
    try:
        cid = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Введите числовой ID")
        return
    await state.update_data(courier_id=cid)
    await message.answer("📝 Имя курьера:")
    await state.set_state(AdminCourierStates.waiting_name)


@router.message(AdminCourierStates.waiting_name)
async def adm_courier_name(message: Message, state: FSMContext):
    await state.update_data(courier_name=message.text.strip())
    await message.answer("📱 Телефон:")
    await state.set_state(AdminCourierStates.waiting_phone)


@router.message(AdminCourierStates.waiting_phone)
async def adm_courier_phone(message: Message, state: FSMContext):
    data = await state.get_data()
    await db.add_courier(data['courier_id'], data['courier_name'], message.text.strip())
    await message.answer(f"✅ Курьер «{data['courier_name']}» добавлен!")
    await state.clear()
    c = await db.get_couriers(only_active=False)
    await message.answer("🚴 Курьеры:", reply_markup=admin_couriers_kb(c))


# ==================== НАСТРОЙКИ ====================
@router.callback_query(F.data == "adm_settings")
async def adm_settings(callback: CallbackQuery):
    s = await db.get_all_settings()
    await callback.message.edit_text(
        "⚙️ <b>Настройки:</b>\nНажмите для изменения",
        reply_markup=admin_settings_kb(s), parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(AdminSettingCB.filter())
async def adm_setting_edit(callback: CallbackQuery, callback_data: AdminSettingCB,
                           state: FSMContext):
    current = await db.get_setting(callback_data.key)
    await state.update_data(setting_key=callback_data.key)
    await callback.message.edit_text(
        f"⚙️ <b>{callback_data.key}</b>\nТекущее: <i>{current}</i>\n\nНовое значение:",
        parse_mode="HTML"
    )
    await state.set_state(AdminSettingStates.waiting_value)
    await callback.answer()


@router.message(AdminSettingStates.waiting_value)
async def adm_setting_save(message: Message, state: FSMContext):
    data = await state.get_data()
    await db.set_setting(data['setting_key'], message.text.strip())
    await message.answer(
        f"✅ <b>{data['setting_key']}</b> = <i>{message.text.strip()}</i>",
        parse_mode="HTML"
    )
    await state.clear()
    s = await db.get_all_settings()
    await message.answer("⚙️ Настройки:", reply_markup=admin_settings_kb(s))


# ==================== ЗАКАЗЫ ====================
@router.callback_query(F.data == "adm_orders")
async def adm_orders(callback: CallbackQuery):
    await callback.message.edit_text(
        "📦 <b>Фильтр заказов:</b>",
        reply_markup=admin_orders_filter_kb(), parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(AdminOrdersCB.filter())
async def adm_orders_list(callback: CallbackQuery, callback_data: AdminOrdersCB):
    st = callback_data.status
    orders = await db.get_all_orders(50) if st == "all" else await db.get_orders_by_status(st)
    if not orders:
        await callback.answer("Заказов нет", show_alert=True)
        return
    text = f"📦 <b>Заказы ({st}):</b>\n\n"
    for o in orders[:20]:
        se = order_status_emoji(o['status'])
        text += f"#{o['id']} | {se} | {format_price(o['total_price'])} | {o['user_fullname'] or '—'}\n"
    await callback.message.edit_text(
        text, reply_markup=back_kb("adm_orders"), parse_mode="HTML"
    )
    await callback.answer()


# ==================== КЛИЕНТЫ ====================
@router.callback_query(F.data == "adm_users")
async def adm_users(callback: CallbackQuery):
    users = await db.get_all_users()
    text = "👥 <b>Клиенты:</b>\n\n"
    for u in users[:30]:
        text += (
            f"👤 {u['full_name']} (@{u['username'] or '—'})\n"
            f"   📦 {u['total_orders']} заказов | 💰 {format_price(u['total_spent'])}\n\n"
        )
    await callback.message.edit_text(
        text, reply_markup=back_kb(), parse_mode="HTML"
    )
    await callback.answer()


# ==================== СТАТИСТИКА ====================
@router.callback_query(F.data == "adm_stats")
async def adm_stats(callback: CallbackQuery):
    today = await db.get_today_stats()
    uc = await db.get_users_count()
    all_o = await db.get_all_orders(limit=99999)
    total_rev = sum(o['total_price'] for o in all_o)
    completed = sum(1 for o in all_o if o['status'] == 'completed')
    cnt = len(all_o) or 1
    text = (
        "📊 <b>Статистика</b>\n\n"
        f"📅 <b>Сегодня:</b>\n"
        f"   Заказов: {today[0]}\n"
        f"   Выручка: {format_price(today[1])}\n\n"
        f"📈 <b>Всего:</b>\n"
        f"   Заказов: {len(all_o)}\n"
        f"   Завершённых: {completed}\n"
        f"   Выручка: {format_price(total_rev)}\n"
        f"   Клиентов: {uc}\n"
        f"   Ср. чек: {format_price(total_rev / cnt)}"
    )
    await callback.message.edit_text(text, reply_markup=back_kb(), parse_mode="HTML")
    await callback.answer()


# ==================== РАССЫЛКА ====================
@router.callback_query(F.data == "adm_broadcast")
async def adm_broadcast(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("📢 Текст рассылки:")
    await state.set_state(AdminBroadcastStates.waiting_message)
    await callback.answer()


@router.message(AdminBroadcastStates.waiting_message)
async def adm_broadcast_text(message: Message, state: FSMContext):
    await state.update_data(broadcast_text=message.text)
    uc = await db.get_users_count()
    await message.answer(
        f"📢 <b>Превью:</b>\n\n{message.text}\n\n"
        f"Получателей: <b>{uc}</b>",
        reply_markup=admin_broadcast_confirm_kb(), parse_mode="HTML"
    )
    await state.set_state(AdminBroadcastStates.confirming)


@router.callback_query(F.data == "adm_broadcast_yes", AdminBroadcastStates.confirming)
async def adm_broadcast_send(callback: CallbackQuery, state: FSMContext, bot: Bot):
    import asyncio
    data = await state.get_data()
    text = data['broadcast_text']
    users = await db.get_all_users()
    sent = failed = skipped = 0
    for u in users:
        # Fix bug 7: skip banned users
        if u['is_banned']:
            skipped += 1
            continue
        try:
            await bot.send_message(u['user_id'], text, parse_mode="HTML")
            sent += 1
            # Fix bug 7: rate limit ~20 msg/sec to avoid Telegram flood ban
            await asyncio.sleep(0.05)
        except Exception:
            failed += 1
    await callback.message.edit_text(
        f"✅ Рассылка завершена!\n📤 Отправлено: {sent}\n"
        f"❌ Ошибок: {failed}\n⏭ Пропущено (бан): {skipped}"
    )
    await state.clear()
    await callback.answer()


@router.callback_query(F.data == "adm_broadcast_no", AdminBroadcastStates.confirming)
async def adm_broadcast_cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ Рассылка отменена")
    await callback.answer()


# ==================== НАСТРОЙКИ АНАЛИТИКИ ====================
@router.callback_query(F.data == "adm_analytics")
async def adm_analytics_redirect(callback: CallbackQuery):
    """Перенаправляем на роутер аналитики."""
    # Handled by analytics router - this just makes sure adm_back works
    from handlers.analytics import adm_analytics
    await adm_analytics(callback)


@router.callback_query(F.data == "adm_analytics_settings")
async def adm_analytics_settings(callback: CallbackQuery):
    enabled = await db.get_setting("analytics_daily_report")
    hour = await db.get_setting("analytics_report_hour") or "23"
    status = "✅ Включён" if enabled == "1" else "❌ Выключен"
    builder = InlineKeyboardBuilder()
    toggle = "Выключить" if enabled == "1" else "Включить"
    builder.row(InlineKeyboardButton(
        text=f"{'🔴' if enabled == '1' else '🟢'} {toggle} авто-отчёт",
        callback_data="analytics_toggle_report"
    ))
    builder.row(
        InlineKeyboardButton(text="⬅️ Назад", callback_data="adm_back")
    )
    await callback.message.edit_text(
        f"⚙️ <b>Настройки аналитики</b>\n\n"
        f"📊 Ежедневный отчёт: <b>{status}</b>\n"
        f"🕙 Время отправки: <b>{hour}:00</b>",
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "analytics_toggle_report")
async def analytics_toggle_report(callback: CallbackQuery):
    current = await db.get_setting("analytics_daily_report")
    new_val = "0" if current == "1" else "1"
    await db.set_setting("analytics_daily_report", new_val)
    await adm_analytics_settings(callback)


# ==================== НАСТРОЙКИ ИЗБРАННОГО ====================
@router.callback_query(F.data == "adm_favorites_settings")
async def adm_favorites_settings(callback: CallbackQuery):
    enabled = await db.get_setting("favorites_enabled")
    max_items = await db.get_setting("favorites_max_items") or "50"
    status = "✅ Включено" if enabled == "1" else "❌ Выключено"
    builder = InlineKeyboardBuilder()
    toggle = "Выключить" if enabled == "1" else "Включить"
    builder.row(InlineKeyboardButton(
        text=f"{'🔴' if enabled == '1' else '🟢'} {toggle} избранное",
        callback_data="fav_settings_toggle"
    ))
    builder.row(InlineKeyboardButton(
        text=f"📝 Макс. товаров: {max_items}",
        callback_data="fav_settings_max"
    ))
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="adm_back"))
    await callback.message.edit_text(
        f"⚙️ <b>Настройки избранного</b>\n\n"
        f"❤️ Статус: <b>{status}</b>\n"
        f"📦 Макс. товаров в избранном: <b>{max_items}</b>",
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "fav_settings_toggle")
async def fav_settings_toggle(callback: CallbackQuery):
    current = await db.get_setting("favorites_enabled")
    await db.set_setting("favorites_enabled", "0" if current == "1" else "1")
    await adm_favorites_settings(callback)


@router.callback_query(F.data == "fav_settings_max")
async def fav_settings_max(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "📝 Введите максимальное количество товаров в избранном (1-200):"
    )
    await state.set_state(AdminSettingStates.waiting_value)
    await state.update_data(setting_key="favorites_max_items",
                             setting_back="adm_favorites_settings")
    await callback.answer()


# ==================== НАСТРОЙКИ ГЕОЛОКАЦИИ ====================
@router.callback_query(F.data == "adm_geo_settings")
async def adm_geo_settings(callback: CallbackQuery):
    enabled = await db.get_setting("geo_enabled")
    provider = await db.get_setting("geo_provider") or "osm"
    yandex_key = await db.get_setting("geo_yandex_key") or ""
    status = "✅ Включена" if enabled == "1" else "❌ Выключена"
    prov_name = "Яндекс.Карты" if provider == "yandex" else "OpenStreetMap (бесплатно)"
    builder = InlineKeyboardBuilder()
    toggle = "Выключить" if enabled == "1" else "Включить"
    builder.row(InlineKeyboardButton(
        text=f"{'🔴' if enabled == '1' else '🟢'} {toggle} геолокацию",
        callback_data="geo_settings_toggle"
    ))
    builder.row(
        InlineKeyboardButton(
            text="🗺 OSM (бесплатно)" if provider != "osm" else "✅ OSM (бесплатно)",
            callback_data="geo_set_osm"
        ),
        InlineKeyboardButton(
            text="🗺 Яндекс" if provider != "yandex" else "✅ Яндекс",
            callback_data="geo_set_yandex"
        )
    )
    if provider == "yandex":
        key_display = yandex_key[:8] + "..." if len(yandex_key) > 8 else (yandex_key or "не задан")
        builder.row(InlineKeyboardButton(
            text=f"🔑 API ключ: {key_display}",
            callback_data="geo_set_yandex_key"
        ))
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="adm_back"))
    await callback.message.edit_text(
        f"⚙️ <b>Настройки геолокации</b>\n\n"
        f"📍 Статус: <b>{status}</b>\n"
        f"🗺 Провайдер: <b>{prov_name}</b>",
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "geo_settings_toggle")
async def geo_settings_toggle(callback: CallbackQuery):
    current = await db.get_setting("geo_enabled")
    await db.set_setting("geo_enabled", "0" if current == "1" else "1")
    await adm_geo_settings(callback)


@router.callback_query(F.data == "geo_set_osm")
async def geo_set_osm(callback: CallbackQuery):
    await db.set_setting("geo_provider", "osm")
    await adm_geo_settings(callback)


@router.callback_query(F.data == "geo_set_yandex")
async def geo_set_yandex(callback: CallbackQuery):
    await db.set_setting("geo_provider", "yandex")
    await adm_geo_settings(callback)


@router.callback_query(F.data == "geo_set_yandex_key")
async def geo_set_yandex_key(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "🔑 Введите API ключ Яндекс.Геокодера:\n\n"
        "Получить ключ: https://developer.tech.yandex.ru/"
    )
    await state.set_state(AdminSettingStates.waiting_value)
    await state.update_data(setting_key="geo_yandex_key",
                             setting_back="adm_geo_settings")
    await callback.answer()