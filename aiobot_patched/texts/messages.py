class Msg:
    WELCOME = "Добро пожаловать в наш бот доставки! 🍕"
    CART_EMPTY = "🛒 Ваша корзина пуста"
    ORDER_CANCELLED = "❌ Оформление заказа отменено"
    PHONE_INVALID = "❌ Некорректный номер. Попробуйте ещё раз:"
    ADDRESS_SHORT = "❌ Адрес слишком короткий. Попробуйте ещё раз:"
    NO_CATEGORIES = "😔 Меню пока пусто"
    NO_PRODUCTS = "В этой категории пока нет товаров"
    NO_PROMOS = "😔 Сейчас нет активных акций"
    NO_ORDERS = "📋 У вас пока нет заказов"
    NO_SLOTS = ("😔 На сегодня нет доступных слотов.\n"
                "Попробуйте завтра или выберите доставку.")
    CHOOSE_CATEGORY = "📋 <b>Выберите категорию:</b>"
    CHOOSE_DELIVERY = "🛍 <b>Оформление заказа</b>\n\nВыберите способ получения:"
    CHOOSE_PAYMENT = "💳 <b>Выберите способ оплаты:</b>"
    ENTER_ADDRESS = "📍 Введите адрес доставки:"
    ENTER_PHONE = "📱 Введите номер телефона или отправьте контакт:"
    ENTER_COMMENT = "💬 Комментарий к заказу (или нажмите Пропустить):"
    ENTER_PROMO = "🏷 Введите промокод:"
    SEARCH_MIN = "Введите минимум 2 символа для поиска"
    SEARCH_EMPTY = "🔍 По запросу «{query}» ничего не найдено"
    BOT_PAUSED = "⏸ Бот временно не принимает заказы.\nПопробуйте позже!"
    OUTSIDE_HOURS = "⏰ Сейчас мы не работаем.\n{hours}"
    CASH_HINT = "\n\n💵 <i>Подготовьте наличные для оплаты</i>"
    CARD_DELIVERY_HINT = "\n\n💳 <i>Оплата картой курьеру при получении</i>"
    CARD_PICKUP_HINT = "\n\n💳 <i>Оплата картой при получении</i>"
    ADMIN_NO_ACCESS = "❌ Нет доступа"
    DELETE_CONFIRM = ("⚠️ <b>Удалить «{name}»?</b>\n\n"
                      "{extra}\nЭто действие необратимо.")

    @staticmethod
    def order_status_text(order_id: int, status: str) -> str:
        m = {
            "confirmed": f"✅ Ваш заказ <b>#{order_id}</b> подтверждён!",
            "cooking": f"👨‍🍳 Ваш заказ <b>#{order_id}</b> готовится!",
            "delivering": f"🚴 Ваш заказ <b>#{order_id}</b> в пути!",
            "delivered": f"📦 Ваш заказ <b>#{order_id}</b> доставлен! Спасибо! 🙏",
            "cancelled": f"❌ Ваш заказ <b>#{order_id}</b> отменён.",
            "ready_for_pickup": f"✅ Ваш заказ <b>#{order_id}</b> готов к выдаче!",
            "completed": f"✅ Заказ <b>#{order_id}</b> завершён. Спасибо! 🙏",
        }
        return m.get(status, f"Заказ #{order_id}: {status}")