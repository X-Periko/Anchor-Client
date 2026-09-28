import os
import sqlite3
from pathlib import Path

# En Android/iOS, Flet expone FLET_APP_STORAGE_PATH apuntando a un directorio
# privado escribible de la app. En escritorio no existe, así que caemos al
# directorio del propio módulo.
_APP_STORAGE = os.environ.get("FLET_APP_STORAGE_PATH")
DB_DIR = Path(_APP_STORAGE) if _APP_STORAGE else Path(__file__).parent
DB_PATH = DB_DIR / "tasks.db"


def connect():
    # Asegurar que el directorio existe (Android lo crea vacío al instalar)
    DB_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # permite acceder a las columnas por nombre: fila["nombre"]
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def create_table():
    with connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nick TEXT NOT NULL UNIQUE COLLATE NOCASE,
                email TEXT NOT NULL UNIQUE COLLATE NOCASE,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                name TEXT NOT NULL,
                description TEXT,
                deadline TEXT,
                priority INTEGER NOT NULL DEFAULT 1,
                done INTEGER NOT NULL DEFAULT 0
            )
        """)

#--------------------------USERS DB--------------------------

def create_user(nick, email, password_hash):
    with connect() as conn:
        cursor = conn.execute(
            "INSERT INTO users (nick, email, password_hash) VALUES (?, ?, ?)",
            (nick, email, password_hash),
        )
        return cursor.lastrowid   # lanza sqlite3.IntegrityError si nick/email ya existen


def get_user_by_email(email):
    with connect() as conn:
        row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        return dict(row) if row else None

def get_user_by_nick(nick):
    with connect() as conn:
        row = conn.execute("SELECT * FROM users WHERE nick = ?", (nick,)).fetchone()
        return dict(row) if row else None

def get_user_by_id(user_id):
    with connect() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return dict(row) if row else None
    
def list_users():
    with connect() as conn:
        rows = conn.execute("SELECT * FROM tasks ").fetchall()
        return [dict(r) for r in rows]

#--------------------------TASKS DB--------------------------

def add_task(name, user_id, description=None, deadline=None, priority=1):
    with connect() as conn:
        cursor = conn.execute(
            "INSERT INTO tasks (user_id, name, description, deadline, priority) VALUES (?, ?, ?, ?, ?)",
            (user_id, name, description, deadline, priority)
        )
        return cursor.lastrowid


def list_tasks(user_id):
    with connect() as conn:
        rows = conn.execute("SELECT * FROM tasks WHERE user_id = ?", (user_id,)).fetchall()
        return [dict(r) for r in rows]


def get_task(user_id, task_id):
    with connect() as conn:
        row = conn.execute("SELECT * FROM tasks WHERE id = ? AND user_id = ?", (task_id,user_id)).fetchone()
        return dict(row) if row else None


def set_done(user_id, task_id, done: bool):
    with connect() as conn:
        conn.execute("UPDATE tasks SET done = ? WHERE id = ? AND user_id = ?", (int(done), task_id, user_id))


def edit_task(user_id, task_id, description, deadline, priority):
    with connect() as conn:
        conn.execute(
            "UPDATE tasks SET description = ?, deadline = ?, priority = ? WHERE id = ? AND user_id = ?",
            (description, deadline, priority, task_id, user_id)
        )

def delete_task(user_id, task_id, all:bool = False):
    with connect() as conn:
        if all: 
            conn.execute("DELETE FROM tasks WHERE user_id = ?", (user_id,))
            return
        conn.execute("DELETE FROM tasks WHERE id = ? AND user_id = ?", (task_id,user_id))

def find_tasks_by_name(user_id, name):
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM tasks WHERE name LIKE ? AND user_id = ? COLLATE NOCASE",
            (name,user_id)
        ).fetchall()
        return [dict(r) for r in rows]

if __name__ == "__main__":
    create_table()
    print(f"Base de datos creada en: {DB_PATH}")
