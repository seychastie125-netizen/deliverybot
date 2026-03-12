"""
Утилиты для работы с модификаторами товаров.
Единое место — устраняет дублирование кода в db.py, order_service.py, cart.py, order.py.
"""
import json


def parse_modifiers_price(modifiers_json: str) -> float:
    """Возвращает суммарную доплату за выбранные модификаторы."""
    try:
        data = json.loads(modifiers_json)
        extra = 0.0
        for _group_name, options in data.items():
            if isinstance(options, list):
                for opt in options:
                    extra += opt.get("price", 0)
            elif isinstance(options, dict):
                extra += options.get("price", 0)
        return extra
    except (json.JSONDecodeError, AttributeError, TypeError):
        return 0.0


def format_modifiers_text(modifiers_json: str, short: bool = False) -> str:
    """
    Форматирует модификаторы для отображения.

    :param modifiers_json: JSON-строка с модификаторами
    :param short: True — «(Размер: Большой; Соус: Острый)», False — с переносами
    """
    try:
        data = json.loads(modifiers_json)
        if not data:
            return ""
        parts = []
        for group_name, options in data.items():
            if isinstance(options, list):
                names = [o["name"] for o in options]
                parts.append(f"{group_name}: {', '.join(names)}")
            elif isinstance(options, dict):
                parts.append(f"{group_name}: {options['name']}")
        if not parts:
            return ""
        sep = "; " if short else "; "
        return " (" + sep.join(parts) + ")"
    except (json.JSONDecodeError, TypeError, KeyError):
        return ""


def format_modifiers_plain(modifiers_json: str) -> str:
    """Возвращает строку вида «Размер: Большой; Соус: Острый» без скобок."""
    try:
        data = json.loads(modifiers_json)
        if not data:
            return ""
        parts = []
        for group_name, options in data.items():
            if isinstance(options, list):
                names = [o["name"] for o in options]
                parts.append(f"{group_name}: {', '.join(names)}")
            elif isinstance(options, dict):
                parts.append(f"{group_name}: {options['name']}")
        return "; ".join(parts)
    except (json.JSONDecodeError, TypeError, KeyError):
        return ""



def format_modifiers_inline(modifiers_json: str) -> str:
    """Версия для строки заказа: «\\n    (Размер: Большой; Соус: Острый)»."""
    try:
        data = json.loads(modifiers_json)
        if not data:
            return ""
        parts = []
        for group_name, options in data.items():
            if isinstance(options, list):
                parts.append(f"{group_name}: {', '.join(o['name'] for o in options)}")
            elif isinstance(options, dict):
                parts.append(f"{group_name}: {options['name']}")
        if parts:
            return f"\n    <i>({'; '.join(parts)})</i>"
        return ""
    except (json.JSONDecodeError, TypeError, KeyError):
        return ""
