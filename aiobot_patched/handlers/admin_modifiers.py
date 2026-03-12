from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from database.db import db
from keyboards.callbacks import (
    AdminProdCB, ModGroupCB, ModOptionCB, ModGroupTypeCB
)
from states.states import AdminModGroupStates, AdminModOptionStates, AdminModOptionEditStates
from utils.helpers import format_price
from filters.role import IsAdmin

router = Router()
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())


# ===== ПРОСМОТР МОДИФИКАТОРОВ ТОВАРА =====
@router.callback_query(AdminProdCB.filter(F.action == "mods"))
async def adm_prod_modifiers(callback: CallbackQuery, callback_data: AdminProdCB):
    pid = callback_data.id
    product = await db.get_product(pid)
    if not product:
        await callback.answer("Товар не найден", show_alert=True)
        return

    groups = await db.get_product_full_modifiers(pid)

    text = f"⚙️ <b>Модификаторы: {product['name']}</b>\n\n"

    if not groups:
        text += "<i>Нет модификаторов</i>"
    else:
        for g_data in groups:
            g = g_data["group"]
            options = g_data["options"]
            req = "обязат." if g['is_required'] else "опцион."
            mult = "несколько" if g['is_multiple'] else "один"
            text += f"📦 <b>{g['name']}</b> ({req}, {mult})\n"
            for opt in options:
                avail = "✅" if opt['is_available'] else "❌"
                default = " ⭐" if opt['is_default'] else ""
                price = ""
                if opt['price_change'] > 0:
                    price = f" +{format_price(opt['price_change'])}"
                elif opt['price_change'] < 0:
                    price = f" {format_price(opt['price_change'])}"
                text += f"  {avail} {opt['name']}{price}{default}\n"
            text += "\n"

    builder = InlineKeyboardBuilder()
    for g_data in groups:
        g = g_data["group"]
        builder.button(
            text=f"📦 {g['name']}",
            callback_data=ModGroupCB(action="detail", product_id=pid, group_id=g['id']).pack()
        )
    builder.adjust(1)
    builder.row(InlineKeyboardButton(
        text="➕ Добавить группу",
        callback_data=ModGroupCB(action="add", product_id=pid).pack()
    ))
    builder.row(InlineKeyboardButton(
        text="⬅️ К товару",
        callback_data=AdminProdCB(action="detail", id=pid).pack()
    ))

    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await callback.answer()


# ===== ДОБАВЛЕНИЕ ГРУППЫ =====
@router.callback_query(ModGroupCB.filter(F.action == "add"))
async def adm_mod_group_add(callback: CallbackQuery, callback_data: ModGroupCB,
                            state: FSMContext):
    await state.update_data(mod_product_id=callback_data.product_id)
    await callback.message.edit_text(
        "📦 Введите название группы модификаторов:\n\n"
        "<i>Примеры: Размер, Тесто, Добавки, Соус</i>",
        parse_mode="HTML"
    )
    await state.set_state(AdminModGroupStates.waiting_name)
    await callback.answer()


@router.message(AdminModGroupStates.waiting_name)
async def adm_mod_group_name(message: Message, state: FSMContext):
    await state.update_data(mod_group_name=message.text.strip())

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="☝️ Обязательный, один",
                callback_data=ModGroupTypeCB(is_required=1, is_multiple=0).pack()
            )
        ],
        [
            InlineKeyboardButton(
                text="☝️ Обязательный, несколько",
                callback_data=ModGroupTypeCB(is_required=1, is_multiple=1).pack()
            )
        ],
        [
            InlineKeyboardButton(
                text="👆 Необязательный, один",
                callback_data=ModGroupTypeCB(is_required=0, is_multiple=0).pack()
            )
        ],
        [
            InlineKeyboardButton(
                text="👆 Необязательный, несколько",
                callback_data=ModGroupTypeCB(is_required=0, is_multiple=1).pack()
            )
        ],
    ])

    await message.answer(
        "Тип группы:\n\n"
        "• <b>Обязательный, один</b> — клиент ДОЛЖЕН выбрать 1 (напр. Размер)\n"
        "• <b>Обязательный, несколько</b> — клиент ДОЛЖЕН выбрать 1+ (напр. Начинка)\n"
        "• <b>Необязательный, один</b> — можно выбрать 0 или 1\n"
        "• <b>Необязательный, несколько</b> — можно выбрать 0+ (напр. Добавки)",
        reply_markup=kb, parse_mode="HTML"
    )
    await state.set_state(AdminModGroupStates.waiting_type)


