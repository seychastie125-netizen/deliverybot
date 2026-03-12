from aiogram.filters.callback_data import CallbackData


class CategoryCB(CallbackData, prefix="cat"):
    id: int


class ProductCB(CallbackData, prefix="prod"):
    id: int


class ProductPageCB(CallbackData, prefix="prodpage"):
    cat_id: int
    page: int


class CartActionCB(CallbackData, prefix="crt"):
    action: str
    item_id: int = 0
    product_id: int = 0


class DeliveryTypeCB(CallbackData, prefix="dtype"):
    type: str


class PaymentCB(CallbackData, prefix="pay"):
    method: str


class PickupTimeCB(CallbackData, prefix="ptime", sep="|"):
    time: str  # Format: HHMM (e.g. "1800") — no colon allowed in aiogram callback data  # формат HHMM (без двоеточия, чтобы избежать конфликта с разделителем)


class MgrOrderCB(CallbackData, prefix="mgr"):
    action: str
    order_id: int


class MgrCourierCB(CallbackData, prefix="mgrc"):
    order_id: int
    courier_id: int


class AdminCatCB(CallbackData, prefix="acat"):
    action: str
    id: int = 0


class AdminProdCB(CallbackData, prefix="aprod"):
    action: str
    id: int = 0


class AdminPromoCB(CallbackData, prefix="apromo"):
    action: str
    id: int = 0


class AdminPromotionCB(CallbackData, prefix="aaction"):
    action: str
    id: int = 0


class AdminCourierCB(CallbackData, prefix="acour"):
    action: str
    id: int = 0


class AdminSettingCB(CallbackData, prefix="aset"):
    key: str


class AdminOrdersCB(CallbackData, prefix="aord"):
    status: str


class NewProdCatCB(CallbackData, prefix="npc"):
    cat_id: int


class EditFieldCB(CallbackData, prefix="ef"):
    field: str


class PromoTypeCB(CallbackData, prefix="pt"):
    discount_type: str


# ===== MODIFIER CALLBACKS =====
class ModGroupCB(CallbackData, prefix="mg"):
    action: str
    product_id: int = 0
    group_id: int = 0


class ModOptionCB(CallbackData, prefix="mo"):
    action: str
    group_id: int = 0
    option_id: int = 0


class ModGroupTypeCB(CallbackData, prefix="mgt"):
    is_required: int
    is_multiple: int


class MgrCancelConfirmCB(CallbackData, prefix="mgrcnl"):
    order_id: int
    confirmed: int  # 1 = да отменить, 0 = назад


# Client-side modifier selection
class ClientModCB(CallbackData, prefix="cm"):
    action: str
    product_id: int = 0
    group_id: int = 0
    option_id: int = 0