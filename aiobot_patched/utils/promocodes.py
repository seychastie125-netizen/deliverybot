from database.db import db
from datetime import datetime


async def validate_promo(code: str, user_id: int, order_total: float):
    promo = await db.get_promocode(code)
    if not promo:
        return None, "❌ Промокод не найден"
    if not promo['is_active']:
        return None, "❌ Промокод неактивен"
    if promo['expires_at']:
        try:
            expires = datetime.fromisoformat(promo['expires_at'])
            if datetime.now() > expires:
                return None, "❌ Промокод истёк"
        except ValueError:
            pass
    if promo['max_uses'] != -1 and promo['used_count'] >= promo['max_uses']:
        return None, "❌ Промокод исчерпан"
    if promo['min_order'] > 0 and order_total < promo['min_order']:
        return None, f"❌ Минимальная сумма для промокода: {promo['min_order']:.0f}₽"
    used = await db.check_promo_used_by_user(user_id, promo['id'])
    if used:
        return None, "❌ Вы уже использовали этот промокод"
    return promo, None


def calculate_discount(promo, total: float) -> float:
    if promo['discount_type'] == 'percent':
        return total * promo['discount_value'] / 100
    else:
        return min(promo['discount_value'], total)