@router.callback_query(ModGroupTypeCB.filter(), AdminModGroupStates.waiting_type)
async def adm_mod_group_type(callback: CallbackQuery, callback_data: ModGroupTypeCB,
                             state: FSMContext):
    await state.update_data(
        mod_is_required=callback_data.is_required,
        mod_is_multiple=callback_data.is_multiple
    )

    if callback_data.is_multiple:
        await callback.message.edit_text(
            "🔢 Максимальное количество выборов (0 = без лимита):"
        )
        await state.set_state(AdminModGroupStates.waiting_max_select)
    else:
        data = await state.get_data()
        await _save_mod_group(callback, state, max_select=1)

    await callback.answer()


@router.message(AdminModGroupStates.waiting_max_select)
async def adm_mod_group_max(message: Message, state: FSMContext):
    try:
        max_sel = int(message.text.strip())
    except ValueError:
        max_sel = 0

    if max_sel <= 0:
        max_sel = 99

    data = await state.get_data()
    min_sel = 1 if data['mod_is_required'] else 0

    gid = await db.add_modifier_group(
        product_id=data['mod_product_id'],
        name=data['mod_group_name'],
        is_required=data['mod_is_required'],
        is_multiple=data['mod_is_multiple'],
        min_select=min_sel,
        max_select=max_sel
    )

    await message.answer(
        f"✅ Группа «{data['mod_group_name']}» создана!\n"
        f"Теперь добавьте варианты."
    )
    await state.clear()

    # Показываем группу
    product = await db.get_product(data['mod_product_id'])
    await _show_group_detail(message, data['mod_product_id'], gid)


async def _save_mod_group(callback_or_msg, state, max_select=1):
    data = await state.get_data()
    min_sel = 1 if data['mod_is_required'] else 0

    gid = await db.add_modifier_group(
        product_id=data['mod_product_id'],
        name=data['mod_group_name'],
        is_required=data['mod_is_required'],
        is_multiple=data['mod_is_multiple'],
        min_select=min_sel,
        max_select=max_select
    )

    await state.clear()

    if isinstance(callback_or_msg, CallbackQuery):
        await callback_or_msg.message.edit_text(
            f"✅ Группа «{data['mod_group_name']}» создана!"
        )
        await _show_group_detail(callback_or_msg.message, data['mod_product_id'], gid)
    else:
        await callback_or_msg.answer(
            f"✅ Группа «{data['mod_group_name']}» создана!"
        )
        await _show_group_detail(callback_or_msg, data['mod_product_id'], gid)


async def _show_group_detail(msg_target, product_id: int, group_id: int):
    group = await db.get_modifier_group(group_id)
    options = await db.get_modifier_options(group_id, only_available=False)

    req = "Обязательный" if group['is_required'] else "Необязательный"
    mult = "несколько" if group['is_multiple'] else "один"

    text = (
        f"📦 <b>{group['name']}</b>\n"
        f"Тип: {req}, {mult}\n"
        f"Выбор: {group['min_select']}—{group['max_select']}\n\n"
    )

    if options:
        text += "<b>Варианты:</b>\n"
        for opt in options:
            avail = "✅" if opt['is_available'] else "❌"
            default = " ⭐" if opt['is_default'] else ""
            price = ""
            if opt['price_change'] > 0:
                price = f" (+{format_price(opt['price_change'])})"
            elif opt['price_change'] < 0:
                price = f" ({format_price(opt['price_change'])})"
            text += f"  {avail} {opt['name']}{price}{default}\n"
    else:
        text += "<i>Нет вариантов</i>"

    builder = InlineKeyboardBuilder()
    for opt in options:
        builder.button(
            text=f"✏️ {opt['name']}",
            callback_data=ModOptionCB(action="detail", group_id=group_id, option_id=opt['id']).pack()
        )
    builder.adjust(2)
    builder.row(InlineKeyboardButton(
        text="➕ Добавить вариант",
        callback_data=ModOptionCB(action="add", group_id=group_id).pack()
    ))
    builder.row(InlineKeyboardButton(
        text="🗑 Удалить группу",
        callback_data=ModGroupCB(action="del", product_id=product_id, group_id=group_id).pack()
    ))
    builder.row(InlineKeyboardButton(
        text="⬅️ К модификаторам",
        callback_data=AdminProdCB(action="mods", id=product_id).pack()
    ))

    await msg_target.answer(text, reply_markup=builder.as_markup(), parse_mode="HTML")


