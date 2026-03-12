from typing import Any, Awaitable, Callable, Dict
from aiogram import BaseMiddleware
from aiogram.types import Message
import time


class ThrottlingMiddleware(BaseMiddleware):
    """
    Ограничитель частоты сообщений.
    Периодически очищает устаревшие записи, чтобы не копить память
    для всех уникальных пользователей за всё время работы бота.
    """
    MAX_CACHE_SIZE = 5_000

    def __init__(self, rate_limit: float = 0.5):
        self.rate_limit = rate_limit
        self.user_last: Dict[int, float] = {}
        self._call_count = 0

    def _evict_expired(self) -> None:
        """Удаляет устаревшие записи из кэша."""
        now = time.time()
        expired = [uid for uid, ts in self.user_last.items()
                   if now - ts > self.rate_limit * 10]
        for uid in expired:
            del self.user_last[uid]

    async def __call__(self,
                       handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
                       event: Message,
                       data: Dict[str, Any]) -> Any:
        uid = event.from_user.id
        now = time.time()

        if uid in self.user_last and (now - self.user_last[uid]) < self.rate_limit:
            return

        self.user_last[uid] = now

        # Периодически чистим устаревшие записи
        self._call_count += 1
        if self._call_count >= self.MAX_CACHE_SIZE:
            self._call_count = 0
            self._evict_expired()

        return await handler(event, data)