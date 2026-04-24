import sqlite3
from datetime import datetime


class Database:
    def __init__(self, db_name="shop.db"):
        self.conn = sqlite3.connect(db_name, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()
        self._migrate()

    # ───────────────────────── MIGRATION SAFE INIT ─────────────────────────
    def _migrate(self):
        # USERS (fix missing column issues safely)
        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            balance REAL DEFAULT 0
        )
        """)

        # PRODUCTS
        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            description TEXT,
            price REAL,
            emoji TEXT,
            delivery TEXT,
            active INTEGER DEFAULT 1
        )
        """)

        # ORDERS
        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            product_id INTEGER,
            amount REAL,
            created_at TEXT
        )
        """)

        # INVOICES
        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS invoices (
            invoice_id INTEGER PRIMARY KEY,
            user_id INTEGER,
            amount REAL,
            credited INTEGER DEFAULT 0,
            created_at TEXT
        )
        """)

        # ── FIX OLD DATABASE ISSUE (IMPORTANT) ──
        self._fix_users_table()

        self.conn.commit()

    # This fixes your exact error automatically
    def _fix_users_table(self):
        self.cursor.execute("PRAGMA table_info(users)")
        columns = [col["name"] for col in self.cursor.fetchall()]

        # If old DB used "id" instead of "user_id"
        if "id" in columns and "user_id" not in columns:
            self.cursor.execute("ALTER TABLE users RENAME TO users_old")

            self.cursor.execute("""
            CREATE TABLE users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                balance REAL DEFAULT 0
            )
            """)

            self.cursor.execute("""
            INSERT INTO users (user_id, username, balance)
            SELECT id, username, 0 FROM users_old
            """)

    # ───────────────────────── USERS ─────────────────────────
    def ensure_user(self, user_id, username=None):
        self.cursor.execute("""
        INSERT OR IGNORE INTO users (user_id, username, balance)
        VALUES (?, ?, 0)
        """, (user_id, username))
        self.conn.commit()

    def get_balance(self, user_id):
        self.cursor.execute("SELECT balance FROM users WHERE user_id=?", (user_id,))
        row = self.cursor.fetchone()
        return row["balance"] if row else 0

    def credit_balance(self, user_id, invoice_id, amount):
        if self.invoice_credited(invoice_id):
            return

        self.cursor.execute("""
        UPDATE users SET balance = balance + ?
        WHERE user_id = ?
        """, (amount, user_id))

        self.cursor.execute("""
        UPDATE invoices SET credited = 1 WHERE invoice_id = ?
        """, (invoice_id,))

        self.conn.commit()

    def deduct_balance(self, user_id, amount):
        self.cursor.execute("""
        UPDATE users SET balance = balance - ?
        WHERE user_id = ?
        """, (amount, user_id))
        self.conn.commit()

    # ───────────────────────── INVOICES ─────────────────────────
    def save_invoice(self, user_id, invoice_id, amount):
        self.cursor.execute("""
        INSERT OR IGNORE INTO invoices (invoice_id, user_id, amount, credited, created_at)
        VALUES (?, ?, ?, 0, ?)
        """, (invoice_id, user_id, amount, datetime.utcnow().isoformat()))
        self.conn.commit()

    def invoice_credited(self, invoice_id):
        self.cursor.execute("SELECT credited FROM invoices WHERE invoice_id=?", (invoice_id,))
        row = self.cursor.fetchone()
        return bool(row["credited"]) if row else False

    # ───────────────────────── PRODUCTS ─────────────────────────
    def add_product(self, name, description, price, emoji, delivery):
        self.cursor.execute("""
        INSERT INTO products (name, description, price, emoji, delivery)
        VALUES (?, ?, ?, ?, ?)
        """, (name, description, price, emoji, delivery))
        self.conn.commit()
        return self.cursor.lastrowid

    def get_products(self, active_only=True):
        if active_only:
            self.cursor.execute("SELECT * FROM products WHERE active=1")
        else:
            self.cursor.execute("SELECT * FROM products")
        return [dict(row) for row in self.cursor.fetchall()]

    def get_product(self, product_id):
        self.cursor.execute("SELECT * FROM products WHERE id=?", (product_id,))
        row = self.cursor.fetchone()
        return dict(row) if row else None

    # ───────────────────────── ORDERS ─────────────────────────
    def create_order(self, user_id, product_id, amount):
        self.cursor.execute("""
        INSERT INTO orders (user_id, product_id, amount, created_at)
        VALUES (?, ?, ?, ?)
        """, (user_id, product_id, amount, datetime.utcnow().isoformat()))
        self.conn.commit()
        return self.cursor.lastrowid

    def get_orders(self, user_id):
        self.cursor.execute("""
        SELECT * FROM orders WHERE user_id=?
        ORDER BY id DESC
        """, (user_id,))
        return [dict(row) for row in self.cursor.fetchall()]