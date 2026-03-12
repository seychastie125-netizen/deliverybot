import json
import aiosqlite
import logging
from typing import Optional
from aiosqlite import Row
from config import config
from utils.modifiers import parse_modifiers_price

logger = logging.getLogger(__name__)

# Белые списки допустимых колонок для динамических UPDATE-запросов
# Защита от SQL-инъекции через имена ключей kwargs
_ALLOWED_COLS: dict[str, set[str]] = {
    "users": {"username", "full_name", "phone", "address", "is_banned",
              "total_orders", "total_spent"},
    "categories": {"name", "emoji", "sort_order", "is_active"},
    "products": {"category_id", "name", "description", "price",
                 "image_url", "is_available", "sort_order"},
    "modifier_groups": {"name", "is_required", "is_multiple",
                        "min_select", "max_select", "sort_order"},
    "modifier_options": {"name", "price_change", "is_default",
                         "is_available", "sort_order"},
    "promotions": {"title", "description", "image_url", "discount_percent",
                   "apply_to", "category_id", "product_id",
                   "is_active", "start_date", "end_date"},
}


def _validate_columns(table: str, kwargs: dict) -> None:
    """Проверяет имена колонок по белому списку. Бросает ValueError при нарушении."""
    allowed = _ALLOWED_COLS.get(table)
    if allowed is None:
        raise ValueError(f"Неизвестная таблица: {table}")
    invalid = set(kwargs.keys()) - allowed
    if invalid:
        raise ValueError(f"Недопустимые колонки для {table}: {invalid}")


