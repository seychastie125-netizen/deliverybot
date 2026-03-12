from aiogram.fsm.state import State, StatesGroup


class OrderStates(StatesGroup):
    choosing_delivery_type = State()
    choosing_pickup_time = State()
    choosing_payment = State()
    entering_address = State()
    entering_phone = State()
    entering_comment = State()
    entering_promo = State()
    confirming = State()


class AdminProductStates(StatesGroup):
    waiting_category = State()
    waiting_name = State()
    waiting_description = State()
    waiting_price = State()
    waiting_image = State()


class AdminCategoryStates(StatesGroup):
    waiting_name = State()
    waiting_emoji = State()


class AdminPromoStates(StatesGroup):
    waiting_code = State()
    waiting_type = State()
    waiting_value = State()
    waiting_min_order = State()
    waiting_max_uses = State()


class AdminPromotionStates(StatesGroup):
    waiting_title = State()
    waiting_description = State()
    waiting_discount = State()


class AdminCourierStates(StatesGroup):
    waiting_user_id = State()
    waiting_name = State()
    waiting_phone = State()


class AdminSettingStates(StatesGroup):
    waiting_value = State()


class AdminBroadcastStates(StatesGroup):
    waiting_message = State()
    confirming = State()


class AdminEditProductStates(StatesGroup):
    waiting_field = State()
    waiting_value = State()


# ===== MODIFIER STATES =====
class AdminModGroupStates(StatesGroup):
    waiting_name = State()
    waiting_type = State()
    waiting_max_select = State()


class AdminModOptionStates(StatesGroup):
    waiting_name = State()
    waiting_price = State()


class AdminModOptionEditStates(StatesGroup):
    waiting_field = State()
    waiting_value = State()


class ClientModifierStates(StatesGroup):
    selecting_modifiers = State()