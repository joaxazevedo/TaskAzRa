import sqlite3
from datetime import date, datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException

from common.db import get_connection
from backend.deps import get_current_user
from backend.schemas import TaskCreate, TaskUpdate, CommentCreate, ConfirmationDecision
from backend.tags import set_task_tags, get_tags_for_task, get_tags_for_tasks

router = APIRouter(tags=["tasks"])

VALID_TYPES = {"unica", "periodica", "manual"}
VALID_RECURRENCE_KINDS = {"intervalo_dias", "dia_fixo_mes", "dia_semana"}
WEEKDAY_CODES = {"SEG", "TER", "QUA", "QUI", "SEX", "SAB", "DOM"}
MAX_RECURRENCE_END_YEARS = 10


def validate_recurrence_end_date(end_date_str: str) -> None:
    try:
        end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="recurrence_end_date deve estar no formato YYYY-MM-DD")

    today = date.today()
    if end_date < today:
        raise HTTPException(status_code=400, detail="recurrence_end_date não pode estar no passado")

    try:
        max_date = today.replace(year=today.year + MAX_RECURRENCE_END_YEARS)
    except ValueError:
        max_date = today.replace(year=today.year + MAX_RECURRENCE_END_YEARS, day=28)
    if end_date > max_date:
        raise HTTPException(
            status_code=400,
            detail=f"recurrence_end_date não pode passar de {MAX_RECURRENCE_END_YEARS} anos a partir de hoje",
        )


def validate_due_date(due_date_str: str) -> None:
    try:
        due_date = datetime.strptime(due_date_str, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="due_date deve estar no formato YYYY-MM-DD")
    if due_date < date.today():
        raise HTTPException(status_code=400, detail="due_date não pode estar no passado")


def validate_recurrence_value(kind: str, value: str) -> None:
    if kind == "intervalo_dias":
        if not value.isdigit() or int(value) < 1:
            raise HTTPException(
                status_code=400, detail="recurrence_value deve ser um número de dias >= 1"
            )
    elif kind == "dia_fixo_mes":
        if not value.isdigit() or not (1 <= int(value) <= 31):
            raise HTTPException(
                status_code=400, detail="recurrence_value deve ser um dia do mês entre 1 e 31"
            )
    elif kind == "dia_semana":
        codes = {c.strip().upper() for c in value.split(",") if c.strip()}
        if not codes or not codes.issubset(WEEKDAY_CODES):
            raise HTTPException(
                status_code=400,
                detail=f"recurrence_value deve conter dias válidos: {', '.join(sorted(WEEKDAY_CODES))}",
            )