class Database:
    def __init__(self):
        self.db_path = config.DB_PATH
        self.conn: Optional[aiosqlite.Connection] = None

    @property
    def _conn(self) -> aiosqlite.Connection:
        """Возвращает соединение или бросает RuntimeError если не подключено."""
        if self.conn is None:
            raise RuntimeError(
                "База данных не подключена. Вызовите db.connect() перед использованием."
            )
        return self.conn

    async def connect(self):
        try:
            self.conn = await aiosqlite.connect(self.db_path)
            self.conn.row_factory = aiosqlite.Row
            await self._conn.execute("PRAGMA journal_mode=WAL")
            await self._conn.execute("PRAGMA foreign_keys=ON")
            await self.create_tables()
            await self.run_migrations()
            logger.info("Database connected and migrated")
        except Exception:
            if self.conn:
                await self.conn.close()
                self.conn = None
            raise

    async def close(self):
        if self.conn:
            await self.conn.close()

    async def _column_exists(self, table: str, column: str) -> bool:
        cursor = await self._conn.execute(f"PRAGMA table_info({table})")
        columns = await cursor.fetchall()
        column_names = [col[1] for col in columns]
        return column in column_names

    async def _add_column(self, table: str, column: str, col_type: str, default=None):
        if not await self._column_exists(table, column):
            default_clause = ""
            if default is not None:
                if isinstance(default, str):
                    default_clause = f" DEFAULT '{default}'"
                else:
                    default_clause = f" DEFAULT {default}"
            sql = f"ALTER TABLE {table} ADD COLUMN {column} {col_type}{default_clause}"
            await self._conn.execute(sql)
            await self._conn.commit()
            logger.info(f"Migration: added {table}.{column}")

    async def run_migrations(self):
        logger.info("Running migrations...")
        await self._add_column("orders", "payment_method", "TEXT", "cash")
        await self._add_column("orders", "pickup_time", "TEXT", None)
        await self._add_column("orders", "pickup_reminded", "INTEGER", 0)
        await self._add_column("orders", "promotion_discount", "REAL", 0)
        await self._add_column("cart", "modifiers_json", "TEXT", "{}")
        await self._add_column("promotions", "apply_to", "TEXT", "all")
        # Feature I: geolocation fields on orders
        await self._add_column("orders", "delivery_lat", "REAL", None)
        await self._add_column("orders", "delivery_lon", "REAL", None)

        await self._conn.execute("DROP INDEX IF EXISTS idx_cart_user_product")
        await self._conn.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_cart_user_product_mods
            ON cart(user_id, product_id, modifiers_json)
        """)

        new_settings = {
            "pickup_address": "ул. Примерная, 1",
            "pickup_reminder_minutes": "15",
            "pickup_time_step": "15",
            "pickup_min_wait": "30",
            "analytics_daily_report": "0",
            "analytics_report_hour": "23",
            "geo_enabled": "0",
            "geo_provider": "osm",
            "geo_yandex_key": "",
            "favorites_enabled": "1",
            "favorites_max_items": "50",
        }
        for key, value in new_settings.items():
            await self._conn.execute(
                "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
                (key, value)
            )
        await self._conn.commit()
        logger.info("Migrations completed")

    async def create_tables(self):
        await self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                full_name TEXT,
                phone TEXT,
                address TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_banned INTEGER DEFAULT 0,
                total_orders INTEGER DEFAULT 0,
                total_spent REAL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                emoji TEXT DEFAULT '🍽',
                sort_order INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category_id INTEGER,
                name TEXT NOT NULL,
                description TEXT,
                price REAL NOT NULL,
                image_url TEXT,
                is_available INTEGER DEFAULT 1,
                sort_order INTEGER DEFAULT 0,
                FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS modifier_groups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                is_required INTEGER DEFAULT 0,
                is_multiple INTEGER DEFAULT 0,
                min_select INTEGER DEFAULT 0,
                max_select INTEGER DEFAULT 1,
                sort_order INTEGER DEFAULT 0,
                FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS modifier_options (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                price_change REAL DEFAULT 0,
                is_default INTEGER DEFAULT 0,
                is_available INTEGER DEFAULT 1,
                sort_order INTEGER DEFAULT 0,
                FOREIGN KEY (group_id) REFERENCES modifier_groups(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS cart (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                product_id INTEGER,
                quantity INTEGER DEFAULT 1,
                modifiers_json TEXT DEFAULT '{}',
                FOREIGN KEY (user_id) REFERENCES users(user_id),
                FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
            );

            CREATE UNIQUE INDEX IF NOT EXISTS idx_cart_user_product_mods
                ON cart(user_id, product_id, modifiers_json);

            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                items_json TEXT NOT NULL,
                total_price REAL NOT NULL,
                discount REAL DEFAULT 0,
                promotion_discount REAL DEFAULT 0,
                promo_code TEXT,
                delivery_type TEXT DEFAULT 'delivery',
                payment_method TEXT DEFAULT 'cash',
                address TEXT,
                phone TEXT,
                comment TEXT,
                pickup_time TEXT,
                pickup_reminded INTEGER DEFAULT 0,
                status TEXT DEFAULT 'new',
                courier_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            );

            CREATE TABLE IF NOT EXISTS order_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER NOT NULL,
                old_status TEXT,
                new_status TEXT NOT NULL,
                changed_by INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (order_id) REFERENCES orders(id)
            );

            CREATE TABLE IF NOT EXISTS promocodes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT UNIQUE NOT NULL,
                discount_type TEXT DEFAULT 'percent',
                discount_value REAL NOT NULL,
                min_order REAL DEFAULT 0,
                max_uses INTEGER DEFAULT -1,
                used_count INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 1,
                expires_at TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS promo_usages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                promo_id INTEGER,
                used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id),
                FOREIGN KEY (promo_id) REFERENCES promocodes(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS promotions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT,
                image_url TEXT,
                discount_percent REAL DEFAULT 0,
                apply_to TEXT DEFAULT 'all',
                category_id INTEGER,
                product_id INTEGER,
                is_active INTEGER DEFAULT 1,
                start_date TIMESTAMP,
                end_date TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS couriers (
                user_id INTEGER PRIMARY KEY,
                full_name TEXT,
                phone TEXT,
                is_active INTEGER DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            );

            INSERT OR IGNORE INTO settings (key, value) VALUES
                ('min_order_amount', '500'),
                ('delivery_price', '200'),
                ('free_delivery_from', '2000'),
                ('work_hours_start', '09:00'),
                ('work_hours_end', '23:00'),
                ('welcome_message', 'Добро пожаловать в наш бот доставки! 🍕'),
                ('order_confirmation_msg', 'Ваш заказ #{order_id} принят! Ожидайте подтверждения.'),
                ('bot_is_active', '1'),
                ('currency_symbol', '₽'),
                ('pickup_address', 'ул. Примерная, 1'),
                ('pickup_reminder_minutes', '15'),
                ('pickup_time_step', '15'),
                ('pickup_min_wait', '30'),
                ('analytics_daily_report', '0'),
                ('analytics_report_hour', '23'),
                ('geo_enabled', '0'),
                ('geo_provider', 'osm'),
                ('geo_yandex_key', ''),
                ('favorites_enabled', '1'),
                ('favorites_max_items', '50');

            -- Bug 17: indexes for orders table
            CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
            CREATE INDEX IF NOT EXISTS idx_orders_user_id ON orders(user_id);
            CREATE INDEX IF NOT EXISTS idx_orders_created ON orders(created_at);

            -- Feature F: Favourites
            CREATE TABLE IF NOT EXISTS favorites (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, product_id),
                FOREIGN KEY (user_id) REFERENCES users(user_id),
                FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
            );

            -- Feature I: Geolocation addresses
            CREATE TABLE IF NOT EXISTS delivery_addresses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                address_text TEXT NOT NULL,
                lat REAL,
                lon REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            );
        """)
        await self._conn.commit()

    # ==================== USERS ====================
    async def add_user(self, user_id: int, username: str, full_name: str):
        await self._conn.execute(
            "INSERT INTO users (user_id, username, full_name) VALUES (?, ?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET "
            "username=excluded.username, full_name=excluded.full_name",
            (user_id, username, full_name)
        )
        await self._conn.commit()

    async def get_user(self, user_id: int):
        cursor = await self._conn.execute(
            "SELECT * FROM users WHERE user_id = ?", (user_id,)
        )
        return await cursor.fetchone()

    async def update_user(self, user_id: int, **kwargs):
        _validate_columns("users", kwargs)
        sets = ", ".join(f"{k} = ?" for k in kwargs)
        values = list(kwargs.values()) + [user_id]
        await self._conn.execute(f"UPDATE users SET {sets} WHERE user_id = ?", values)
        await self._conn.commit()

    async def get_all_users(self):
        cursor = await self._conn.execute("SELECT * FROM users ORDER BY created_at DESC")
        return await cursor.fetchall()

    async def get_users_count(self):
        cursor = await self._conn.execute("SELECT COUNT(*) FROM users")
        row = await cursor.fetchone()
        return row[0]

    # ==================== CATEGORIES ====================
    async def get_categories(self, only_active=True):
        query = "SELECT * FROM categories"
        if only_active:
            query += " WHERE is_active = 1"
        query += " ORDER BY sort_order, name"
        cursor = await self._conn.execute(query)
        return await cursor.fetchall()

    async def add_category(self, name: str, emoji: str = "🍽"):
        await self._conn.execute(
            "INSERT INTO categories (name, emoji) VALUES (?, ?)", (name, emoji)
        )
        await self._conn.commit()

    async def update_category(self, cat_id: int, **kwargs):
        _validate_columns("categories", kwargs)
        sets = ", ".join(f"{k} = ?" for k in kwargs)
        values = list(kwargs.values()) + [cat_id]
        await self._conn.execute(f"UPDATE categories SET {sets} WHERE id = ?", values)
        await self._conn.commit()

    async def delete_category(self, cat_id: int):
        await self._conn.execute("""
            DELETE FROM modifier_options WHERE group_id IN (
                SELECT mg.id FROM modifier_groups mg
                JOIN products p ON mg.product_id = p.id
                WHERE p.category_id = ?
            )
        """, (cat_id,))
        await self._conn.execute("""
            DELETE FROM modifier_groups WHERE product_id IN (
                SELECT id FROM products WHERE category_id = ?
            )
        """, (cat_id,))
        await self._conn.execute(
            "DELETE FROM cart WHERE product_id IN (SELECT id FROM products WHERE category_id = ?)",
            (cat_id,)
        )
        await self._conn.execute(
            "DELETE FROM products WHERE category_id = ?", (cat_id,)
        )
        await self._conn.execute(
            "DELETE FROM categories WHERE id = ?", (cat_id,)
        )
        await self._conn.commit()

    async def get_category(self, cat_id: int):
        cursor = await self._conn.execute(
            "SELECT * FROM categories WHERE id = ?", (cat_id,)
        )
        return await cursor.fetchone()

    # ==================== PRODUCTS ====================
    async def get_products(self, category_id: int, only_available=True):
        query = "SELECT * FROM products WHERE category_id = ?"
        if only_available:
            query += " AND is_available = 1"
        query += " ORDER BY sort_order, name"
        cursor = await self._conn.execute(query, (category_id,))
        return await cursor.fetchall()

    async def get_product(self, product_id: int):
        cursor = await self._conn.execute(
            "SELECT * FROM products WHERE id = ?", (product_id,)
        )
        return await cursor.fetchone()

    async def add_product(self, category_id: int, name: str, description: str,
                          price: float, image_url: str = None):
        cursor = await self._conn.execute(
            "INSERT INTO products (category_id, name, description, price, image_url) "
            "VALUES (?, ?, ?, ?, ?)",
            (category_id, name, description, price, image_url)
        )
        await self._conn.commit()
        return cursor.lastrowid

    async def update_product(self, product_id: int, **kwargs):
        _validate_columns("products", kwargs)
        sets = ", ".join(f"{k} = ?" for k in kwargs)
        values = list(kwargs.values()) + [product_id]
        await self._conn.execute(f"UPDATE products SET {sets} WHERE id = ?", values)
        await self._conn.commit()

    async def delete_product(self, product_id: int):
        await self._conn.execute("""
            DELETE FROM modifier_options WHERE group_id IN (
                SELECT id FROM modifier_groups WHERE product_id = ?
            )
        """, (product_id,))
        await self._conn.execute(
            "DELETE FROM modifier_groups WHERE product_id = ?", (product_id,)
        )
        await self._conn.execute(
            "DELETE FROM cart WHERE product_id = ?", (product_id,)
        )
        await self._conn.execute(
            "DELETE FROM products WHERE id = ?", (product_id,)
        )
        await self._conn.commit()

    async def get_all_products(self):
        cursor = await self._conn.execute(
            "SELECT p.*, c.name as category_name FROM products p "
            "LEFT JOIN categories c ON p.category_id = c.id ORDER BY c.name, p.name"
        )
        return await cursor.fetchall()

    # ==================== MODIFIER GROUPS ====================
    async def get_modifier_groups(self, product_id: int):
        cursor = await self._conn.execute(
            "SELECT * FROM modifier_groups WHERE product_id = ? ORDER BY sort_order, id",
            (product_id,)
        )
        return await cursor.fetchall()

    async def get_modifier_group(self, group_id: int):
        cursor = await self._conn.execute(
            "SELECT * FROM modifier_groups WHERE id = ?", (group_id,)
        )
        return await cursor.fetchone()

    async def add_modifier_group(self, product_id: int, name: str,
                                  is_required: int = 0, is_multiple: int = 0,
                                  min_select: int = 0, max_select: int = 1):
        cursor = await self._conn.execute(
            "INSERT INTO modifier_groups "
            "(product_id, name, is_required, is_multiple, min_select, max_select) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (product_id, name, is_required, is_multiple, min_select, max_select)
        )
        await self._conn.commit()
        return cursor.lastrowid

    async def update_modifier_group(self, group_id: int, **kwargs):
        _validate_columns("modifier_groups", kwargs)
        sets = ", ".join(f"{k} = ?" for k in kwargs)
        values = list(kwargs.values()) + [group_id]
        await self._conn.execute(
            f"UPDATE modifier_groups SET {sets} WHERE id = ?", values
        )
        await self._conn.commit()

    async def delete_modifier_group(self, group_id: int):
        await self._conn.execute(
            "DELETE FROM modifier_options WHERE group_id = ?", (group_id,)
        )
        await self._conn.execute(
            "DELETE FROM modifier_groups WHERE id = ?", (group_id,)
        )
        await self._conn.commit()

    # ==================== MODIFIER OPTIONS ====================
    async def get_modifier_options(self, group_id: int, only_available: bool = True):
        query = "SELECT * FROM modifier_options WHERE group_id = ?"
        if only_available:
            query += " AND is_available = 1"
        query += " ORDER BY sort_order, id"
        cursor = await self._conn.execute(query, (group_id,))
        return await cursor.fetchall()

    async def get_modifier_option(self, option_id: int):
        cursor = await self._conn.execute(
            "SELECT * FROM modifier_options WHERE id = ?", (option_id,)
        )
        return await cursor.fetchone()

    async def add_modifier_option(self, group_id: int, name: str,
                                   price_change: float = 0, is_default: int = 0):
        cursor = await self._conn.execute(
            "INSERT INTO modifier_options (group_id, name, price_change, is_default) "
            "VALUES (?, ?, ?, ?)",
            (group_id, name, price_change, is_default)
        )
        await self._conn.commit()
        return cursor.lastrowid

    async def update_modifier_option(self, option_id: int, **kwargs):
        _validate_columns("modifier_options", kwargs)
        sets = ", ".join(f"{k} = ?" for k in kwargs)
        values = list(kwargs.values()) + [option_id]
        await self._conn.execute(
            f"UPDATE modifier_options SET {sets} WHERE id = ?", values
        )
        await self._conn.commit()

    async def delete_modifier_option(self, option_id: int):
        await self._conn.execute(
            "DELETE FROM modifier_options WHERE id = ?", (option_id,)
        )
        await self._conn.commit()

    async def get_product_full_modifiers(self, product_id: int):
        groups = await self.get_modifier_groups(product_id)
        result = []
        for g in groups:
            options = await self.get_modifier_options(g['id'])
            result.append({"group": g, "options": list(options)})
        return result

    # ==================== CART ====================
    async def add_to_cart(self, user_id: int, product_id: int,
                          quantity: int = 1, modifiers_json: str = "{}"):
        cursor = await self._conn.execute(
            "SELECT id, quantity FROM cart "
            "WHERE user_id = ? AND product_id = ? AND modifiers_json = ?",
            (user_id, product_id, modifiers_json)
        )
        existing = await cursor.fetchone()
        if existing:
            new_qty = existing[1] + quantity
            if new_qty <= 0:
                await self._conn.execute("DELETE FROM cart WHERE id = ?", (existing[0],))
            else:
                await self._conn.execute(
                    "UPDATE cart SET quantity = ? WHERE id = ?", (new_qty, existing[0])
                )
        else:
            if quantity > 0:
                await self._conn.execute(
                    "INSERT INTO cart (user_id, product_id, quantity, modifiers_json) "
                    "VALUES (?, ?, ?, ?)",
                    (user_id, product_id, quantity, modifiers_json)
                )
        await self._conn.commit()

    async def get_cart(self, user_id: int):
        cursor = await self._conn.execute(
            "SELECT c.id, c.quantity, c.modifiers_json, "
            "p.id as product_id, p.name, p.price, p.is_available, p.category_id "
            "FROM cart c JOIN products p ON c.product_id = p.id "
            "WHERE c.user_id = ?",
            (user_id,)
        )
        return await cursor.fetchall()

    async def get_cart_total(self, user_id: int) -> float:
        items = await self.get_cart(user_id)
        total = 0.0
        for item in items:
            mods = parse_modifiers_price(item['modifiers_json'])
            total += (item['price'] + mods) * item['quantity']
        return total

    async def update_cart_item(self, cart_id: int, quantity: int, user_id: int = None):
        if quantity <= 0:
            await self.remove_from_cart(cart_id, user_id)
        else:
            if user_id is not None:
                await self._conn.execute(
                    "UPDATE cart SET quantity = ? WHERE id = ? AND user_id = ?",
                    (quantity, cart_id, user_id)
                )
            else:
                await self._conn.execute(
                    "UPDATE cart SET quantity = ? WHERE id = ?", (quantity, cart_id)
                )
            await self._conn.commit()

    async def remove_from_cart(self, cart_id: int, user_id: int = None):
        if user_id is not None:
            await self._conn.execute(
                "DELETE FROM cart WHERE id = ? AND user_id = ?", (cart_id, user_id)
            )
        else:
            await self._conn.execute("DELETE FROM cart WHERE id = ?", (cart_id,))
        await self._conn.commit()

    async def clear_cart(self, user_id: int):
        await self._conn.execute("DELETE FROM cart WHERE user_id = ?", (user_id,))
        await self._conn.commit()

    async def get_cart_count(self, user_id: int):
        cursor = await self._conn.execute(
            "SELECT COALESCE(SUM(quantity), 0) FROM cart WHERE user_id = ?",
            (user_id,)
        )
        row = await cursor.fetchone()
        return row[0]

    # ==================== ORDERS ====================
    async def create_order(self, user_id: int, items_json: str, total_price: float,
                           discount: float, promotion_discount: float,
                           promo_code: str, delivery_type: str,
                           payment_method: str, address: str, phone: str,
                           comment: str, pickup_time: str = None) -> int:
        # В aiosqlite `async with connection` пытается переоткрыть соединение.
        # Правильный способ транзакции — явный BEGIN/COMMIT/ROLLBACK через execute.
        try:
            await self._conn.execute("BEGIN")
            cursor = await self._conn.execute(
                "INSERT INTO orders (user_id, items_json, total_price, discount, "
                "promotion_discount, promo_code, delivery_type, payment_method, "
                "address, phone, comment, pickup_time) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (user_id, items_json, total_price, discount, promotion_discount,
                 promo_code, delivery_type, payment_method, address, phone,
                 comment, pickup_time)
            )
            order_id = cursor.lastrowid
            await self._conn.execute(
                "UPDATE users SET total_orders = total_orders + 1, "
                "total_spent = total_spent + ? WHERE user_id = ?",
                (total_price, user_id)
            )
            await self._conn.execute(
                "INSERT INTO order_history (order_id, old_status, new_status, changed_by) "
                "VALUES (?, NULL, 'new', ?)",
                (order_id, user_id)
            )
            await self._conn.commit()
            return order_id
        except Exception:
            await self._conn.execute("ROLLBACK")
            raise

    async def get_order(self, order_id: int):
        cursor = await self._conn.execute(
            "SELECT o.*, u.username, u.full_name as user_fullname "
            "FROM orders o LEFT JOIN users u ON o.user_id = u.user_id "
            "WHERE o.id = ?",
            (order_id,)
        )
        return await cursor.fetchone()

    async def get_user_orders(self, user_id: int, limit: int = 10):
        cursor = await self._conn.execute(
            "SELECT * FROM orders WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
            (user_id, limit)
        )
        return await cursor.fetchall()

    async def update_order_status(self, order_id: int, status: str,
                                   changed_by: int = None):
        order = await self.get_order(order_id)
        if not order:
            raise ValueError(f"Заказ #{order_id} не найден")
        TERMINAL = {"cancelled", "completed"}
        if order['status'] in TERMINAL:
            raise ValueError(f"Нельзя изменить статус завершённого заказа: {order['status']}")
        old_status = order['status']
        await self._conn.execute(
            "UPDATE orders SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (status, order_id)
        )
        await self._conn.execute(
            "INSERT INTO order_history (order_id, old_status, new_status, changed_by) "
            "VALUES (?, ?, ?, ?)",
            (order_id, old_status, status, changed_by)
        )
        await self._conn.commit()

    async def assign_courier(self, order_id: int, courier_id: int, changed_by: int = None):
        order = await self.get_order(order_id)
        old_status = order['status'] if order else None
        await self._conn.execute(
            "UPDATE orders SET courier_id = ?, status = 'courier_assigned', "
            "updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (courier_id, order_id)
        )
        await self._conn.execute(
            "INSERT INTO order_history (order_id, old_status, new_status, changed_by) "
            "VALUES (?, ?, 'courier_assigned', ?)",
            (order_id, old_status, changed_by)
        )
        await self._conn.commit()

    async def get_orders_by_status(self, status: str):
        cursor = await self._conn.execute(
            "SELECT o.*, u.full_name as user_fullname, u.phone as user_phone "
            "FROM orders o LEFT JOIN users u ON o.user_id = u.user_id "
            "WHERE o.status = ? ORDER BY o.created_at DESC",
            (status,)
        )
        return await cursor.fetchall()

    async def get_all_orders(self, limit: int = 50):
        cursor = await self._conn.execute(
            "SELECT o.*, u.full_name as user_fullname "
            "FROM orders o LEFT JOIN users u ON o.user_id = u.user_id "
            "ORDER BY o.created_at DESC LIMIT ?",
            (limit,)
        )
        return await cursor.fetchall()

    async def get_today_stats(self):
        from datetime import datetime
        import pytz
        today = datetime.now(pytz.timezone(config.TIMEZONE)).strftime("%Y-%m-%d")
        cursor = await self._conn.execute(
            "SELECT COUNT(*) as cnt, COALESCE(SUM(total_price), 0) as total "
            "FROM orders WHERE date(created_at) = ?",
            (today,)
        )
        return await cursor.fetchone()

    async def get_pending_pickup_orders(self):
        cursor = await self._conn.execute(
            "SELECT o.*, u.full_name as user_fullname, u.phone as user_phone "
            "FROM orders o LEFT JOIN users u ON o.user_id = u.user_id "
            "WHERE o.delivery_type = 'pickup' "
            "AND o.pickup_time IS NOT NULL AND o.pickup_time != '' "
            "AND o.pickup_reminded = 0 "
            "AND o.status NOT IN ('cancelled', 'completed', 'delivered')"
        )
        return await cursor.fetchall()

    async def mark_pickup_reminded(self, order_id: int):
        await self._conn.execute(
            "UPDATE orders SET pickup_reminded = 1 WHERE id = ?", (order_id,)
        )
        await self._conn.commit()

    # ==================== PROMOCODES ====================
    async def get_promocode(self, code: str):
        cursor = await self._conn.execute(
            "SELECT * FROM promocodes WHERE code = ? AND is_active = 1",
            (code.upper(),)
        )
        return await cursor.fetchone()

    async def add_promocode(self, code: str, discount_type: str, discount_value: float,
                            min_order: float = 0, max_uses: int = -1, expires_at: str = None):
        await self._conn.execute(
            "INSERT INTO promocodes (code, discount_type, discount_value, min_order, "
            "max_uses, expires_at) VALUES (?, ?, ?, ?, ?, ?)",
            (code.upper(), discount_type, discount_value, min_order, max_uses, expires_at)
        )
        await self._conn.commit()

    async def use_promocode(self, promo_id: int, user_id: int):
        await self._conn.execute(
            "UPDATE promocodes SET used_count = used_count + 1 WHERE id = ?",
            (promo_id,)
        )
        await self._conn.execute(
            "INSERT INTO promo_usages (user_id, promo_id) VALUES (?, ?)",
            (user_id, promo_id)
        )
        await self._conn.commit()

    async def check_promo_used_by_user(self, user_id: int, promo_id: int):
        cursor = await self._conn.execute(
            "SELECT COUNT(*) FROM promo_usages WHERE user_id = ? AND promo_id = ?",
            (user_id, promo_id)
        )
        row = await cursor.fetchone()
        return row[0] > 0

    async def get_all_promocodes(self):
        cursor = await self._conn.execute("SELECT * FROM promocodes ORDER BY id DESC")
        return await cursor.fetchall()

    async def delete_promocode(self, promo_id: int):
        await self._conn.execute(
            "DELETE FROM promo_usages WHERE promo_id = ?", (promo_id,)
        )
        await self._conn.execute(
            "DELETE FROM promocodes WHERE id = ?", (promo_id,)
        )
        await self._conn.commit()

    # ==================== PROMOTIONS ====================
    async def get_active_promotions(self):
        cursor = await self._conn.execute(
            "SELECT * FROM promotions WHERE is_active = 1 "
            "AND (start_date IS NULL OR start_date <= datetime('now')) "
            "AND (end_date IS NULL OR end_date >= datetime('now')) "
            "ORDER BY id DESC"
        )
        return await cursor.fetchall()

    async def add_promotion(self, title: str, description: str,
                            discount_percent: float = 0, apply_to: str = "all",
                            category_id: int = None, product_id: int = None,
                            image_url: str = None):
        await self._conn.execute(
            "INSERT INTO promotions (title, description, discount_percent, "
            "apply_to, category_id, product_id, image_url) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (title, description, discount_percent, apply_to,
             category_id, product_id, image_url)
        )
        await self._conn.commit()

    async def update_promotion(self, promo_id: int, **kwargs):
        _validate_columns("promotions", kwargs)
        sets = ", ".join(f"{k} = ?" for k in kwargs)
        values = list(kwargs.values()) + [promo_id]
        await self._conn.execute(f"UPDATE promotions SET {sets} WHERE id = ?", values)
        await self._conn.commit()

    async def delete_promotion(self, promo_id: int):
        await self._conn.execute(
            "DELETE FROM promotions WHERE id = ?", (promo_id,)
        )
        await self._conn.commit()

    async def get_all_promotions(self):
        cursor = await self._conn.execute("SELECT * FROM promotions ORDER BY id DESC")
        return await cursor.fetchall()

    async def get_promotion(self, promo_id: int):
        cursor = await self._conn.execute(
            "SELECT * FROM promotions WHERE id = ?", (promo_id,)
        )
        return await cursor.fetchone()

    async def get_promotions_for_product(self, product_id: int, category_id: int):
        cursor = await self._conn.execute(
            "SELECT * FROM promotions WHERE is_active = 1 "
            "AND (start_date IS NULL OR start_date <= datetime('now')) "
            "AND (end_date IS NULL OR end_date >= datetime('now')) "
            "AND ("
            "  apply_to = 'all' "
            "  OR (apply_to = 'category' AND category_id = ?) "
            "  OR (apply_to = 'product' AND product_id = ?)"
            ") ORDER BY discount_percent DESC",
            (category_id, product_id)
        )
        return await cursor.fetchall()

    # ==================== COURIERS ====================
    async def add_courier(self, user_id: int, full_name: str, phone: str):
        await self._conn.execute(
            "INSERT OR REPLACE INTO couriers (user_id, full_name, phone) VALUES (?, ?, ?)",
            (user_id, full_name, phone)
        )
        await self._conn.commit()

    async def get_couriers(self, only_active=True):
        query = "SELECT * FROM couriers"
        if only_active:
            query += " WHERE is_active = 1"
        cursor = await self._conn.execute(query)
        return await cursor.fetchall()

    async def get_courier(self, user_id: int):
        cursor = await self._conn.execute(
            "SELECT * FROM couriers WHERE user_id = ?", (user_id,)
        )
        return await cursor.fetchone()

    async def delete_courier(self, user_id: int):
        await self._conn.execute(
            "DELETE FROM couriers WHERE user_id = ?", (user_id,)
        )
        await self._conn.commit()

    # ==================== SETTINGS ====================
    async def get_setting(self, key: str):
        from utils.cache import settings_cache
        cached = settings_cache.get(f"s_{key}")
        if cached is not None:
            return cached
        cursor = await self._conn.execute(
            "SELECT value FROM settings WHERE key = ?", (key,)
        )
        row = await cursor.fetchone()
        value = row[0] if row else None
        if value is not None:
            settings_cache.set(f"s_{key}", value)
        return value

    async def set_setting(self, key: str, value: str):
        await self._conn.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            (key, value)
        )
        await self._conn.commit()
        from utils.cache import settings_cache
        settings_cache.invalidate(f"s_{key}")

    async def get_all_settings(self):
        cursor = await self._conn.execute("SELECT * FROM settings")
        rows = await cursor.fetchall()
        return {row[0]: row[1] for row in rows}

    # ==================== FAVOURITES ====================
    async def add_favorite(self, user_id: int, product_id: int) -> bool:
        """Returns True if added, False if already exists."""
        try:
            await self._conn.execute(
                "INSERT INTO favorites (user_id, product_id) VALUES (?, ?)",
                (user_id, product_id)
            )
            await self._conn.commit()
            return True
        except Exception:
            return False

    async def remove_favorite(self, user_id: int, product_id: int):
        await self._conn.execute(
            "DELETE FROM favorites WHERE user_id = ? AND product_id = ?",
            (user_id, product_id)
        )
        await self._conn.commit()

    async def is_favorite(self, user_id: int, product_id: int) -> bool:
        cursor = await self._conn.execute(
            "SELECT id FROM favorites WHERE user_id = ? AND product_id = ?",
            (user_id, product_id)
        )
        return await cursor.fetchone() is not None

    async def get_favorites(self, user_id: int):
        cursor = await self._conn.execute(
            "SELECT p.*, c.name as category_name, c.emoji as category_emoji "
            "FROM favorites f "
            "JOIN products p ON f.product_id = p.id "
            "LEFT JOIN categories c ON p.category_id = c.id "
            "WHERE f.user_id = ? AND p.is_available = 1 "
            "ORDER BY f.created_at DESC",
            (user_id,)
        )
        return await cursor.fetchall()

    async def get_favorites_count(self, user_id: int) -> int:
        cursor = await self._conn.execute(
            "SELECT COUNT(*) FROM favorites WHERE user_id = ?", (user_id,)
        )
        row = await cursor.fetchone()
        return row[0]

    # ==================== ANALYTICS ====================
    async def get_analytics_stats(self, days: int = 7) -> list:
        """Revenue by day for the last N days."""
        cursor = await self._conn.execute(
            "SELECT date(created_at) as day, "
            "COUNT(*) as orders_count, "
            "COALESCE(SUM(total_price), 0) as revenue "
            "FROM orders "
            "WHERE created_at >= datetime('now', ?) "
            "AND status NOT IN ('cancelled') "
            "GROUP BY date(created_at) ORDER BY day",
            (f"-{days} days",)
        )
        return await cursor.fetchall()

    async def get_top_products(self, limit: int = 10) -> list:
        """Top products by total quantity across all non-cancelled orders."""
        cursor = await self._conn.execute(
            "SELECT items_json FROM orders WHERE status NOT IN ('cancelled')"
        )
        orders = await cursor.fetchall()
        from collections import Counter
        counter: Counter = Counter()
        for o in orders:
            try:
                items = json.loads(o['items_json'])
                for item in items:
                    counter[item['name']] += item.get('quantity', 1)
            except Exception:
                pass
        return [{"name": name, "order_count": cnt}
                for name, cnt in counter.most_common(limit)]

    async def get_top_clients(self, limit: int = 10) -> list:
        """Top clients by total spent."""
        cursor = await self._conn.execute(
            "SELECT u.user_id, u.username, u.full_name, "
            "u.total_orders, u.total_spent "
            "FROM users u "
            "ORDER BY u.total_spent DESC LIMIT ?",
            (limit,)
        )
        return await cursor.fetchall()

    async def get_full_analytics(self, days: int = 7) -> dict:
        """Combined analytics report."""
        stats = await self.get_analytics_stats(days)
        top_products = await self.get_top_products(10)
        top_clients = await self.get_top_clients(10)
        cursor = await self._conn.execute(
            "SELECT COUNT(*) as cnt, COALESCE(SUM(total_price), 0) as total "
            "FROM orders WHERE status NOT IN ('cancelled')"
        )
        totals = await cursor.fetchone()
        return {
            "daily_stats": stats,
            "top_products": top_products,
            "top_clients": top_clients,
            "all_time_orders": totals[0],
            "all_time_revenue": totals[1],
        }

    async def export_orders_csv(self, days: int = 30) -> str:
        """Export orders to CSV string."""
        import csv
        import io
        cursor = await self._conn.execute(
            "SELECT o.id, o.user_id, u.full_name, u.username, "
            "o.total_price, o.status, o.delivery_type, o.payment_method, "
            "o.address, o.phone, o.created_at "
            "FROM orders o LEFT JOIN users u ON o.user_id = u.user_id "
            "WHERE o.created_at >= datetime('now', ?) "
            "ORDER BY o.created_at DESC",
            (f"-{days} days",)
        )
        rows = await cursor.fetchall()
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["ID", "UserID", "ФИО", "Username", "Сумма",
                         "Статус", "Тип доставки", "Оплата", "Адрес",
                         "Телефон", "Дата"])
        for r in rows:
            writer.writerow(list(r))
        return output.getvalue()

    # ==================== GEOLOCATION ====================
    async def save_delivery_address(self, user_id: int, address_text: str,
                                    lat: float = None, lon: float = None) -> int:
        cursor = await self._conn.execute(
            "INSERT INTO delivery_addresses (user_id, address_text, lat, lon) "
            "VALUES (?, ?, ?, ?)",
            (user_id, address_text, lat, lon)
        )
        await self._conn.commit()
        return cursor.lastrowid

    async def get_user_addresses(self, user_id: int, limit: int = 5):
        cursor = await self._conn.execute(
            "SELECT * FROM delivery_addresses WHERE user_id = ? "
            "ORDER BY created_at DESC LIMIT ?",
            (user_id, limit)
        )
        return await cursor.fetchall()


db = Database()