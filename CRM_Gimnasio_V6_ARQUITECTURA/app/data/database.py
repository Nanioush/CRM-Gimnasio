import sqlite3
from pathlib import Path
from datetime import date
from app.config.settings import DEFAULT_ACTIVITIES

DB_PATH = Path(__file__).resolve().parents[2] / "gimnasio.db"

class Database:
    def __init__(self, path=DB_PATH):
        self.path = str(path)

    def connect(self):
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def initialize(self):
        with self.connect() as conn:
            cur = conn.cursor()

            cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'admin'
            )
            """)

            cur.execute("""
            CREATE TABLE IF NOT EXISTS students (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                surname TEXT NOT NULL,
                phone TEXT,
                email TEXT,
                birth_date TEXT,
                plan TEXT NOT NULL DEFAULT 'Adulto',
                activity TEXT,
                join_date TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1
            )
            """)

            cur.execute("""
            CREATE TABLE IF NOT EXISTS teachers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                surname TEXT NOT NULL,
                phone TEXT,
                email TEXT,
                specialty TEXT
            )
            """)

            cur.execute("""
            CREATE TABLE IF NOT EXISTS activities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                teacher_id INTEGER,
                schedule TEXT,
                capacity INTEGER DEFAULT 20,
                FOREIGN KEY(teacher_id) REFERENCES teachers(id)
            )
            """)

            cur.execute("""
            CREATE TABLE IF NOT EXISTS attendance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                activity TEXT NOT NULL,
                date TEXT NOT NULL,
                present INTEGER NOT NULL DEFAULT 1,
                FOREIGN KEY(student_id) REFERENCES students(id)
            )
            """)

            cur.execute("""
            CREATE TABLE IF NOT EXISTS payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                amount REAL NOT NULL,
                concept TEXT,
                date TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'Pendiente',
                billing_month TEXT,
                FOREIGN KEY(student_id) REFERENCES students(id)
            )
            """)

            # Migración para bases creadas por versiones anteriores.
            payment_columns = {
                row["name"] for row in cur.execute("PRAGMA table_info(payments)").fetchall()
            }
            if "billing_month" not in payment_columns:
                cur.execute("ALTER TABLE payments ADD COLUMN billing_month TEXT")

            cur.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS idx_payments_student_month
                ON payments(student_id, billing_month)
                WHERE billing_month IS NOT NULL
            """)

            cur.execute("""
            CREATE TABLE IF NOT EXISTS invoices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                invoice_number TEXT UNIQUE NOT NULL,
                student_id INTEGER NOT NULL,
                amount REAL NOT NULL,
                concept TEXT NOT NULL,
                issue_date TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'Emitida',
                FOREIGN KEY(student_id) REFERENCES students(id)
            )
            """)

            # Garantiza una cuenta administrativa funcional.
            # INSERT OR IGNORE crea el usuario si no existe y el UPDATE
            # corrige credenciales de una base creada por una versión anterior.
            cur.execute(
                "INSERT OR IGNORE INTO users(username, password, role) VALUES(?,?,?)",
                ("admin", "admin123", "admin")
            )
            cur.execute(
                "UPDATE users SET password=?, role=? WHERE username=?",
                ("admin123", "admin", "admin")
            )

            for name in DEFAULT_ACTIVITIES:
                cur.execute("INSERT OR IGNORE INTO activities(name) VALUES(?)", (name,))

            conn.commit()

    def authenticate(self, username, password):
        username = (username or "").strip()
        password = (password or "").strip()
        with self.connect() as conn:
            cur = conn.execute(
                "SELECT * FROM users WHERE lower(username)=lower(?) AND password=?",
                (username, password)
            )
            return cur.fetchone()

    def fetchall(self, query, params=()):
        with self.connect() as conn:
            return conn.execute(query, params).fetchall()

    def fetchone(self, query, params=()):
        with self.connect() as conn:
            return conn.execute(query, params).fetchone()

    def execute(self, query, params=()):
        with self.connect() as conn:
            cur = conn.execute(query, params)
            conn.commit()
            return cur.lastrowid


    def execute_many(self, query, params_sequence):
        with self.connect() as conn:
            conn.executemany(query, params_sequence)
            conn.commit()
