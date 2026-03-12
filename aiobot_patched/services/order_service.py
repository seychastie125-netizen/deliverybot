import json
from dataclasses import dataclass
from database.db import db
from utils.modifiers import parse_modifiers_price, format_modifiers_plain


@dataclass
class OrderResult:
    success: bool
    order_id: int = 0
    error: str = ""


@dataclass
class OrderData:
    user_id: int
    delivery_type: str
    payment_method: str
    address: str
    phone: str
    comment: str
    pickup_time: str = None
    promo_code: str = None
    promo_id: int = None
    discount: float = 0




async def calculate_promotion_discount(user_id: int) -> tuple[float, list[str]]:
    """Считает скидку по акциям. Fix bug 10: загружает все акции одним запросом."""
    cart_items = await db.get_cart(user_id)
    total_promo_discount = 0.0
    promo_details = []

    if not cart_items:
        return 0.0, []

    # Загружаем ВСЕ активные акции одним запросом
    all_promotions = await db.get_active_promotions()

    for item in cart_items:
        product_id = item['product_id']
        category_id = item['category_id']
        base_price = item['price'] + parse_modifiers_price(item['modifiers_json'])

        # Фильтруем в Python, без лишних запросов к БД
        applicable = [
            p for p in all_promotions
            if (p['apply_to'] == 'all'
                or (p['apply_to'] == 'category' and p['category_id'] == category_id)
                or (p['apply_to'] == 'product' and p['product_id'] == product_id))
        ]
        if not applicable:
            continue

        # Берём лучшую акцию (макс. скидка)
        best = max(applicable, key=lambda p: p['discount_percent'])
        if best['discount_percent'] <= 0:
            continue

        item_total = base_price * item['quantity']
        discount = round(item_total * best['discount_percent'] / 100, 2)
        total_promo_discount += discount
        promo_details.append(
            f"🔥 {best['title']}: {item['name']} "
            f"-{best['discount_percent']:.0f}% (-{discount:.0f}₽)"
        )

    return total_promo_discount, promo_details


async def calculate_total(user_id: int, promo_discount: float = 0,
                          delivery_type: str = "delivery") -> dict:
    """Считает полную стоимость заказа с учётом всех скидок."""
    subtotal = await db.get_cart_total(user_id)

    # Акционная скидка
    promotion_discount, promo_details = await calculate_promotion_discount(user_id)

    # Доставка
    delivery_price = 0.0
    if delivery_type == "delivery":
        dp = float(await db.get_setting("delivery_price") or 0)
        free_from = float(await db.get_setting("free_delivery_from") or 999999)
        if subtotal < free_from:
            delivery_price = dp

    total = max(0, subtotal + delivery_price - promo_discount - promotion_discount)

    return {
        "subtotal": subtotal,
        "delivery_price": delivery_price,
        "discount": promo_discount,
        "promotion_discount": promotion_discount,
        "promotion_details": promo_details,
        "total": total,
    }


async def validate_cart(user_id: int) -> tuple[bool, str]:
    cart_items = await db.get_cart(user_id)
    if not cart_items:
        return False, "🛒 Корзина пуста"
    total = await db.get_cart_total(user_id)
    min_order = float(await db.get_setting("min_order_amount") or 0)
    if total < min_order:
        return False, f"❌ Минимальная сумма заказа: {min_order:.0f}₽"
    for item in cart_items:
        product = await db.get_product(item['product_id'])
        if not product or not product['is_available']:
            return False, f"❌ Товар «{item['name']}» недоступен"
    return True, ""


async def create_order(data: OrderData) -> OrderResult:
    valid, error = await validate_cart(data.user_id)
    if not valid:
        return OrderResult(success=False, error=error)

    totals = await calculate_total(data.user_id, data.discount, data.delivery_type)

    cart_items = await db.get_cart(data.user_id)
    items_list = []
    for item in cart_items:
        item_price = item['price'] + parse_modifiers_price(item['modifiers_json'])
        mods_text = format_modifiers_plain(item['modifiers_json'])

        entry = {
            "name": item['name'],
            "price": item['price'],
            "quantity": item['quantity'],
            "sum": item_price * item['quantity'],
            "modifiers": mods_text,
            "modifiers_data": json.loads(item['modifiers_json'])
                if item['modifiers_json'] else {}
        }
        items_list.append(entry)

    items_json = json.dumps(items_list, ensure_ascii=False)

    # Fix bug 13: double-order protection - check cart is still non-empty atomically
    # Fix bug 2: atomic promo usage inside transaction
    try:
        await db._conn.execute("BEGIN IMMEDIATE")

        # Re-validate cart hasn't been cleared by a parallel request
        cursor = await db._conn.execute(
            "SELECT COUNT(*) FROM cart WHERE user_id = ?", (data.user_id,)
        )
        row = await cursor.fetchone()
        if row[0] == 0:
            await db._conn.execute("ROLLBACK")
            return OrderResult(success=False, error="🛒 Корзина уже была оформлена")

        # Fix bug 2: atomically mark promo as used inside the same transaction
        if data.promo_id:
            await db._conn.execute(
                "UPDATE promocodes SET used_count = used_count + 1 "
                "WHERE id = ? AND (max_uses = -1 OR used_count < max_uses)",
                (data.promo_id,)
            )
            cursor = await db._conn.execute("SELECT changes()")
            changes = (await cursor.fetchone())[0]
            if changes == 0:
                await db._conn.execute("ROLLBACK")
                return OrderResult(success=False, error="❌ Промокод исчерпан")
            await db._conn.execute(
                "INSERT INTO promo_usages (user_id, promo_id) VALUES (?, ?)",
                (data.user_id, data.promo_id)
            )

        cursor = await db._conn.execute(
            "INSERT INTO orders (user_id, items_json, total_price, discount, "
            "promotion_discount, promo_code, delivery_type, payment_method, "
            "address, phone, comment, pickup_time) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (data.user_id, items_json, totals['total'], data.discount,
             totals['promotion_discount'], data.promo_code or "",
             data.delivery_type, data.payment_method, data.address,
             data.phone, data.comment, data.pickup_time)
        )
        order_id = cursor.lastrowid
        await db._conn.execute(
            "UPDATE users SET total_orders = total_orders + 1, "
            "total_spent = total_spent + ? WHERE user_id = ?",
            (totals['total'], data.user_id)
        )
        await db._conn.execute(
            "INSERT INTO order_history (order_id, old_status, new_status, changed_by) "
            "VALUES (?, NULL, 'new', ?)",
            (order_id, data.user_id)
        )
        await db._conn.execute("DELETE FROM cart WHERE user_id = ?", (data.user_id,))
        await db._conn.commit()
    except Exception as e:
        try:
            await db._conn.execute("ROLLBACK")
        except Exception:
            pass
        raise

    return OrderResult(success=True, order_id=order_id)