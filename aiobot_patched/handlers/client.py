from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart
from aiogram.utils.keyboard import InlineKeyboardBuilder
from database.db import db
from keyboards.client_kb import (
    main_menu_kb, categories_kb, products_kb,
    order_status_emoji, reorder_kb
)
from keyboards.callbacks import (
    CategoryCB, ProductCB, ProductPageCB, ClientModCB, CartActionCB
)
from texts.messages import Msg
from texts.buttons import Btn
from utils.helpers import format_price
from aiogram.types import InlineKeyboardButton
import json

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message):
    welcome = await db.get_setting("welcome_message") or Msg.WELCOME
    cnt = await db.get_cart_count(message.from_user.id)
    await message.answer(welcome, reply_markup=main_menu_kb(cnt))


@router.message(F.text == Btn.MENU)
async def show_menu(message: Message):
    cats = await db.get_categories()
    if not cats:
        await message.answer(Msg.NO_CATEGORIES)
        return
    await message.answer(Msg.CHOOSE_CATEGORY, reply_markup=categories_kb(cats),
                         parse_mode="HTML")


@router.callback_query(F.data == "back_categories")
async def back_to_categories(callback: CallbackQuery):
    cats = await db.get_categories()
    if not cats:
        await callback.message.edit_text(Msg.NO_CATEGORIES)
        return
    await callback.message.edit_text(
        Msg.CHOOSE_CATEGORY, reply_markup=categories_kb(cats), parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(CategoryCB.filter())
async def show_category(callback: CallbackQuery, callback_data: CategoryCB):
    cat_id = callback_data.id
    cat = await db.get_category(cat_id)
    prods = await db.get_products(cat_id)
    if not prods:
        await callback.answer(Msg.NO_PRODUCTS, show_alert=True)
        return
    text = f"{cat['emoji']} <b>{cat['name']}</b>\n\nВыберите блюдо:"
    await callback.message.edit_text(
        text, reply_markup=products_kb(prods, cat_id), parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(ProductPageCB.filter())
async def product_page(callback: CallbackQuery, callback_data: ProductPageCB):
    cat_id = callback_data.cat_id
    page = callback_data.page
    cat = await db.get_category(cat_id)
    prods = await db.get_products(cat_id)
    text = f"{cat['emoji']} <b>{cat['name']}</b>\n\nВыберите блюдо:"
    await callback.message.edit_text(
        text, reply_markup=products_kb(prods, cat_id, page), parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(ProductCB.filter())
async def show_product(callback: CallbackQuery, callback_data: ProductCB):
    prod = await db.get_product(callback_data.id)
    if not prod:
        await callback.answer("Товар не найден", show_alert=True)
        return

    groups = await db.get_product_full_modifiers(callback_data.id)

    # Проверяем акции для товара
    promos = await db.get_promotions_for_product(prod['id'], prod['category_id'])

    text = (
        f"<b>{prod['name']}</b>\n\n"
        f"{prod['description'] or ''}\n\n"
        f"💰 Цена: <b>{format_price(prod['price'])}</b>"
    )

    # Показываем акцию
    if promos:
        best = promos[0]
        if best['discount_percent'] > 0:
            discounted = prod['price'] * (1 - best['discount_percent'] / 100)
            text = (
                f"<b>{prod['name']}</b>\n\n"
                f"{prod['description'] or ''}\n\n"
                f"💰 Цена: <s>{format_price(prod['price'])}</s> "
                f"<b>{format_price(discounted)}</b>\n"
                f"🔥 <b>{best['title']}</b> (-{best['discount_percent']:.0f}%)"
            )

    if groups:
        text += "\n\n⚙️ <b>Настройте под себя:</b>"
        for g_data in groups:
            g = g_data["group"]
            opts = g_data["options"]
            opt_names = []
            for o in opts:
                if o['is_available']:
                    p = f" +{format_price(o['price_change'])}" if o['price_change'] > 0 else ""
                    opt_names.append(f"{o['name']}{p}")
            if opt_names:
                req = "⚠️" if g['is_required'] else ""
                text += f"\n{req} {g['name']}: {', '.join(opt_names)}"

    kb = _product_detail_kb(prod['id'], prod['category_id'], bool(groups),
                             await db.is_favorite(callback.from_user.id, prod['id']))

    if prod['image_url']:
        try:
            await callback.message.delete()
            await callback.message.answer_photo(
                photo=prod['image_url'], caption=text,
                reply_markup=kb, parse_mode="HTML"
            )
            await callback.answer()
            return
        except Exception:
            pass
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()


def _product_detail_kb(product_id: int, category_id: int, has_modifiers: bool,
                        is_fav: bool = False):
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()

    if has_modifiers:
        builder.row(InlineKeyboardButton(
            text="🛒 Добавить (настроить)",
            callback_data=ClientModCB(action="start", product_id=product_id).pack()
        ))
    else:
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

    fav_text = "💔 Убрать из избранного" if is_fav else "❤️ В избранное"
    builder.row(InlineKeyboardButton(
        text=fav_text,
        callback_data=f"fav_toggle_{product_id}"
    ))

    builder.row(InlineKeyboardButton(
        text="⬅️ Назад",
        callback_data=CategoryCB(id=category_id).pack()
    ))
    return builder.as_markup()


@router.callback_query(F.data == "noop")
async def noop(callback: CallbackQuery):
    await callback.answer()


@router.message(F.text == Btn.PROMOS)
async def show_promotions(message: Message):
    promos = await db.get_active_promotions()
    if not promos:
        await message.answer(Msg.NO_PROMOS)
        return
    for p in promos:
        text = f"🔥 <b>{p['title']}</b>\n\n{p['description'] or ''}"
        if p['discount_percent'] > 0:
            text += f"\n\n💰 Скидка: <b>{p['discount_percent']:.0f}%</b>"

            # Показываем к чему применяется
            apply = p['apply_to'] if p['apply_to'] else 'all'
            if apply == 'all':
                text += "\n📋 На всё меню"
            elif apply == 'category' and p['category_id']:
                cat = await db.get_category(p['category_id'])
                if cat:
                    text += f"\n📋 На категорию: {cat['emoji']} {cat['name']}"
            elif apply == 'product' and p['product_id']:
                prod = await db.get_product(p['product_id'])
                if prod:
                    text += f"\n📋 На товар: {prod['name']}"

        if p['image_url']:
            try:
                await message.answer_photo(p['image_url'], caption=text, parse_mode="HTML")
                continue
            except Exception:
                pass
        await message.answer(text, parse_mode="HTML")


@router.message(F.text == Btn.MY_ORDERS)
async def show_my_orders(message: Message):
    orders = await db.get_user_orders(message.from_user.id, limit=5)
    if not orders:
        await message.answer(Msg.NO_ORDERS)
        return
    text = "📋 <b>Ваши последние заказы:</b>\n\n"
    for o in orders:
        st = order_status_emoji(o['status'])
        text += (
            f"📦 <b>Заказ #{o['id']}</b>\n"
            f"   {st}\n"
            f"   💰 {format_price(o['total_price'])}\n"
            f"   📅 {o['created_at']}\n\n"
        )
    last = orders[0]
    await message.answer(text, reply_markup=reorder_kb(last['id']), parse_mode="HTML")


@router.callback_query(F.data.startswith("reorder_"))
async def reorder(callback: CallbackQuery):
    order_id = int(callback.data.split("_")[1])
    order = await db.get_order(order_id)
    if not order or order['user_id'] != callback.from_user.id:
        await callback.answer("❌ Заказ не найден", show_alert=True)
        return
    items = json.loads(order['items_json'])
    await db.clear_cart(callback.from_user.id)
    added = 0
    unavailable = []
    for item in items:
        cursor = await db._conn.execute(
            "SELECT id, is_available FROM products WHERE name = ?", (item['name'],)
        )
        product = await cursor.fetchone()
        if product and product[1]:
            mods = item.get('modifiers_data', {})
            mods_json = json.dumps(mods, ensure_ascii=False) if mods else "{}"
            await db.add_to_cart(callback.from_user.id, product[0], item['quantity'], mods_json)
            added += 1
        else:
            unavailable.append(item['name'])
    text = f"✅ Добавлено {added} позиций"
    if unavailable:
        text += f"\n❌ Недоступны: {', '.join(unavailable)}"
    await callback.answer(text, show_alert=True)


@router.message(F.text == Btn.ABOUT)
async def about_us(message: Message):
    await message.answer(
        "🏪 <b>Наша доставка</b>\n\n"
        "Мы готовим с любовью и доставляем быстро!",
        parse_mode="HTML"
    )


@router.message(F.text == Btn.CONTACTS)
async def contacts(message: Message):
    start = await db.get_setting("work_hours_start") or "09:00"
    end = await db.get_setting("work_hours_end") or "23:00"
    addr = await db.get_setting("pickup_address") or ""
    await message.answer(
        f"📞 <b>Контакты</b>\n\n"
        f"⏰ Время работы: {start} — {end}\n"
        f"📍 Адрес: {addr}",
        parse_mode="HTML"
    )