@router.post("/tasks")
def create_task(payload: TaskCreate, current_user: sqlite3.Row = Depends(get_current_user)):
    if payload.type not in VALID_TYPES:
        raise HTTPException(status_code=400, detail=f"type inválido: {payload.type}")
    if payload.due_date and payload.type != "unica":
        raise HTTPException(status_code=400, detail="due_date só é válido para tarefas do tipo 'unica'")
    if payload.due_date:
        validate_due_date(payload.due_date)
    if payload.type == "periodica":
        if payload.recurrence_kind not in VALID_RECURRENCE_KINDS or not payload.recurrence_value:
            raise HTTPException(
                status_code=400,
                detail="Tarefas periódicas exigem recurrence_kind e recurrence_value",
            )
        if payload.recurrence_end_date and payload.recurrence_max_occurrences:
            raise HTTPException(
                status_code=400,
                detail="Escolha apenas um limite de recorrência: data de fim OU quantidade de repetições",
            )
        validate_recurrence_value(payload.recurrence_kind, payload.recurrence_value)
        if payload.recurrence_end_date:
            validate_recurrence_end_date(payload.recurrence_end_date)
        if payload.recurrence_max_occurrences is not None and payload.recurrence_max_occurrences < 1:
            raise HTTPException(
                status_code=400, detail="recurrence_max_occurrences deve ser >= 1"
            )

    created_by = current_user["id"]

    conn = get_connection()
    try:
        if payload.assigned_to is not None and payload.assigned_to != created_by:
            linked = conn.execute(
                "SELECT 1 FROM user_links WHERE user_id = ? AND linked_user_id = ?",
                (created_by, payload.assigned_to),
            ).fetchone()
            if linked is None:
                raise HTTPException(
                    status_code=403,
                    detail="Só é possível atribuir tarefas a você mesmo ou a um usuário vinculado",
                )

        cur = conn.execute(
            """
            INSERT INTO tasks
                (title, description, type, recurrence_kind, recurrence_value,
                 recurrence_end_date, recurrence_max_occurrences, priority, created_by, assigned_to,
                 needs_confirmation)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload.title,
                payload.description,
                payload.type,
                payload.recurrence_kind,
                payload.recurrence_value,
                payload.recurrence_end_date,
                payload.recurrence_max_occurrences,
                payload.priority,
                created_by,
                payload.assigned_to,
                1 if payload.needs_confirmation else 0,
            ),
        )
        task_id = cur.lastrowid

        if payload.type in ("unica", "periodica"):
            # Tarefas periódicas também ganham a 1ª ocorrência na hora da criação —
            # sem isso, ficariam invisíveis até o scheduler rodar e calcular o próximo
            # vencimento, o que pode nunca acontecer se o scheduler não estiver ativo.
            conn.execute(
                "INSERT INTO task_instances (task_id, due_date, status) VALUES (?, ?, 'pendente')",
                (task_id, payload.due_date),
            )
        if payload.tags is not None:
            set_task_tags(conn, task_id, payload.tags)
        conn.commit()
    finally:
        conn.close()
    return {"id": task_id, "title": payload.title, "type": payload.type}


@router.get("/tasks")
def list_tasks(
    active: Optional[bool] = True, current_user: sqlite3.Row = Depends(get_current_user)
):
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM tasks WHERE active = ? ORDER BY created_at DESC",
            (1 if active else 0,),
        ).fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]


@router.get("/tasks/{task_id}")
def get_task(task_id: int, current_user: sqlite3.Row = Depends(get_current_user)):
    conn = get_connection()
    try:
        task = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        if task is None:
            raise HTTPException(status_code=404, detail="Tarefa não encontrada")
        instance = conn.execute(
            """
            SELECT due_date FROM task_instances
            WHERE task_id = ? AND status = 'pendente'
            ORDER BY id DESC LIMIT 1
            """,
            (task_id,),
        ).fetchone()
        tags = get_tags_for_task(conn, task_id)
    finally:
        conn.close()
    result = dict(task)
    result["due_date"] = instance["due_date"] if instance else None
    result["tags"] = tags
    return result


@router.patch("/tasks/{task_id}")
def update_task(
    task_id: int, payload: TaskUpdate, current_user: sqlite3.Row = Depends(get_current_user)
):
    if payload.priority not in {"baixa", "media", "alta"}:
        raise HTTPException(status_code=400, detail="priority inválida")
    if payload.due_date:
        validate_due_date(payload.due_date)

    conn = get_connection()
    try:
        task = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        if task is None:
            raise HTTPException(status_code=404, detail="Tarefa não encontrada")
        if payload.due_date and task["type"] != "unica":
            raise HTTPException(
                status_code=400, detail="due_date só é válido para tarefas do tipo 'unica'"
            )

        if payload.assigned_to is not None and payload.assigned_to != current_user["id"]:
            linked = conn.execute(
                "SELECT 1 FROM user_links WHERE user_id = ? AND linked_user_id = ?",
                (current_user["id"], payload.assigned_to),
            ).fetchone()
            if linked is None:
                raise HTTPException(
                    status_code=403,
                    detail="Só é possível atribuir tarefas a você mesmo ou a um usuário vinculado",
                )

        conn.execute(
            """
            UPDATE tasks
            SET title = ?, description = ?, priority = ?, assigned_to = ?, needs_confirmation = ?
            WHERE id = ?
            """,
            (
                payload.title,
                payload.description,
                payload.priority,
                payload.assigned_to,
                1 if payload.needs_confirmation else 0,
                task_id,
            ),
        )
        if task["type"] == "unica":
            conn.execute(
                "UPDATE task_instances SET due_date = ? WHERE task_id = ? AND status = 'pendente'",
                (payload.due_date, task_id),
            )
        if payload.tags is not None:
            set_task_tags(conn, task_id, payload.tags)
        conn.commit()
    finally:
        conn.close()
    return {"id": task_id, "title": payload.title}


@router.post("/tasks/{task_id}/ativar")
def ativar_tarefa_manual(task_id: int, current_user: sqlite3.Row = Depends(get_current_user)):
    conn = get_connection()
    try:
        task = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        if task is None:
            raise HTTPException(status_code=404, detail="Tarefa não encontrada")
        if task["type"] != "manual":
            raise HTTPException(status_code=400, detail="Apenas tarefas do tipo 'manual' podem ser ativadas")

        cur = conn.execute(
            "INSERT INTO task_instances (task_id, status) VALUES (?, 'pendente')",
            (task_id,),
        )
        conn.commit()
        instance_id = cur.lastrowid
    finally:
        conn.close()
    return {"instance_id": instance_id, "task_id": task_id, "status": "pendente"}


@router.get("/instances")
def list_instances(
    status: Optional[str] = None,
    assigned_to: Optional[int] = None,
    assigned_to_exact: Optional[int] = None,
    current_user: sqlite3.Row = Depends(get_current_user),
):
    if assigned_to_exact is not None and assigned_to_exact != current_user["id"]:
        linked = get_connection()
        try:
            is_linked = linked.execute(
                "SELECT 1 FROM user_links WHERE user_id = ? AND linked_user_id = ?",
                (current_user["id"], assigned_to_exact),
            ).fetchone()
        finally:
            linked.close()
        if is_linked is None:
            raise HTTPException(
                status_code=403,
                detail="Só é possível filtrar por você mesmo ou por um usuário vinculado",
            )

    query = """
        SELECT
            ti.id, ti.task_id, ti.due_date, ti.status, ti.completed_by, ti.completed_at, ti.created_at,
            ti.confirmation_requested_by, requester.name AS confirmation_requested_by_name,
            t.title, t.description, t.type, t.priority, t.assigned_to, t.created_by,
            t.needs_confirmation, t.created_at AS task_created_at,
            creator.name AS created_by_name, assignee.name AS assigned_to_name
        FROM task_instances ti
        JOIN tasks t ON t.id = ti.task_id
        JOIN users creator ON creator.id = t.created_by
        LEFT JOIN users assignee ON assignee.id = t.assigned_to
        LEFT JOIN users requester ON requester.id = ti.confirmation_requested_by
        WHERE 1 = 1
    """
    params = []
    if status:
        query += " AND ti.status = ?"
        params.append(status)
    if assigned_to is not None:
        query += " AND (t.assigned_to = ? OR t.assigned_to IS NULL)"
        params.append(assigned_to)
    if assigned_to_exact is not None:
        query += " AND t.assigned_to = ?"
        params.append(assigned_to_exact)
    query += """
        ORDER BY
            CASE t.priority
                WHEN 'alta' THEN 0
                WHEN 'media' THEN 1
                WHEN 'baixa' THEN 2
                ELSE 3
            END,
            ti.created_at ASC
    """

    conn = get_connection()
    try:
        rows = [dict(r) for r in conn.execute(query, params).fetchall()]
        task_ids = [r["task_id"] for r in rows]
        tags_by_task = get_tags_for_tasks(conn, task_ids)
        comment_counts = {}
        if task_ids:
            placeholders = ",".join("?" for _ in task_ids)
            for r in conn.execute(
                f"""
                SELECT task_id, COUNT(*) AS n FROM task_comments
                WHERE task_id IN ({placeholders})
                GROUP BY task_id
                """,
                task_ids,
            ).fetchall():
                comment_counts[r["task_id"]] = r["n"]
    finally:
        conn.close()
    for r in rows:
        r["tags"] = tags_by_task.get(r["task_id"], [])
        r["comment_count"] = comment_counts.get(r["task_id"], 0)
    return rows


@router.post("/instances/{instance_id}/feito")
def concluir_instancia(instance_id: int, current_user: sqlite3.Row = Depends(get_current_user)):
    conn = get_connection()
    try:
        instance = conn.execute(
            "SELECT * FROM task_instances WHERE id = ?", (instance_id,)
        ).fetchone()
        if instance is None:
            raise HTTPException(status_code=404, detail="Instância não encontrada")
        if instance["status"] != "pendente":
            raise HTTPException(status_code=400, detail="Instância não está pendente")

        task = conn.execute(
            "SELECT needs_confirmation FROM tasks WHERE id = ?", (instance["task_id"],)
        ).fetchone()

        if task["needs_confirmation"]:
            # Não conclui direto — fica esperando o criador da tarefa confirmar
            # (ver POST /instances/{id}/confirmar).
            conn.execute(
                """
                UPDATE task_instances
                SET status = 'aguardando_confirmacao', confirmation_requested_by = ?
                WHERE id = ?
                """,
                (current_user["id"], instance_id),
            )
            conn.commit()
            return {"id": instance_id, "status": "aguardando_confirmacao"}

        conn.execute(
            """
            UPDATE task_instances
            SET status = 'feito', completed_by = ?, completed_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (current_user["id"], instance_id),
        )
        conn.commit()
    finally:
        conn.close()
    return {"id": instance_id, "status": "feito"}


