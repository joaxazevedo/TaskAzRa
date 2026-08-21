import sqlite3

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

from common.db import get_connection
from common.auth import hash_pin, verify_pin, generate_session_token
from backend.deps import get_current_user, require_self
from backend.schemas import UserCreate, UserLogin

router = APIRouter(prefix="/users", tags=["users"])


class UserLinkCreate(BaseModel):
    linked_user_id: int


class UserThemeUpdate(BaseModel):
    theme: str  # 'light' | 'dark'


def _serialize_user(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "name": row["name"],
        "username": row["username"],
        "email": row["email"],
        "telegram_chat_id": row["telegram_chat_id"],
        "theme": row["theme"],
    }


@router.post("")
def create_user(payload: UserCreate):
    conn = get_connection()
    try:
        cur = conn.execute(
            """
            INSERT INTO users (name, username, pin_hash, email, telegram_chat_id)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                payload.name,
                payload.username,
                hash_pin(payload.pin),
                payload.email,
                payload.telegram_chat_id,
            ),
        )
        conn.commit()
        user_id = cur.lastrowid
    except sqlite3.IntegrityError as e:
        raise HTTPException(status_code=409, detail=f"Usuário ou chat_id já cadastrado: {e}")
    finally:
        conn.close()
    return {"id": user_id, "name": payload.name, "username": payload.username}


@router.get("")
def list_users(current_user: sqlite3.Row = Depends(get_current_user)):
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT id, name, username, email, telegram_chat_id, theme, created_at FROM users"
        ).fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]


@router.post("/login")
def login(payload: UserLogin):
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT id, name, username, pin_hash, email, telegram_chat_id, theme FROM users WHERE username = ?",
            (payload.username,),
        ).fetchone()
        if row is None or not verify_pin(payload.pin, row["pin_hash"]):
            raise HTTPException(status_code=401, detail="Usuário ou PIN inválido")

        token = generate_session_token()
        conn.execute(
            "INSERT INTO sessions (token, user_id) VALUES (?, ?)", (token, row["id"])
        )
        conn.commit()
    finally:
        conn.close()
    return {"token": token, "user": _serialize_user(row)}


@router.post("/logout")
def logout(authorization: str = Header(default=None)):
    if authorization and authorization.startswith("Bearer "):
        token = authorization.removeprefix("Bearer ").strip()
        conn = get_connection()
        try:
            conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
            conn.commit()
        finally:
            conn.close()
    return {"status": "ok"}


@router.get("/me")
def get_me(current_user: sqlite3.Row = Depends(get_current_user)):
    return _serialize_user(current_user)


@router.patch("/{user_id}/theme")
def update_theme(
    user_id: int,
    payload: UserThemeUpdate,
    current_user: sqlite3.Row = Depends(get_current_user),
):
    require_self(user_id, current_user)
    if payload.theme not in ("light", "dark"):
        raise HTTPException(status_code=400, detail="theme deve ser 'light' ou 'dark'")

    conn = get_connection()
    try:
        cur = conn.execute("UPDATE users SET theme = ? WHERE id = ?", (payload.theme, user_id))
        conn.commit()
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Usuário não encontrado")
    finally:
        conn.close()
    return {"id": user_id, "theme": payload.theme}


@router.post("/{user_id}/links")
def link_user(
    user_id: int,
    payload: UserLinkCreate,
    current_user: sqlite3.Row = Depends(get_current_user),
):
    require_self(user_id, current_user)
    if user_id == payload.linked_user_id:
        raise HTTPException(status_code=400, detail="Não é possível vincular o usuário a si mesmo")

    conn = get_connection()
    try:
        users = conn.execute(
            "SELECT id FROM users WHERE id IN (?, ?)", (user_id, payload.linked_user_id)
        ).fetchall()
        if len(users) != 2:
            raise HTTPException(status_code=404, detail="Usuário não encontrado")

        conn.execute(
            "INSERT OR IGNORE INTO user_links (user_id, linked_user_id) VALUES (?, ?)",
            (user_id, payload.linked_user_id),
        )
        conn.execute(
            "INSERT OR IGNORE INTO user_links (user_id, linked_user_id) VALUES (?, ?)",
            (payload.linked_user_id, user_id),
        )
        conn.commit()
    finally:
        conn.close()
    return {"user_id": user_id, "linked_user_id": payload.linked_user_id}


@router.get("/{user_id}/links")
def list_links(user_id: int, current_user: sqlite3.Row = Depends(get_current_user)):
    require_self(user_id, current_user)
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT u.id, u.name, u.username
            FROM user_links ul
            JOIN users u ON u.id = ul.linked_user_id
            WHERE ul.user_id = ?
            """,
            (user_id,),
        ).fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]


@router.delete("/{user_id}/links/{linked_user_id}")
def unlink_user(
    user_id: int,
    linked_user_id: int,
    current_user: sqlite3.Row = Depends(get_current_user),
):
    require_self(user_id, current_user)
    conn = get_connection()
    try:
        conn.execute(
            "DELETE FROM user_links WHERE (user_id = ? AND linked_user_id = ?) OR (user_id = ? AND linked_user_id = ?)",
            (user_id, linked_user_id, linked_user_id, user_id),
        )
        conn.commit()
    finally:
        conn.close()
    return {"status": "ok"}
