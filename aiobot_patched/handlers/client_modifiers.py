from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from database.db import db
from keyboards.callbacks import ClientModCB
from states.states import ClientModifierStates
from utils.helpers import format_price
import json

router = Router()


@router.callback_query(ClientModCB.filter(F.action == "start"))
async def start_modifiers(callback: CallbackQuery, callback_data: ClientModCB,
                          state: FSMContext):
    product_id = callback_data.product_id
    groups = await db.get_product_full_modifiers(product_id)

    if not groups:
        await db.add_to_cart(callback.from_user.id, product_id, 1, "{}")
        cnt = await db.get_cart_count(callback.from_user.id)
        product = await db.get_product(product_id)
        await callback.answer(f"✅ {product['name']} добавлен! (в корзине: {cnt})")
        return

    selections = {}
    for g_data in groups:
        g = g_data["group"]
        gid = str(g['id'])
        defaults = [
            opt['id'] for opt in g_data["options"]
            if opt['is_default'] and opt['is_available']
        ]
        if g['is_multiple']:
            selections[gid] = defaults
        else:
            selections[gid] = defaults[0] if defaults else None

    await state.update_data(
        mod_product_id=product_id,
        mod_selections=selections,
        mod_current_group=0
    )
    await state.set_state(ClientModifierStates.selecting_modifiers)
    await _show_modifier_step(callback, state)
    await callback.answer()


