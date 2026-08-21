import sqlite3
from typing import List, Optional


def get_or_create_tag(conn: sqlite3.Connection, name: str) -> int:
    row = conn.execute("SELECT id FROM tags WHERE name = ? COLLATE NOCASE", (name,)).fetchone()
    if row:
        return row["id"]
    cur = conn.execute("INSERT INTO tags (name) VALUES (?)", (name,))
    return cur.lastrowid


def set_task_tags(conn: sqlite3.Connection, task_id: int, tag_names: Optional[List[str]]) -> None:
    conn.execute("DELETE FROM task_tags WHERE task_id = ?", (task_id,))
    seen = set()
    for raw in tag_names or []:
        name = raw.strip()
        if not name or name.lower() in seen:
            continue
        seen.add(name.lower())
        tag_id = get_or_create_tag(conn, name)
        conn.execute(
            "INSERT OR IGNORE INTO task_tags (task_id, tag_id) VALUES (?, ?)", (task_id, tag_id)
        )


def get_tags_for_task(conn: sqlite3.Connection, task_id: int) -> List[str]:
    rows = conn.execute(
        """
        SELECT t.name FROM task_tags tt
        JOIN tags t ON t.id = tt.tag_id
        WHERE tt.task_id = ?
        ORDER BY t.name COLLATE NOCASE
        """,
        (task_id,),
    ).fetchall()
    return [r["name"] for r in rows]


def get_tags_for_tasks(conn: sqlite3.Connection, task_ids: List[int]) -> dict:
    if not task_ids:
        return {}
    placeholders = ",".join("?" for _ in task_ids)
    rows = conn.execute(
        f"""
        SELECT tt.task_id, t.name FROM task_tags tt
        JOIN tags t ON t.id = tt.tag_id
        WHERE tt.task_id IN ({placeholders})
        ORDER BY t.name COLLATE NOCASE
        """,
        task_ids,
    ).fetchall()
    result: dict = {}
    for r in rows:
        result.setdefault(r["task_id"], []).append(r["name"])
    return result
