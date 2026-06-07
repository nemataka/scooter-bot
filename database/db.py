import aiosqlite
import math
from config import DB_NAME


async def init_db():
    """Маълумотлар базасини яратиш"""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                role TEXT DEFAULT 'pending',
                phone TEXT,
                is_active BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                order_id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_name TEXT NOT NULL,
                client_phone TEXT NOT NULL,
                delivery_address TEXT NOT NULL,
                order_details TEXT,
                amount REAL DEFAULT 0,
                status TEXT DEFAULT 'new',
                courier_id INTEGER,
                created_by INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                assigned_at TIMESTAMP,
                completed_at TIMESTAMP,
                cancelled_at TIMESTAMP,
                cancel_reason TEXT,
                FOREIGN KEY (courier_id) REFERENCES users(user_id),
                FOREIGN KEY (created_by) REFERENCES users(user_id)
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS broadcast_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER,
                courier_id INTEGER,
                message_id INTEGER,
                FOREIGN KEY (order_id) REFERENCES orders(order_id)
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS deposits (
                deposit_id INTEGER PRIMARY KEY AUTOINCREMENT,
                courier_id INTEGER,
                amount REAL NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (courier_id) REFERENCES users(user_id)
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER,
                courier_id INTEGER,
                amount REAL NOT NULL,
                commission REAL NOT NULL,
                type TEXT DEFAULT 'commission',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (order_id) REFERENCES orders(order_id),
                FOREIGN KEY (courier_id) REFERENCES users(user_id)
            )
        """)

        # ─── 1. settings, delivery_orders, delivery_tracking жадваллари ───
        await db.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS delivery_orders (
                delivery_id INTEGER PRIMARY KEY AUTOINCREMENT,
                courier_id INTEGER,
                admin_id INTEGER NOT NULL,
                client_name TEXT,
                client_phone TEXT,
                from_address TEXT,
                to_address TEXT,
                status TEXT DEFAULT 'new',
                start_lat REAL,
                start_lon REAL,
                end_lat REAL,
                end_lon REAL,
                total_km REAL DEFAULT 0,
                wait_minutes REAL DEFAULT 0,
                total_price REAL DEFAULT 0,
                started_at TIMESTAMP,
                finished_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (courier_id) REFERENCES users(user_id)
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS delivery_tracking (
                track_id INTEGER PRIMARY KEY AUTOINCREMENT,
                delivery_id INTEGER NOT NULL,
                latitude REAL NOT NULL,
                longitude REAL NOT NULL,
                speed REAL DEFAULT 0,
                mode TEXT DEFAULT 'moving',
                recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (delivery_id) REFERENCES delivery_orders(delivery_id)
            )
        """)

        await db.execute("""
            INSERT OR IGNORE INTO settings (key, value) VALUES
                ('km_price', '2000'),
                ('wait_free_minutes', '5'),
                ('wait_price_per_minute', '500'),
                ('speed_threshold', '5'),
                ('commission_percent', '15')
        """)

        await db.commit()


# ─── USER ───────────────────────────────────────────

async def add_user(user_id, username, first_name, last_name):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "INSERT OR IGNORE INTO users (user_id, username, first_name, last_name) VALUES (?, ?, ?, ?)",
            (user_id, username, first_name, last_name)
        )
        await db.commit()


async def get_user(user_id):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        return await cursor.fetchone()


async def update_user_role(user_id, role):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE users SET role = ? WHERE user_id = ?", (role, user_id))
        await db.commit()


async def get_all_couriers():
    """Барча курьерлар (фаол + блокланган)"""
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(
            "SELECT * FROM users WHERE role = 'courier'"
        )
        return await cursor.fetchall()


async def get_active_couriers():
    """Фақат фаол курьерлар (заказ учун)"""
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(
            "SELECT * FROM users WHERE role = 'courier' AND is_active = 1"
        )
        return await cursor.fetchall()


async def toggle_courier_active(courier_id: int, is_active: bool):
    """Курьерни блоклаш / фаоллаштириш"""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "UPDATE users SET is_active = ? WHERE user_id = ?",
            (1 if is_active else 0, courier_id)
        )
        await db.commit()


async def get_all_admins():
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT * FROM users WHERE role = 'admin'")
        return await cursor.fetchall()


async def get_pending_couriers():
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT * FROM users WHERE role = 'pending'")
        return await cursor.fetchall()


# ─── ORDER ──────────────────────────────────────────

