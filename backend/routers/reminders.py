import sqlite3

from pydantic import BaseModel
from fastapi import APIRouter, Depends

from common.db import get_connection
from backend.deps import get_current_user

router = APIRouter(prefix="/reminders", tags=["reminders"])


class ReminderCreate(BaseModel):
    hour: str  # formato "HH:MM"


@router.post("")
def create_reminder(
    payload: ReminderCreate, current_user: sqlite3.Row = Depends(get_current_user)
):
    conn = get_connection()
    try:
        cur = conn.execute(
            "INSERT INTO reminder_configs (user_id, hour) VALUES (?, ?)",
            (current_user["id"], payload.hour),
        )
        conn.commit()
        reminder_id = cur.lastrowid
    finally:
        conn.close()
    return {"id": reminder_id, "user_id": current_user["id"], "hour": payload.hour}


@router.get("")
def list_reminders(current_user: sqlite3.Row = Depends(get_current_user)):
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM reminder_configs WHERE user_id = ?", (current_user["id"],)
        ).fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]
