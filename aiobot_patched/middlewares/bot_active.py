from typing import Any, Awaitable, Callable, Dict
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, TelegramObject
from database.db import db
from utils.helpers import is_admin, is_manager
from texts.messages import Msg


class BotActiveMiddleware(BaseMiddleware):
    async def __call__(self, handler: Callable, event: TelegramObject,
                       data: Dict[str, Any]) -> Any:
        if hasattr(event, 'from_user') and event.from_user:
            uid = event.from_user.id

            # Администраторы и менеджеры проходят без ограничений
            if is_admin(uid) or is_manager(uid):
                return await handler(event, data)

            # FIX: проверяем бан пользователя (ранее поле is_banned игнорировалось)
            user_row = await db.get_user(uid)
            if user_row and user_row['is_banned']:
                if isinstance(event, Message):
                    await event.answer("🚫 Вы заблокированы и не можете пользоваться ботом.")
                elif isinstance(event, CallbackQuery):
                    await event.answer("🚫 Вы заблокированы.", show_alert=True)
                return

        active = await db.get_setting("bot_is_active")
        if active != "1":
            if isinstance(event, Message):
                await event.answer(Msg.BOT_PAUSED)
            elif isinstance(event, CallbackQuery):
                await event.answer(Msg.BOT_PAUSED, show_alert=True)
            return

        return await handler(event, data)