import sqlite3
from fastapi import APIRouter, Depends

from common.db import get_connection
from backend.deps import get_current_user

router = APIRouter(prefix="/tags", tags=["tags"])


@router.get("")
def list_tags(current_user: sqlite3.Row = Depends(get_current_user)):
    conn = get_connection()
    try:
        rows = conn.execute("SELECT id, name FROM tags ORDER BY name COLLATE NOCASE").fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]