@router.post("/instances/{instance_id}/confirmar")
def confirmar_instancia(
    instance_id: int,
    payload: ConfirmationDecision,
    current_user: sqlite3.Row = Depends(get_current_user),
):
    comment = payload.comment.strip()
    if not comment:
        raise HTTPException(status_code=400, detail="Comentário é obrigatório")
    if payload.action not in {"concluir", "devolver"}:
        raise HTTPException(status_code=400, detail="action deve ser 'concluir' ou 'devolver'")

    conn = get_connection()
    try:
        instance = conn.execute(
            "SELECT * FROM task_instances WHERE id = ?", (instance_id,)
        ).fetchone()
        if instance is None:
            raise HTTPException(status_code=404, detail="Instância não encontrada")
        if instance["status"] != "aguardando_confirmacao":
            raise HTTPException(
                status_code=400, detail="Instância não está aguardando confirmação"
            )

        task = conn.execute(
            "SELECT created_by FROM tasks WHERE id = ?", (instance["task_id"],)
        ).fetchone()
        if task["created_by"] != current_user["id"]:
            raise HTTPException(
                status_code=403,
                detail="Só quem criou a tarefa pode confirmar sua conclusão",
            )

        if payload.action == "concluir":
            conn.execute(
                """
                UPDATE task_instances
                SET status = 'feito', completed_by = ?, completed_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (instance["confirmation_requested_by"], instance_id),
            )
            new_status = "feito"
        else:
            conn.execute(
                """
                UPDATE task_instances
                SET status = 'pendente', confirmation_requested_by = NULL,
                    completed_by = NULL, completed_at = NULL
                WHERE id = ?
                """,
                (instance_id,),
            )
            new_status = "pendente"

        conn.execute(
            "INSERT INTO task_comments (task_id, user_id, text) VALUES (?, ?, ?)",
            (instance["task_id"], current_user["id"], comment),
        )
        conn.commit()
    finally:
        conn.close()
    return {"id": instance_id, "status": new_status}


@router.get("/tasks/{task_id}/comments")
def list_comments(task_id: int, current_user: sqlite3.Row = Depends(get_current_user)):
    conn = get_connection()
    try:
        task = conn.execute("SELECT id FROM tasks WHERE id = ?", (task_id,)).fetchone()
        if task is None:
            raise HTTPException(status_code=404, detail="Tarefa não encontrada")
        rows = conn.execute(
            """
            SELECT tc.id, tc.text, tc.created_at, tc.user_id, u.name AS user_name
            FROM task_comments tc
            JOIN users u ON u.id = tc.user_id
            WHERE tc.task_id = ?
            ORDER BY tc.id ASC
            """,
            (task_id,),
        ).fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]


@router.post("/tasks/{task_id}/comments")
def create_comment(
    task_id: int, payload: CommentCreate, current_user: sqlite3.Row = Depends(get_current_user)
):
    text = payload.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Comentário não pode ser vazio")

    conn = get_connection()
    try:
        task = conn.execute("SELECT id FROM tasks WHERE id = ?", (task_id,)).fetchone()
        if task is None:
            raise HTTPException(status_code=404, detail="Tarefa não encontrada")
        cur = conn.execute(
            "INSERT INTO task_comments (task_id, user_id, text) VALUES (?, ?, ?)",
            (task_id, current_user["id"], text),
        )
        conn.commit()
        comment_id = cur.lastrowid
        comment = conn.execute(
            """
            SELECT tc.id, tc.text, tc.created_at, tc.user_id, u.name AS user_name
            FROM task_comments tc
            JOIN users u ON u.id = tc.user_id
            WHERE tc.id = ?
            """,
            (comment_id,),
        ).fetchone()
    finally:
        conn.close()
    return dict(comment)
