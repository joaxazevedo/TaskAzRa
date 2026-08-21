import sqlite3
from typing import Optional
from fastapi import APIRouter, Depends

from common.db import get_connection
from backend.deps import get_current_user

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/completed")
def relatorio_concluidas(
    start: Optional[str] = None,
    end: Optional[str] = None,
    current_user: sqlite3.Row = Depends(get_current_user),
):
    query = """
        SELECT
            ti.id, ti.task_id, t.title, t.priority, t.assigned_to, ti.completed_by,
            ti.created_at, ti.completed_at, assignee.name AS assigned_to_name,
            completer.name AS completed_by_name,
            (julianday(ti.completed_at) - julianday(ti.created_at)) AS dias_para_completar
        FROM task_instances ti
        JOIN tasks t ON t.id = ti.task_id
        LEFT JOIN users assignee ON assignee.id = t.assigned_to
        LEFT JOIN users completer ON completer.id = ti.completed_by
        WHERE ti.status = 'feito'
    """
    params = []
    if start:
        query += " AND ti.completed_at >= ?"
        params.append(start)
    if end:
        query += " AND ti.completed_at <= ?"
        params.append(end)
    query += " ORDER BY ti.completed_at DESC"

    conn = get_connection()
    try:
        rows = conn.execute(query, params).fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]


@router.get("/pending")
def relatorio_pendentes(current_user: sqlite3.Row = Depends(get_current_user)):
    query = """
        SELECT
            ti.id, t.title, t.priority, t.assigned_to, ti.due_date, ti.created_at,
            (julianday('now') - julianday(ti.created_at)) AS dias_pendente
        FROM task_instances ti
        JOIN tasks t ON t.id = ti.task_id
        WHERE ti.status = 'pendente'
        ORDER BY dias_pendente DESC
    """
    conn = get_connection()
    try:
        rows = conn.execute(query).fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]
