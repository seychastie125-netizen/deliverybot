from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from database.db import db
from keyboards.client_kb import cart_kb, empty_cart_kb, main_menu_kb
from keyboards.callbacks import CartActionCB
from texts.buttons import Btn
from utils.helpers import format_price
from utils.modifiers import parse_modifiers_price, format_modifiers_text

router = Router()


def _item_price_with_mods(item) -> float:
    """Считает цену позиции с учётом модификаторов."""
    return item['price'] + parse_modifiers_price(item['modifiers_json'])


async def _refresh_menu(target, user_id: int):
    """Обновляет reply-клавиатуру с актуальным счётчиком корзины.

    Reply-клавиатура в Telegram привязана к чату, а не к конкретному сообщению —
    она остаётся видимой пока не будет заменена следующим ReplyKeyboard/Remove.
    Удалять сообщение-носитель нельзя: клавиатура исчезнет вместе с ним.
    """
    cnt = await db.get_cart_count(user_id)
    kb = main_menu_kb(cnt)
    if isinstance(target, CallbackQuery):
        await target.message.answer(
            f"🛒 В корзине: {cnt} шт." if cnt > 0 else "🛒 Корзина пуста",
            reply_markup=kb
        )
    else:
        await target.answer(
            f"🛒 В корзине: {cnt} шт." if cnt > 0 else "🛒 Корзина пуста",
            reply_markup=kb
        )


async def _show_cart(target, user_id: int, edit: bool = False):
    items = await db.get_cart(user_id)
    if not items:
        text = "🛒 Ваша корзина пуста"
        kb = empty_cart_kb()
    else:
        total = 0
        lines = []
        for i in items:
            item_price = _item_price_with_mods(i)
            s = item_price * i['quantity']
            total += s
            mods_text = format_modifiers_text(i['modifiers_json'])
            lines.append(
                f"  {i['name']}{mods_text} x{i['quantity']} = {format_price(s)}"
            )
        text = (
            "🛒 <b>Ваша корзина:</b>\n\n"
            + "\n".join(lines)
            + f"\n\n💰 <b>Итого: {format_price(total)}</b>"
        )
        kb = cart_kb(items)

    if edit and isinstance(target, CallbackQuery):
        try:
            await target.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
        except Exception:
            await target.message.answer(text, reply_markup=kb, parse_mode="HTML")
    elif isinstance(target, Message):
        await target.answer(text, reply_markup=kb, parse_mode="HTML")
    else:
        await target.message.answer(text, reply_markup=kb, parse_mode="HTML")


@router.message(F.text.startswith(Btn.CART))
async def cmd_cart(message: Message):
    await _show_cart(message, message.from_user.id)


@router.callback_query(CartActionCB.filter(F.action == "add"))
async def cart_add(callback: CallbackQuery, callback_data: CartActionCB, state: FSMContext):
    prod = await db.get_product(callback_data.product_id)
    if not prod:
        await callback.answer("Товар не найден", show_alert=True)
        return

    groups = await db.get_product_full_modifiers(callback_data.product_id)
    if groups:
        from keyboards.callbacks import ClientModCB
        from handlers.client_modifiers import start_modifiers
        fake_data = ClientModCB(action="start", product_id=callback_data.product_id)
        await start_modifiers(callback, fake_data, state)
        return

    await db.add_to_cart(callback.from_user.id, callback_data.product_id, 1, "{}")
    cnt = await db.get_cart_count(callback.from_user.id)
    await _refresh_menu(callback, callback.from_user.id)
    await callback.answer(f"✅ {prod['name']} добавлен! (в корзине: {cnt})")


@router.callback_query(CartActionCB.filter(F.action == "plus"))
async def cart_plus(callback: CallbackQuery, callback_data: CartActionCB, state: FSMContext):
    groups = await db.get_product_full_modifiers(callback_data.product_id)
    if groups:
        from keyboards.callbacks import ClientModCB
        from handlers.client_modifiers import start_modifiers
        fake_data = ClientModCB(action="start", product_id=callback_data.product_id)
        await start_modifiers(callback, fake_data, state)
        return

    await db.add_to_cart(callback.from_user.id, callback_data.product_id, 1, "{}")
    cnt = await db.get_cart_count(callback.from_user.id)
    await _refresh_menu(callback, callback.from_user.id)
    await callback.answer(f"➕ (в корзине: {cnt})")


@router.callback_query(CartActionCB.filter(F.action == "minus"))
async def cart_minus(callback: CallbackQuery, callback_data: CartActionCB):
    await db.add_to_cart(callback.from_user.id, callback_data.product_id, -1, "{}")
    await _refresh_menu(callback, callback.from_user.id)
    cnt = await db.get_cart_count(callback.from_user.id)
    await callback.answer(f"➖ (в корзине: {cnt})")


@router.callback_query(CartActionCB.filter(F.action == "inc"))
async def cart_inc(callback: CallbackQuery, callback_data: CartActionCB):
    user_id = callback.from_user.id
    items = await db.get_cart(user_id)
    for i in items:
        if i['id'] == callback_data.item_id:
            await db.update_cart_item(callback_data.item_id, i['quantity'] + 1, user_id)
            break
    await _refresh_menu(callback, user_id)
    await _show_cart(callback, user_id, edit=True)
    await callback.answer()


@router.callback_query(CartActionCB.filter(F.action == "dec"))
async def cart_dec(callback: CallbackQuery, callback_data: CartActionCB):
    user_id = callback.from_user.id
    items = await db.get_cart(user_id)
    for i in items:
        if i['id'] == callback_data.item_id:
            nq = i['quantity'] - 1
            await db.update_cart_item(callback_data.item_id, nq, user_id)
            break
    await _refresh_menu(callback, user_id)
    await _show_cart(callback, user_id, edit=True)
    await callback.answer()


@router.callback_query(CartActionCB.filter(F.action == "remove"))
async def cart_remove(callback: CallbackQuery, callback_data: CartActionCB):
    await db.remove_from_cart(callback_data.item_id, callback.from_user.id)
    await _refresh_menu(callback, callback.from_user.id)
    await _show_cart(callback, callback.from_user.id, edit=True)
    await callback.answer("🗑 Удалено")


@router.callback_query(CartActionCB.filter(F.action == "clear"))
async def cart_clear(callback: CallbackQuery):
    await db.clear_cart(callback.from_user.id)
    await _refresh_menu(callback, callback.from_user.id)
    await _show_cart(callback, callback.from_user.id, edit=True)
    await callback.answer("🗑 Корзина очищена")