# ===== ДЕТАЛИ ГРУППЫ =====
@router.callback_query(ModGroupCB.filter(F.action == "detail"))
async def adm_mod_group_detail(callback: CallbackQuery, callback_data: ModGroupCB):
    await _show_group_detail_cb(callback, callback_data.product_id, callback_data.group_id)
    await callback.answer()


async def _show_group_detail_cb(callback: CallbackQuery, product_id: int, group_id: int):
    group = await db.get_modifier_group(group_id)
    if not group:
        await callback.answer("Не найдена", show_alert=True)
        return

    options = await db.get_modifier_options(group_id, only_available=False)

    req = "Обязательный" if group['is_required'] else "Необязательный"
    mult = "несколько" if group['is_multiple'] else "один"

    text = (
        f"📦 <b>{group['name']}</b>\n"
        f"Тип: {req}, {mult}\n"
        f"Выбор: {group['min_select']}—{group['max_select']}\n\n"
    )

    if options:
        text += "<b>Варианты:</b>\n"
        for opt in options:
            avail = "✅" if opt['is_available'] else "❌"
            default = " ⭐" if opt['is_default'] else ""
            price = ""
            if opt['price_change'] > 0:
                price = f" (+{format_price(opt['price_change'])})"
            elif opt['price_change'] < 0:
                price = f" ({format_price(opt['price_change'])})"
            text += f"  {avail} {opt['name']}{price}{default}\n"
    else:
        text += "<i>Нет вариантов</i>"

    builder = InlineKeyboardBuilder()
    for opt in options:
        builder.button(
            text=f"✏️ {opt['name']}",
            callback_data=ModOptionCB(
                action="detail", group_id=group_id, option_id=opt['id']
            ).pack()
        )
    builder.adjust(2)
    builder.row(InlineKeyboardButton(
        text="➕ Добавить вариант",
        callback_data=ModOptionCB(action="add", group_id=group_id).pack()
    ))
    builder.row(InlineKeyboardButton(
        text="🗑 Удалить группу",
        callback_data=ModGroupCB(
            action="del", product_id=product_id, group_id=group_id
        ).pack()
    ))
    builder.row(InlineKeyboardButton(
        text="⬅️ К модификаторам",
        callback_data=AdminProdCB(action="mods", id=product_id).pack()
    ))

    await callback.message.edit_text(
        text, reply_markup=builder.as_markup(), parse_mode="HTML"
    )


# ===== УДАЛЕНИЕ ГРУППЫ =====
@router.callback_query(ModGroupCB.filter(F.action == "del"))
async def adm_mod_group_del_confirm(callback: CallbackQuery, callback_data: ModGroupCB):
    group = await db.get_modifier_group(callback_data.group_id)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="🗑 Да, удалить",
            callback_data=ModGroupCB(
                action="del_yes",
                product_id=callback_data.product_id,
                group_id=callback_data.group_id
            ).pack()
        )],
        [InlineKeyboardButton(
            text="❌ Отмена",
            callback_data=ModGroupCB(
                action="detail",
                product_id=callback_data.product_id,
                group_id=callback_data.group_id
            ).pack()
        )]
    ])
    await callback.message.edit_text(
        f"⚠️ Удалить группу «{group['name']}» и все варианты?",
        reply_markup=kb
    )
    await callback.answer()


@router.callback_query(ModGroupCB.filter(F.action == "del_yes"))
async def adm_mod_group_del_exec(callback: CallbackQuery, callback_data: ModGroupCB):
    await db.delete_modifier_group(callback_data.group_id)
    await callback.answer("🗑 Группа удалена")
    # Возврат к списку модификаторов
    await callback.message.delete()
    # Вызываем показ модификаторов через callback_data
    from keyboards.callbacks import AdminProdCB as AP
    fake_cb = AdminProdCB(action="mods", id=callback_data.product_id)
    await adm_prod_modifiers_redirect(callback, callback_data.product_id)


