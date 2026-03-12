from aiogram.types import InlineKeyboardButton
from math import ceil


class Paginator:
    def __init__(self, items: list, page: int = 1, per_page: int = 8,
                 callback_prefix: str = "page"):
        self.items = items
        self.page = max(1, page)
        self.per_page = per_page
        self.callback_prefix = callback_prefix
        self.total_pages = max(1, ceil(len(items) / per_page))
        if self.page > self.total_pages:
            self.page = self.total_pages

    @property
    def current_items(self) -> list:
        start = (self.page - 1) * self.per_page
        end = start + self.per_page
        return self.items[start:end]

    def nav_buttons(self) -> list[InlineKeyboardButton]:
        buttons = []
        if self.page > 1:
            buttons.append(InlineKeyboardButton(
                text="◀️",
                callback_data=f"{self.callback_prefix}_{self.page - 1}"
            ))
        buttons.append(InlineKeyboardButton(
            text=f"{self.page}/{self.total_pages}",
            callback_data="noop"
        ))
        if self.page < self.total_pages:
            buttons.append(InlineKeyboardButton(
                text="▶️",
                callback_data=f"{self.callback_prefix}_{self.page + 1}"
            ))
        return buttons

    @property
    def has_pages(self) -> bool:
        return self.total_pages > 1