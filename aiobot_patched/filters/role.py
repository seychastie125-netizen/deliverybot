from aiogram.filters import BaseFilter
from aiogram.types import TelegramObject
from config import config


class IsAdmin(BaseFilter):
    async def __call__(self, event: TelegramObject) -> bool:
        if not hasattr(event, 'from_user') or not event.from_user:
            return False
        return event.from_user.id in config.ADMIN_IDS


class IsManager(BaseFilter):
    async def __call__(self, event: TelegramObject) -> bool:
        if not hasattr(event, 'from_user') or not event.from_user:
            return False
        uid = event.from_user.id
        return uid in config.ADMIN_IDS or uid in config.MANAGER_IDS