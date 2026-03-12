from typing import Any, Awaitable, Callable, Dict
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from database.db import db


class AutoRegisterMiddleware(BaseMiddleware):
    async def __call__(self, handler: Callable, event: TelegramObject,
                       data: Dict[str, Any]) -> Any:
        if hasattr(event, 'from_user') and event.from_user:
            user = event.from_user
            await db.add_user(user.id, user.username or "", user.full_name or "")
        return await handler(event, data)