async def adm_prod_modifiers_redirect(callback: CallbackQuery, product_id: int):
    product = await db.get_product(product_id)
    groups = await db.get_product_full_modifiers(product_id)

    text = f"⚙️ <b>Модификаторы: {product['name']}</b>\n\n"
    if not groups:
        text += "<i>Нет модификаторов</i>"
    else:
        for g_data in groups:
            g = g_data["group"]
            options = g_data["options"]
            req = "обязат." if g['is_required'] else "опцион."
            mult = "несколько" if g['is_multiple'] else "один"
            text += f"📦 <b>{g['name']}</b> ({req}, {mult})\n"
            for opt in options:
                avail = "✅" if opt['is_available'] else "❌"
                price = ""
                if opt['price_change'] > 0:
                    price = f" +{format_price(opt['price_change'])}"
                text += f"  {avail} {opt['name']}{price}\n"
            text += "\n"

    builder = InlineKeyboardBuilder()
    for g_data in groups:
        g = g_data["group"]
        builder.button(
            text=f"📦 {g['name']}",
            callback_data=ModGroupCB(
                action="detail", product_id=product_id, group_id=g['id']
            ).pack()
        )
    builder.adjust(1)
    builder.row(InlineKeyboardButton(
        text="➕ Добавить группу",
        callback_data=ModGroupCB(action="add", product_id=product_id).pack()
    ))
    builder.row(InlineKeyboardButton(
        text="⬅️ К товару",
        callback_data=AdminProdCB(action="detail", id=product_id).pack()
    ))

    await callback.message.answer(
        text, reply_markup=builder.as_markup(), parse_mode="HTML"
    )


# ===== ДОБАВЛЕНИЕ ВАРИАНТА =====
@router.callback_query(ModOptionCB.filter(F.action == "add"))
async def adm_mod_option_add(callback: CallbackQuery, callback_data: ModOptionCB,
                             state: FSMContext):
    await state.update_data(mod_option_group_id=callback_data.group_id)
    await callback.message.edit_text(
        "📝 Название варианта:\n\n<i>Примеры: 25 см, Тонкое, Двойной сыр</i>",
        parse_mode="HTML"
    )
    await state.set_state(AdminModOptionStates.waiting_name)
    await callback.answer()


@router.message(AdminModOptionStates.waiting_name)
async def adm_mod_option_name(message: Message, state: FSMContext):
    await state.update_data(mod_option_name=message.text.strip())
    await message.answer(
        "💰 Доплата за этот вариант (0 = бесплатно):\n\n"
        "<i>Примеры: 0, 100, 150, -50</i>",
        parse_mode="HTML"
    )
    await state.set_state(AdminModOptionStates.waiting_price)


@router.message(AdminModOptionStates.waiting_price)
async def adm_mod_option_price(message: Message, state: FSMContext):
    try:
        price = float(message.text.strip().replace(",", "."))
    except ValueError:
        price = 0

    data = await state.get_data()
    group_id = data['mod_option_group_id']

    await db.add_modifier_option(
        group_id=group_id,
        name=data['mod_option_name'],
        price_change=price
    )

    group = await db.get_modifier_group(group_id)

    await message.answer(
        f"✅ Вариант «{data['mod_option_name']}» добавлен!\n"
        f"Доплата: {format_price(price)}"
    )
    await state.clear()

    # Показываем группу заново
    await _show_group_detail(message, group['product_id'], group_id)


# ===== ДЕТАЛИ ВАРИАНТА =====
@router.callback_query(ModOptionCB.filter(F.action == "detail"))
async def adm_mod_option_detail(callback: CallbackQuery, callback_data: ModOptionCB):
    opt = await db.get_modifier_option(callback_data.option_id)
    if not opt:
        await callback.answer("Не найден", show_alert=True)
        return

    group = await db.get_modifier_group(callback_data.group_id)
    avail = "✅ Доступен" if opt['is_available'] else "❌ Скрыт"
    default = "⭐ По умолчанию" if opt['is_default'] else ""
    price = f"+{format_price(opt['price_change'])}" if opt['price_change'] >= 0 else format_price(opt['price_change'])

    text = (
        f"✏️ <b>{opt['name']}</b>\n\n"
        f"💰 Доплата: {price}\n"
        f"{avail}\n"
        f"{default}"
    )

    toggle_avail = "Скрыть" if opt['is_available'] else "Показать"
    toggle_default = "Убрать ⭐" if opt['is_default'] else "Сделать ⭐"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=f"👁 {toggle_avail}",
                callback_data=ModOptionCB(
                    action="toggle_avail",
                    group_id=callback_data.group_id,
                    option_id=callback_data.option_id
                ).pack()
            ),
            InlineKeyboardButton(
                text=toggle_default,
                callback_data=ModOptionCB(
                    action="toggle_default",
                    group_id=callback_data.group_id,
                    option_id=callback_data.option_id
                ).pack()
            )
        ],
        [
            InlineKeyboardButton(
                text="✏️ Изменить название",
                callback_data=ModOptionCB(
                    action="edit_name",
                    group_id=callback_data.group_id,
                    option_id=callback_data.option_id
                ).pack()
            ),
            InlineKeyboardButton(
                text="💰 Изменить цену",
                callback_data=ModOptionCB(
                    action="edit_price",
                    group_id=callback_data.group_id,
                    option_id=callback_data.option_id
                ).pack()
            )
        ],
        [InlineKeyboardButton(
            text="🗑 Удалить вариант",
            callback_data=ModOptionCB(
                action="del",
                group_id=callback_data.group_id,
                option_id=callback_data.option_id
            ).pack()
        )],
        [InlineKeyboardButton(
            text="⬅️ К группе",
            callback_data=ModGroupCB(
                action="detail",
                product_id=group['product_id'],
                group_id=callback_data.group_id
            ).pack()
        )]
    ])

    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()


