import os
from dotenv import load_dotenv
from dataclasses import dataclass, field

load_dotenv()


@dataclass
class Config:
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
    ADMIN_IDS: list[int] = field(default_factory=list)
    MANAGER_IDS: list[int] = field(default_factory=list)
    DB_PATH: str = os.getenv("DB_PATH", "database/delivery.db")
    TIMEZONE: str = os.getenv("TIMEZONE", "Europe/Moscow")

    def __post_init__(self):
        admin_str = os.getenv("ADMIN_IDS", "")
        self.ADMIN_IDS = [int(x.strip()) for x in admin_str.split(",") if x.strip()]
        manager_str = os.getenv("MANAGER_IDS", "")
        self.MANAGER_IDS = [int(x.strip()) for x in manager_str.split(",") if x.strip()]
        if not self.BOT_TOKEN:
            raise ValueError("BOT_TOKEN не задан в .env — скопируйте .env.example")
        if not self.ADMIN_IDS:
            raise ValueError("ADMIN_IDS не задан — некому управлять ботом")


config = Config()