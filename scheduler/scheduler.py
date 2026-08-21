import time
from datetime import date, datetime, timedelta
from calendar import monthrange

import requests

from common.config import load_config
from common.db import get_connection, init_db
from bot.telegram_bot import send_message, format_due_date

WEEKDAY_CODES = ["SEG", "TER", "QUA", "QUI", "SEX", "SAB", "DOM"]


def _parse_date(value: str) -> date:
    return datetime.strptime(value.split(" ")[0], "%Y-%m-%d").date()


def compute_next_due_date(recurrence_kind: str, recurrence_value: str, reference: date) -> date:
    if recurrence_kind == "intervalo_dias":
        n = int(recurrence_value)
        return reference + timedelta(days=n)

    if recurrence_kind == "dia_fixo_mes":
        day = int(recurrence_value)
        year, month = reference.year, reference.month
        last_day_this_month = monthrange(year, month)[1]
        if reference.day < day <= last_day_this_month:
            return date(year, month, day)
        month += 1
        year += month > 12
        month = month if month <= 12 else 1
        day = min(day, monthrange(year, month)[1])
        return date(year, month, day)

    if recurrence_kind == "dia_semana":
        codes = {c.strip().upper() for c in recurrence_value.split(",") if c.strip()}
        target_weekdays = {WEEKDAY_CODES.index(c) for c in codes if c in WEEKDAY_CODES}
        if not target_weekdays:
            raise ValueError(f"recurrence_value inválido para dia_semana: {recurrence_value}")
        for offset in range(1, 8):
            candidate = reference + timedelta(days=offset)
            if candidate.weekday() in target_weekdays:
                return candidate

    raise ValueError(f"recurrence_kind desconhecido: {recurrence_kind}")


def generate_periodic_instances(conn):
    today = date.today()
    tasks = conn.execute(
        "SELECT * FROM tasks WHERE type = 'periodica' AND active = 1"
    ).fetchall()

    for task in tasks:
        last_instance = conn.execute(
            """
            SELECT * FROM task_instances
            WHERE task_id = ?
            ORDER BY id DESC LIMIT 1
            """,
            (task["id"],),
        ).fetchone()

        if last_instance is not None and last_instance["status"] in ("pendente", "aguardando_confirmacao"):
            continue  # já existe pendência em aberto (ou esperando confirmação), não gera outra

        max_occurrences = task["recurrence_max_occurrences"]
        if max_occurrences is not None:
            total_instances = conn.execute(
                "SELECT COUNT(*) AS n FROM task_instances WHERE task_id = ?", (task["id"],)
            ).fetchone()["n"]
            if total_instances >= max_occurrences:
                conn.execute("UPDATE tasks SET active = 0 WHERE id = ?", (task["id"],))
                continue

        if last_instance is not None:
            reference = _parse_date(last_instance["due_date"] or last_instance["created_at"])
        else:
            reference = _parse_date(task["created_at"])

        next_due = compute_next_due_date(task["recurrence_kind"], task["recurrence_value"], reference)

        end_date = task["recurrence_end_date"]
        if end_date is not None and next_due > _parse_date(end_date):
            conn.execute("UPDATE tasks SET active = 0 WHERE id = ?", (task["id"],))
            continue

        if next_due <= today:
            conn.execute(
                "INSERT INTO task_instances (task_id, due_date, status) VALUES (?, ?, 'pendente')",
                (task["id"], next_due.isoformat()),
            )
    conn.commit()


def send_reminders(conn, token: str):
    now = datetime.now()
    current_hm = now.strftime("%H:%M")
    today = now.strftime("%Y-%m-%d")

    configs = conn.execute(
        """
        SELECT * FROM reminder_configs
        WHERE enabled = 1 AND hour = ?
          AND (last_sent_date IS NULL OR last_sent_date != ?)
        """,
        (current_hm, today),
    ).fetchall()

    for cfg in configs:
        user = conn.execute("SELECT * FROM users WHERE id = ?", (cfg["user_id"],)).fetchone()
        if user is None or not user["telegram_chat_id"]:
            continue

        rows = conn.execute(
            """
            SELECT ti.id, t.title, t.priority, ti.due_date
            FROM task_instances ti
            JOIN tasks t ON t.id = ti.task_id
            WHERE ti.status = 'pendente'
              AND (t.assigned_to = ? OR t.assigned_to IS NULL)
            ORDER BY
                CASE t.priority
                    WHEN 'alta' THEN 0
                    WHEN 'media' THEN 1
                    WHEN 'baixa' THEN 2
                    ELSE 3
                END,
                ti.id ASC
            """,
            (user["id"],),
        ).fetchall()

        if rows:
            linhas = [
                f"#{r['id']} [{r['priority']}]{format_due_date(r['due_date'])} {r['title']}"
                for r in rows
            ]
            text = "Lembrete de tarefas pendentes:\n" + "\n".join(linhas)
        else:
            text = "Sem tarefas pendentes no momento. 🎉"

        try:
            send_message(token, user["telegram_chat_id"], text)
        except requests.RequestException as e:
            print(f"Falha ao enviar lembrete para {user['username']}: {e}")
            continue

        conn.execute(
            "UPDATE reminder_configs SET last_sent_date = ? WHERE id = ?", (today, cfg["id"])
        )
    conn.commit()


def run():
    config = load_config()
    token = config["telegram_bot_token"]
    interval = config["scheduler_interval_seconds"]

    init_db()
    print("Scheduler iniciado...", flush=True)
    while True:
        conn = get_connection()
        try:
            generate_periodic_instances(conn)
            if token:
                send_reminders(conn, token)
        except Exception as e:
            print(f"Erro no scheduler: {e}", flush=True)
        finally:
            conn.close()
        time.sleep(interval)


if __name__ == "__main__":
    run()