async def create_order(client_name, client_phone, delivery_address,
                       order_details, amount, created_by):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(
            """INSERT INTO orders 
               (client_name, client_phone, delivery_address, order_details, amount, created_by)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (client_name, client_phone, delivery_address, order_details, amount, created_by)
        )
        await db.commit()
        return cursor.lastrowid


async def get_order(order_id):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT * FROM orders WHERE order_id = ?", (order_id,))
        return await cursor.fetchone()


async def assign_order(order_id, courier_id):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "UPDATE orders SET courier_id = ?, status = 'assigned', assigned_at = CURRENT_TIMESTAMP WHERE order_id = ?",
            (courier_id, order_id)
        )
        await db.commit()


async def assign_order_atomic(order_id: int, courier_id: int) -> bool:
    """
    Broadcast заказни курьерга атомар бириктириш.
    Фақат status='broadcast' бўлса UPDATE қилади.
    True  — муваффақиятли
    False — бошқа курьер олган
    """
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(
            """UPDATE orders
               SET courier_id = ?,
                   status = 'assigned',
                   assigned_at = CURRENT_TIMESTAMP
               WHERE order_id = ? AND status = 'broadcast'""",
            (courier_id, order_id)
        )
        await db.commit()
        return cursor.rowcount == 1
    

async def update_order_status(order_id, status, courier_id=None, reason=None):
    async with aiosqlite.connect(DB_NAME) as db:
        if status == 'completed':
            await db.execute(
                "UPDATE orders SET status = ?, completed_at = CURRENT_TIMESTAMP WHERE order_id = ?",
                (status, order_id)
            )
        elif status == 'cancelled':
            await db.execute(
                "UPDATE orders SET status = ?, cancelled_at = CURRENT_TIMESTAMP, cancel_reason = ? WHERE order_id = ?",
                (status, reason, order_id)
            )
        else:
            await db.execute(
                "UPDATE orders SET status = ? WHERE order_id = ?",
                (status, order_id)
            )
        await db.commit()


async def get_orders_by_status(status):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(
            """SELECT o.*, u.first_name, u.username
               FROM orders o
               LEFT JOIN users u ON o.courier_id = u.user_id
               WHERE o.status = ?
               ORDER BY o.created_at DESC""",
            (status,)
        )
        return await cursor.fetchall()


async def get_courier_orders(courier_id, status=None):
    async with aiosqlite.connect(DB_NAME) as db:
        if status:
            cursor = await db.execute(
                "SELECT * FROM orders WHERE courier_id = ? AND status = ? ORDER BY created_at DESC",
                (courier_id, status)
            )
        else:
            cursor = await db.execute(
                "SELECT * FROM orders WHERE courier_id = ? ORDER BY created_at DESC",
                (courier_id,)
            )
        return await cursor.fetchall()


async def get_all_orders():
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT * FROM orders ORDER BY created_at DESC")
        return await cursor.fetchall()


async def get_stats_by_courier(courier_id, start_date=None, end_date=None):
    async with aiosqlite.connect(DB_NAME) as db:
        query = """
            SELECT
                COUNT(*) as total,
                COALESCE(SUM(CASE WHEN status='completed' THEN amount ELSE 0 END), 0) as total_amount,
                COUNT(CASE WHEN status='completed' THEN 1 END) as completed,
                COUNT(CASE WHEN status='cancelled' THEN 1 END) as cancelled
            FROM orders
            WHERE courier_id = ?
        """
        params = [courier_id]
        if start_date and end_date:
            query += " AND created_at BETWEEN ? AND ?"
            params.extend([start_date, end_date])
        cursor = await db.execute(query, params)
        return await cursor.fetchone()


async def get_general_stats(start_date=None, end_date=None):
    async with aiosqlite.connect(DB_NAME) as db:
        query = """
            SELECT
                COUNT(*) as total,
                COALESCE(SUM(CASE WHEN status='completed' THEN amount ELSE 0 END), 0) as total_amount,
                COUNT(CASE WHEN status='completed' THEN 1 END) as completed,
                COUNT(CASE WHEN status='assigned' THEN 1 END) as in_progress,
                COUNT(CASE WHEN status='new' THEN 1 END) as new_orders,
                COUNT(CASE WHEN status='cancelled' THEN 1 END) as cancelled
            FROM orders WHERE 1=1
        """
        params = []
        if start_date and end_date:
            query += " AND created_at BETWEEN ? AND ?"
            params.extend([start_date, end_date])
        cursor = await db.execute(query, params)
        return await cursor.fetchone()


async def save_broadcast_message(order_id, courier_id, message_id):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "INSERT INTO broadcast_messages (order_id, courier_id, message_id) VALUES (?, ?, ?)",
            (order_id, courier_id, message_id)
        )
        await db.commit()


async def get_broadcast_messages(order_id):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(
            "SELECT courier_id, message_id FROM broadcast_messages WHERE order_id = ?",
            (order_id,)
        )
        return await cursor.fetchall()


async def delete_broadcast_messages(order_id):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("DELETE FROM broadcast_messages WHERE order_id = ?", (order_id,))
        await db.commit()


# ─── DEPOSIT ────────────────────────────────────────

async def add_deposit(courier_id, amount):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "INSERT INTO deposits (courier_id, amount) VALUES (?, ?)",
            (courier_id, amount)
        )
        await db.commit()


async def get_courier_balance(courier_id):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM deposits WHERE courier_id = ?",
            (courier_id,)
        )
        total_deposits = (await cursor.fetchone())[0]

        cursor = await db.execute(
            "SELECT COALESCE(SUM(commission), 0) FROM transactions WHERE courier_id = ?",
            (courier_id,)
        )
        total_commission = (await cursor.fetchone())[0]

        return total_deposits - total_commission


async def add_transaction(order_id, courier_id, amount, commission):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "INSERT INTO transactions (order_id, courier_id, amount, commission) VALUES (?, ?, ?, ?)",
            (order_id, courier_id, amount, commission)
        )
        await db.commit()


async def get_courier_transactions(courier_id):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(
            "SELECT * FROM transactions WHERE courier_id = ? ORDER BY created_at DESC",
            (courier_id,)
        )
        return await cursor.fetchall()


async def get_all_deposits():
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(
            """SELECT d.*, u.first_name, u.username
               FROM deposits d
               JOIN users u ON d.courier_id = u.user_id
               ORDER BY d.created_at DESC"""
        )
        return await cursor.fetchall()


# ─── SETTINGS ───────────────────────────────────────────

async def get_setting(key: str):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(
            "SELECT value FROM settings WHERE key = ?", (key,)
        )
        row = await cursor.fetchone()
        return row[0] if row else None


async def set_setting(key: str, value: str):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            (key, value)
        )
        await db.commit()


async def get_all_settings() -> dict:
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT key, value FROM settings")
        rows = await cursor.fetchall()
        return {row[0]: row[1] for row in rows}


# ─── DELIVERY ORDERS ───────────────────────────────────

async def create_delivery_order(courier_id, admin_id, client_name,
                                 client_phone, from_address, to_address):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(
            """INSERT INTO delivery_orders
               (courier_id, admin_id, client_name, client_phone,
                from_address, to_address)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (courier_id, admin_id, client_name, client_phone,
             from_address, to_address)
        )
        await db.commit()
        return cursor.lastrowid


