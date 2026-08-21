import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "taskazra.db"

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    username TEXT NOT NULL UNIQUE,
    pin_hash TEXT NOT NULL,
    email TEXT,
    telegram_chat_id TEXT UNIQUE,
    theme TEXT NOT NULL DEFAULT 'dark' CHECK (theme IN ('light', 'dark')),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT,
    type TEXT NOT NULL CHECK (type IN ('unica', 'periodica', 'manual')),
    recurrence_kind TEXT CHECK (recurrence_kind IN ('intervalo_dias', 'dia_fixo_mes', 'dia_semana')),
    recurrence_value TEXT,
    recurrence_end_date TEXT,
    recurrence_max_occurrences INTEGER,
    priority TEXT NOT NULL DEFAULT 'media' CHECK (priority IN ('baixa', 'media', 'alta')),
    created_by INTEGER NOT NULL REFERENCES users(id),
    assigned_to INTEGER REFERENCES users(id),
    active INTEGER NOT NULL DEFAULT 1,
    needs_confirmation INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS task_instances (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER NOT NULL REFERENCES tasks(id),
    due_date TEXT,
    status TEXT NOT NULL DEFAULT 'pendente' CHECK (status IN ('pendente', 'aguardando_confirmacao', 'feito')),
    completed_by INTEGER REFERENCES users(id),
    completed_at TEXT,
    confirmation_requested_by INTEGER REFERENCES users(id),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS reminder_configs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id),
    hour TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1,
    last_sent_date TEXT
);

CREATE TABLE IF NOT EXISTS user_links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id),
    linked_user_id INTEGER NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, linked_user_id),
    CHECK (user_id != linked_user_id)
);

CREATE TABLE IF NOT EXISTS sessions (
    token TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE COLLATE NOCASE,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS task_tags (
    task_id INTEGER NOT NULL REFERENCES tasks(id),
    tag_id INTEGER NOT NULL REFERENCES tags(id),
    PRIMARY KEY (task_id, tag_id)
);

CREATE TABLE IF NOT EXISTS task_comments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER NOT NULL REFERENCES tasks(id),
    user_id INTEGER NOT NULL REFERENCES users(id),
    text TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""


def get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _migrate_task_instances_status(conn: sqlite3.Connection) -> None:
    """SQLite não permite ALTER de CHECK constraint — reconstrói a tabela
    quando o CHECK antigo (só 'pendente'/'feito') ainda estiver presente."""
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'task_instances'"
    ).fetchone()
    if row is None or "aguardando_confirmacao" in row["sql"]:
        return

    conn.executescript(
        """
        ALTER TABLE task_instances RENAME TO task_instances_old;

        CREATE TABLE task_instances (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER NOT NULL REFERENCES tasks(id),
            due_date TEXT,
            status TEXT NOT NULL DEFAULT 'pendente' CHECK (status IN ('pendente', 'aguardando_confirmacao', 'feito')),
            completed_by INTEGER REFERENCES users(id),
            completed_at TEXT,
            confirmation_requested_by INTEGER REFERENCES users(id),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        INSERT INTO task_instances
            (id, task_id, due_date, status, completed_by, completed_at, created_at)
        SELECT id, task_id, due_date, status, completed_by, completed_at, created_at
        FROM task_instances_old;

        DROP TABLE task_instances_old;
        """
    )


def _migrate(conn: sqlite3.Connection) -> None:
    user_columns = {row["name"] for row in conn.execute("PRAGMA table_info(users)")}
    if "theme" not in user_columns:
        conn.execute("ALTER TABLE users ADD COLUMN theme TEXT NOT NULL DEFAULT 'light'")

    task_columns = {row["name"] for row in conn.execute("PRAGMA table_info(tasks)")}
    if "recurrence_end_date" not in task_columns:
        conn.execute("ALTER TABLE tasks ADD COLUMN recurrence_end_date TEXT")
    if "recurrence_max_occurrences" not in task_columns:
        conn.execute("ALTER TABLE tasks ADD COLUMN recurrence_max_occurrences INTEGER")
    if "needs_confirmation" not in task_columns:
        conn.execute("ALTER TABLE tasks ADD COLUMN needs_confirmation INTEGER NOT NULL DEFAULT 0")

    _migrate_task_instances_status(conn)


def init_db() -> None:
    conn = get_connection()
    try:
        conn.executescript(SCHEMA_SQL)
        _migrate(conn)
        conn.commit()
    finally:
        conn.close()


if __name__ == "__main__":
    init_db()
    print(f"Banco inicializado em {DB_PATH}")
