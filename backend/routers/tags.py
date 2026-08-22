import sqlite3
from fastapi import APIRouter, Depends

from common.db import get_connection
from backend.deps import get_current_user

router = APIRouter(prefix="/tags", tags=["tags"])


@router.get("")
def list_tags(current_user: sqlite3.Row = Depends(get_current_user)):
    conn = get_connection()
    try:
        # Só tags de tarefas com pelo menos uma instância pendente — uma tag
        # cujas tarefas já foram todas concluídas não deve continuar
        # sugerida na criação/edição.
        rows = conn.execute(
            """
            SELECT DISTINCT t.id, t.name
            FROM tags t
            JOIN task_tags tt ON tt.tag_id = t.id
            JOIN task_instances ti ON ti.task_id = tt.task_id
            WHERE ti.status = 'pendente'
            ORDER BY t.name COLLATE NOCASE
            """
        ).fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]