@router.callback_query(ModOptionCB.filter(F.action == "toggle_avail"))
async def adm_mod_option_toggle(callback: CallbackQuery, callback_data: ModOptionCB):
    opt = await db.get_modifier_option(callback_data.option_id)
    await db.update_modifier_option(
        callback_data.option_id,
        is_available=0 if opt['is_available'] else 1
    )
    await callback.answer("✅ Обновлено")
    # Перезагружаем детали
    callback_data_new = ModOptionCB(
        action="detail",
        group_id=callback_data.group_id,
        option_id=callback_data.option_id
    )
    await adm_mod_option_detail(callback, callback_data_new)


@router.callback_query(ModOptionCB.filter(F.action == "toggle_default"))
async def adm_mod_option_default(callback: CallbackQuery, callback_data: ModOptionCB):
    opt = await db.get_modifier_option(callback_data.option_id)
    await db.update_modifier_option(
        callback_data.option_id,
        is_default=0 if opt['is_default'] else 1
    )
    await callback.answer("✅ Обновлено")
    callback_data_new = ModOptionCB(
        action="detail",
        group_id=callback_data.group_id,
        option_id=callback_data.option_id
    )
    await adm_mod_option_detail(callback, callback_data_new)


@router.callback_query(ModOptionCB.filter(F.action == "edit_name"))
async def adm_mod_option_edit_name(callback: CallbackQuery, callback_data: ModOptionCB,
                                   state: FSMContext):
    await state.update_data(
        edit_option_id=callback_data.option_id,
        edit_option_group_id=callback_data.group_id,
        edit_option_field="name"
    )
    await callback.message.edit_text("📝 Новое название варианта:")
    await state.set_state(AdminModOptionEditStates.waiting_value)
    await callback.answer()


@router.callback_query(ModOptionCB.filter(F.action == "edit_price"))
async def adm_mod_option_edit_price(callback: CallbackQuery, callback_data: ModOptionCB,
                                    state: FSMContext):
    await state.update_data(
        edit_option_id=callback_data.option_id,
        edit_option_group_id=callback_data.group_id,
        edit_option_field="price_change"
    )
    await callback.message.edit_text("💰 Новая доплата (число):")
    await state.set_state(AdminModOptionEditStates.waiting_value)
    await callback.answer()


@router.message(AdminModOptionEditStates.waiting_value)
async def adm_mod_option_edit_save(message: Message, state: FSMContext):
    data = await state.get_data()
    field = data['edit_option_field']
    value = message.text.strip()

    if field == "price_change":
        try:
            value = float(value.replace(",", "."))
        except ValueError:
            await message.answer("❌ Введите число")
            return

    await db.update_modifier_option(data['edit_option_id'], **{field: value})
    await message.answer("✅ Обновлено!")
    await state.clear()

    group = await db.get_modifier_group(data['edit_option_group_id'])
    await _show_group_detail(message, group['product_id'], data['edit_option_group_id'])


@router.callback_query(ModOptionCB.filter(F.action == "del"))
async def adm_mod_option_del(callback: CallbackQuery, callback_data: ModOptionCB):
    await db.delete_modifier_option(callback_data.option_id)
    await callback.answer("🗑 Удалено")
    group = await db.get_modifier_group(callback_data.group_id)
    await _show_group_detail_cb(callback, group['product_id'], callback_data.group_id)