async def _show_modifier_step(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    product_id = data['mod_product_id']
    selections = data['mod_selections']
    current_idx = data['mod_current_group']

    product = await db.get_product(product_id)
    groups = await db.get_product_full_modifiers(product_id)

    # Все группы пройдены — итог
    if current_idx >= len(groups):
        await _show_modifier_summary(callback, state)
        return

    g_data = groups[current_idx]
    g = g_data["group"]
    options = g_data["options"]
    gid = str(g['id'])

    req = "⚠️ Обязательно" if g['is_required'] else "Необязательно"
    if g['is_multiple']:
        mult_text = f" (можно несколько, макс. {g['max_select']})"
    else:
        mult_text = " (выберите один)"

    text = (
        f"🍕 <b>{product['name']}</b> — {format_price(product['price'])}\n\n"
        f"📦 <b>{g['name']}</b>\n"
        f"{req}{mult_text}\n\n"
        f"Шаг {current_idx + 1} из {len(groups)}"
    )

    builder = InlineKeyboardBuilder()
    current_selection = selections.get(gid)

    for opt in options:
        if not opt['is_available']:
            continue

        if g['is_multiple']:
            selected = opt['id'] in (current_selection if isinstance(current_selection, list) else [])
        else:
            selected = current_selection == opt['id']

        check = "✅" if selected else "⬜"
        price_text = ""
        if opt['price_change'] > 0:
            price_text = f" (+{format_price(opt['price_change'])})"
        elif opt['price_change'] < 0:
            price_text = f" ({format_price(opt['price_change'])})"

        builder.button(
            text=f"{check} {opt['name']}{price_text}",
            callback_data=ClientModCB(
                action="toggle",
                product_id=product_id,
                group_id=g['id'],
                option_id=opt['id']
            ).pack()
        )

    builder.adjust(1)

    # Навигация
    nav = []
    if current_idx > 0:
        nav.append(InlineKeyboardButton(
            text="◀️ Назад",
            callback_data=ClientModCB(action="prev", product_id=product_id).pack()
        ))

    # Кнопка "Далее" / "Готово" — показываем если:
    # - Группа необязательная (можно пропустить)
    # - Или уже выбран хотя бы один вариант (для обязательной)
    can_proceed = False
    if not g['is_required']:
        can_proceed = True
    else:
        if g['is_multiple']:
            sel_list = current_selection if isinstance(current_selection, list) else []
            can_proceed = len(sel_list) >= g['min_select']
        else:
            can_proceed = current_selection is not None

    if can_proceed:
        is_last = current_idx >= len(groups) - 1
        nav.append(InlineKeyboardButton(
            text="✅ Готово" if is_last else "Далее ▶️",
            callback_data=ClientModCB(action="next", product_id=product_id).pack()
        ))

    if nav:
        builder.row(*nav)

    builder.row(InlineKeyboardButton(
        text="❌ Отмена",
        callback_data=ClientModCB(action="cancel", product_id=product_id).pack()
    ))

    try:
        await callback.message.edit_text(
            text, reply_markup=builder.as_markup(), parse_mode="HTML"
        )
    except Exception:
        await callback.message.answer(
            text, reply_markup=builder.as_markup(), parse_mode="HTML"
        )


@router.callback_query(ClientModCB.filter(F.action == "toggle"),
                       ClientModifierStates.selecting_modifiers)
async def toggle_modifier(callback: CallbackQuery, callback_data: ClientModCB,
                          state: FSMContext):
    data = await state.get_data()
    selections = data['mod_selections']
    group_id = callback_data.group_id
    option_id = callback_data.option_id
    gid = str(group_id)

    group = await db.get_modifier_group(group_id)

    if group['is_multiple']:
        current = selections.get(gid, [])
        if not isinstance(current, list):
            current = []
        if option_id in current:
            current.remove(option_id)
        else:
            if len(current) < group['max_select']:
                current.append(option_id)
            else:
                await callback.answer(
                    f"❌ Максимум {group['max_select']} выборов", show_alert=True
                )
                return
        selections[gid] = current
    else:
        if selections.get(gid) == option_id:
            if not group['is_required']:
                selections[gid] = None
        else:
            selections[gid] = option_id

    await state.update_data(mod_selections=selections)
    await _show_modifier_step(callback, state)
    await callback.answer()


@router.callback_query(ClientModCB.filter(F.action == "next"),
                       ClientModifierStates.selecting_modifiers)
async def next_group(callback: CallbackQuery, callback_data: ClientModCB,
                     state: FSMContext):
    data = await state.get_data()
    product_id = data['mod_product_id']
    current_idx = data['mod_current_group']
    selections = data['mod_selections']

    groups = await db.get_product_full_modifiers(product_id)

    # Защита от выхода за границы
    if current_idx >= len(groups):
        await _show_modifier_summary(callback, state)
        return

    g_data = groups[current_idx]
    g = g_data["group"]
    gid = str(g['id'])

    # Валидация текущей группы
    current_sel = selections.get(gid)
    if g['is_required']:
        if g['is_multiple']:
            sel_list = current_sel if isinstance(current_sel, list) else []
            if len(sel_list) < g['min_select']:
                await callback.answer(
                    f"⚠️ Выберите минимум {g['min_select']}",
                    show_alert=True
                )
                return
        else:
            if current_sel is None:
                await callback.answer("⚠️ Выберите вариант", show_alert=True)
                return

    new_idx = current_idx + 1
    await state.update_data(mod_current_group=new_idx)

    # Если новый индекс >= len(groups) — _show_modifier_step сам вызовет summary
    await _show_modifier_step(callback, state)
    await callback.answer()


@router.callback_query(ClientModCB.filter(F.action == "prev"),
                       ClientModifierStates.selecting_modifiers)
async def prev_group(callback: CallbackQuery, callback_data: ClientModCB,
                     state: FSMContext):
    data = await state.get_data()
    current_idx = max(0, data['mod_current_group'] - 1)
    await state.update_data(mod_current_group=current_idx)
    await _show_modifier_step(callback, state)
    await callback.answer()


@router.callback_query(ClientModCB.filter(F.action == "cancel"),
                       ClientModifierStates.selecting_modifiers)
async def cancel_modifiers(callback: CallbackQuery, callback_data: ClientModCB,
                           state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ Выбор модификаторов отменён")
    await callback.answer()


async def _show_modifier_summary(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    product_id = data['mod_product_id']
    selections = data['mod_selections']

    product = await db.get_product(product_id)
    groups = await db.get_product_full_modifiers(product_id)

    mods_data = {}
    extra_price = 0
    summary_lines = []

    for g_data in groups:
        g = g_data["group"]
        gid = str(g['id'])
        sel = selections.get(gid)

        if g['is_multiple']:
            if not sel or not isinstance(sel, list) or len(sel) == 0:
                continue
            opts = []
            for opt_id in sel:
                opt = await db.get_modifier_option(opt_id)
                if opt:
                    opts.append({
                        "id": opt['id'],
                        "name": opt['name'],
                        "price": opt['price_change']
                    })
                    extra_price += opt['price_change']
                    p_str = f" (+{format_price(opt['price_change'])})" if opt['price_change'] > 0 else ""
                    summary_lines.append(f"  • {opt['name']}{p_str}")
            if opts:
                mods_data[g['name']] = opts
        else:
            if sel is None:
                continue
            opt = await db.get_modifier_option(sel)
            if opt:
                mods_data[g['name']] = {
                    "id": opt['id'],
                    "name": opt['name'],
                    "price": opt['price_change']
                }
                extra_price += opt['price_change']
                p_str = f" (+{format_price(opt['price_change'])})" if opt['price_change'] > 0 else ""
                summary_lines.append(f"  • {g['name']}: {opt['name']}{p_str}")

    total_item_price = product['price'] + extra_price
    mods_json = json.dumps(mods_data, ensure_ascii=False)

    await db.add_to_cart(callback.from_user.id, product_id, 1, mods_json)
    cnt = await db.get_cart_count(callback.from_user.id)

    text = (
        f"✅ <b>{product['name']}</b> добавлен в корзину!\n\n"
        f"💰 Базовая цена: {format_price(product['price'])}\n"
    )
    if summary_lines:
        text += "📋 Выбрано:\n" + "\n".join(summary_lines) + "\n"
    if extra_price > 0:
        text += f"\n➕ Доплата: {format_price(extra_price)}"
    text += f"\n💰 <b>Итого за шт.: {format_price(total_item_price)}</b>"
    text += f"\n\n🛒 В корзине: {cnt} шт."

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛒 Корзина", callback_data="go_cart")],
        [InlineKeyboardButton(text="🍽 Продолжить", callback_data="back_categories")]
    ])

    try:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except Exception:
        await callback.message.answer(text, reply_markup=kb, parse_mode="HTML")

    # Обновляем reply-кнопку Корзина со счётчиком
    from keyboards.client_kb import main_menu_kb
    await callback.message.answer(
        f"🛒 В корзине: {cnt} шт.",
        reply_markup=main_menu_kb(cnt)
    )

    await state.clear()


@router.callback_query(F.data == "go_cart")
async def go_to_cart(callback: CallbackQuery):
    from handlers.cart import _show_cart
    await _show_cart(callback, callback.from_user.id, edit=True)
    await callback.answer()