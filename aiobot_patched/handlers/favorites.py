"""
Feature F: Избранное (Wishlist)
Позволяет пользователям добавлять товары в избранное и быстро заказывать их.
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton

from database.db import db
from keyboards.callbacks import ProductCB, CartActionCB, CategoryCB
from texts.buttons import Btn
from utils.helpers import format_price

router = Router()


# ==================== КЛАВИАТУРЫ ====================

def favorites_kb(products):
    """Клавиатура списка избранного."""
    builder = InlineKeyboardBuilder()
    for p in products:
        builder.row(InlineKeyboardButton(
            text=f"❤️ {p['name']} — {format_price(p['price'])}",
            callback_data=f"fav_view_{p['id']}"
        ))
    builder.row(InlineKeyboardButton(
        text="🗑 Очистить избранное", callback_data="fav_clear"
    ))
    return builder.as_markup()


def product_fav_toggle_kb(product_id: int, category_id: int,
                           is_fav: bool, has_modifiers: bool):
    """Кнопки на карточке товара с кнопкой избранного."""
    builder = InlineKeyboardBuilder()
    fav_text = "💔 Убрать из избранного" if is_fav else "❤️ В избранное"
    builder.row(InlineKeyboardButton(
        text=fav_text,
        callback_data=f"fav_toggle_{product_id}"
    ))
    if has_modifiers:
        from keyboards.callbacks import ClientModCB
        builder.row(InlineKeyboardButton(
            text="🛒 Добавить (настроить)",
            callback_data=ClientModCB(action="start", product_id=product_id).pack()
        ))
    else:
        builder.row(
            InlineKeyboardButton(
                text="➕ В корзину",
                callback_data=CartActionCB(action="add", product_id=product_id).pack()
            )
        )
    builder.row(InlineKeyboardButton(
        text="⬅️ Назад к избранному", callback_data="fav_list"
    ))
    return builder.as_markup()


# ==================== ХЕНДЛЕРЫ ====================

@router.message(F.text == Btn.FAVORITES)
async def show_favorites(message: Message):
    fav_enabled = await db.get_setting("favorites_enabled")
    if fav_enabled != "1":
        await message.answer("❤️ Функция избранного отключена.")
        return
    products = await db.get_favorites(message.from_user.id)
    if not products:
        await message.answer(
            "❤️ <b>Ваше избранное пусто</b>\n\n"
            "Откройте карточку товара и нажмите ❤️ чтобы добавить.",
            parse_mode="HTML"
        )
        return
    await message.answer(
        f"❤️ <b>Избранное ({len(products)} товаров):</b>",
        reply_markup=favorites_kb(products),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "fav_list")
async def fav_list_callback(callback: CallbackQuery):
    products = await db.get_favorites(callback.from_user.id)
    if not products:
        await callback.message.edit_text(
            "❤️ <b>Ваше избранное пусто</b>", parse_mode="HTML"
        )
        await callback.answer()
        return
    await callback.message.edit_text(
        f"❤️ <b>Избранное ({len(products)} товаров):</b>",
        reply_markup=favorites_kb(products),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("fav_view_"))
async def fav_view_product(callback: CallbackQuery):
    product_id = int(callback.data.split("_")[2])
    prod = await db.get_product(product_id)
    if not prod:
        await callback.answer("Товар недоступен", show_alert=True)
        return
    groups = await db.get_product_full_modifiers(product_id)
    is_fav = await db.is_favorite(callback.from_user.id, product_id)
    text = (
        f"<b>{prod['name']}</b>\n\n"
        f"{prod['description'] or ''}\n\n"
        f"💰 Цена: <b>{format_price(prod['price'])}</b>"
    )
    kb = product_fav_toggle_kb(product_id, prod['category_id'], is_fav, bool(groups))
    if prod['image_url']:
        try:
            await callback.message.delete()
            await callback.message.answer_photo(
                photo=prod['image_url'], caption=text, reply_markup=kb, parse_mode="HTML"
            )
            await callback.answer()
            return
        except Exception:
            pass
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("fav_toggle_"))
async def fav_toggle(callback: CallbackQuery):
    fav_enabled = await db.get_setting("favorites_enabled")
    if fav_enabled != "1":
        await callback.answer("Функция избранного отключена", show_alert=True)
        return

    product_id = int(callback.data.split("_")[2])
    user_id = callback.from_user.id
    is_fav = await db.is_favorite(user_id, product_id)

    if is_fav:
        await db.remove_favorite(user_id, product_id)
        await callback.answer("💔 Удалено из избранного")
    else:
        max_items = int(await db.get_setting("favorites_max_items") or 50)
        count = await db.get_favorites_count(user_id)
        if count >= max_items:
            await callback.answer(
                f"❌ Максимум {max_items} товаров в избранном", show_alert=True
            )
            return
        await db.add_favorite(user_id, product_id)
        await callback.answer("❤️ Добавлено в избранное!")

    # Обновляем кнопку
    prod = await db.get_product(product_id)
    groups = await db.get_product_full_modifiers(product_id)
    new_is_fav = await db.is_favorite(user_id, product_id)
    kb = product_fav_toggle_kb(product_id, prod['category_id'] if prod else 0,
                                new_is_fav, bool(groups))
    try:
        await callback.message.edit_reply_markup(reply_markup=kb)
    except Exception:
        pass


@router.callback_query(F.data == "fav_clear")
async def fav_clear(callback: CallbackQuery):
    user_id = callback.from_user.id
    await db._conn.execute("DELETE FROM favorites WHERE user_id = ?", (user_id,))
    await db._conn.commit()
    await callback.message.edit_text(
        "❤️ <b>Избранное очищено</b>", parse_mode="HTML"
    )
    await callback.answer("🗑 Очищено")