async def get_delivery_order(delivery_id):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(
            "SELECT * FROM delivery_orders WHERE delivery_id = ?",
            (delivery_id,)
        )
        return await cursor.fetchone()


async def get_delivery_orders_by_status(status):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(
            "SELECT * FROM delivery_orders WHERE status = ? ORDER BY created_at DESC",
            (status,)
        )
        return await cursor.fetchall()


async def assign_delivery(delivery_id, courier_id):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "UPDATE delivery_orders SET courier_id = ?, status = 'assigned' WHERE delivery_id = ?",
            (courier_id, delivery_id)
        )
        await db.commit()


async def start_delivery(delivery_id, lat, lon):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            """UPDATE delivery_orders
               SET status = 'active', start_lat = ?, start_lon = ?,
                   started_at = CURRENT_TIMESTAMP
               WHERE delivery_id = ?""",
            (lat, lon, delivery_id)
        )
        await db.commit()


async def finish_delivery(delivery_id, total_km, wait_minutes, total_price, lat, lon):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            """UPDATE delivery_orders
               SET status = 'completed', end_lat = ?, end_lon = ?,
                   total_km = ?, wait_minutes = ?, total_price = ?,
                   finished_at = CURRENT_TIMESTAMP
               WHERE delivery_id = ?""",
            (lat, lon, total_km, wait_minutes, total_price, delivery_id)
        )
        await db.commit()


async def update_delivery_status(delivery_id, status):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "UPDATE delivery_orders SET status = ? WHERE delivery_id = ?",
            (status, delivery_id)
        )
        await db.commit()


async def save_tracking_point(delivery_id, lat, lon, speed, mode):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            """INSERT INTO delivery_tracking
               (delivery_id, latitude, longitude, speed, mode)
               VALUES (?, ?, ?, ?, ?)""",
            (delivery_id, lat, lon, speed, mode)
        )
        await db.commit()


async def get_active_delivery(courier_id):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(
            """SELECT * FROM delivery_orders
               WHERE courier_id = ? AND status IN ('active', 'assigned')
               ORDER BY created_at DESC LIMIT 1""",
            (courier_id,)
        )
        return await cursor.fetchone()


async def get_courier_deliveries(courier_id):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(
            "SELECT * FROM delivery_orders WHERE courier_id = ? ORDER BY created_at DESC",
            (courier_id,)
        )
        return await cursor.fetchall()


# ─── HELPERS ───────────────────────────────────────────

def haversine(lat1, lon1, lat2, lon2) -> float:
    """Икки нуқта орасидаги масофа (км)"""
    R = 6371.0
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    return R * 2 * math.asin(math.sqrt(a))


# ─── ADMINS ─────────────────────────────────────────

async def get_admin_ids() -> list:
    """Барча админ ID ларини олиш"""
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(
            "SELECT user_id FROM users WHERE role IN ('admin', 'owner')"
        )
        rows = await cursor.fetchall()
        return [row[0] for row in rows]


async def add_admin(user_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "UPDATE users SET role = 'admin' WHERE user_id = ?", (user_id,)
        )
        await db.commit()


async def remove_admin(user_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "UPDATE users SET role = 'client' WHERE user_id = ?", (user_id,)
        )
        await db.commit()