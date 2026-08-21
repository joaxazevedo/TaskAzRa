import sqlite3

from fastapi import Header, HTTPException

from common.db import get_connection


def get_current_user(authorization: str = Header(default=None)) -> sqlite3.Row:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Não autenticado")

    token = authorization.removeprefix("Bearer ").strip()

    conn = get_connection()
    try:
        row = conn.execute(
            """
            SELECT u.id, u.name, u.username, u.email, u.telegram_chat_id, u.theme
            FROM sessions s
            JOIN users u ON u.id = s.user_id
            WHERE s.token = ?
            """,
            (token,),
        ).fetchone()
    finally:
        conn.close()

    if row is None:
        raise HTTPException(status_code=401, detail="Sessão inválida ou expirada")
    return row


def require_self(user_id: int, current_user: sqlite3.Row) -> None:
    if user_id != current_user["id"]:
        raise HTTPException(status_code=403, detail="Você só pode gerenciar a sua própria conta")
