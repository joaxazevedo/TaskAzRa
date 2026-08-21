import re
import sys
import time
import sqlite3
from datetime import date, datetime

import requests

from common.config import load_config
from common.db import get_connection, init_db
from common.auth import verify_pin
from backend.tags import set_task_tags, get_tags_for_task

# No Windows, stdout redirecionado costuma usar cp1252, que não suporta emoji
# (títulos de tarefa e respostas do bot podem conter emoji livremente).
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

TELEGRAM_API = "https://api.telegram.org/bot{token}/{method}"


def log(msg: str) -> None:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {msg}", flush=True)


def api_call(token: str, method: str, **params):
    url = TELEGRAM_API.format(token=token, method=method)
    resp = requests.post(url, json=params, timeout=35)
    resp.raise_for_status()
    return resp.json()


def send_message(token: str, chat_id, text: str):
    api_call(token, "sendMessage", chat_id=chat_id, text=text)
    log(f"[bot -> {chat_id}] {text}")


def get_user_by_chat_id(conn, chat_id: str):
    return conn.execute(
        "SELECT * FROM users WHERE telegram_chat_id = ?", (str(chat_id),)
    ).fetchone()


def handle_vincular(conn, chat_id, args: str) -> str:
    parts = args.split()
    if len(parts) != 2:
        return "Uso: /vincular <usuario> <pin>"
    username, pin = parts
    row = conn.execute(
        "SELECT id, pin_hash FROM users WHERE username = ?", (username,)
    ).fetchone()
    if row is None or not verify_pin(pin, row["pin_hash"]):
        return "Usuário ou PIN inválido."
    try:
        conn.execute(
            "UPDATE users SET telegram_chat_id = ? WHERE id = ?", (str(chat_id), row["id"])
        )
        conn.commit()
    except sqlite3.IntegrityError:
        return "Este chat já está vinculado a outro usuário."
    return "Conta vinculada com sucesso! Envie /ajuda para ver os comandos."


def format_due_date(due_date_str) -> str:
    if not due_date_str:
        return ""
    due = datetime.strptime(due_date_str, "%Y-%m-%d").date()
    if due.year == date.today().year:
        return f" [Limite: {due.strftime('%m-%d')}]"
    return f" [Limite: {due.strftime('%y-%m-%d')}]"


def extract_tags(text: str):
    """Extrai #hashtags do texto e devolve (titulo_sem_tags, lista_de_tags)."""
    tags = re.findall(r"#(\w+)", text)
    title = re.sub(r"#\w+", "", text)
    title = re.sub(r"\s+", " ", title).strip()
    return title, tags


def handle_tarefas(conn, user, args: str = "") -> str:
    search_text, filter_tags = extract_tags(args or "")
    search_text = search_text.strip().lower()
    filter_tags_lower = {t.lower() for t in filter_tags}

    rows = conn.execute(
        """
        SELECT ti.id, t.id AS task_id, t.title, t.priority, ti.due_date
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
    if not rows:
        return "Nenhuma tarefa pendente. 🎉"

    linhas = []
    for r in rows:
        # Busca por texto: qualquer trecho do título (substring, não palavra
        # inteira) — "ver" bate com "verificar", "versão", etc.
        if search_text and search_text not in r["title"].lower():
            continue

        tags = get_tags_for_task(conn, r["task_id"])
        # Com uma ou mais tags, basta a tarefa ter PELO MENOS UMA delas (OU).
        if filter_tags_lower and not filter_tags_lower & {t.lower() for t in tags}:
            continue

        tags_suffix = f" {' '.join('#' + t for t in tags)}" if tags else ""
        linhas.append(
            f"#{r['id']} [{r['priority']}]{format_due_date(r['due_date'])} {r['title']}{tags_suffix}"
        )

    if not linhas:
        partes = []
        if search_text:
            partes.append(f'"{search_text}"')
        partes.extend("#" + t for t in filter_tags)
        return f"Nenhuma tarefa pendente com {' '.join(partes)}."
    return "Pendentes:\n" + "\n".join(linhas)


def handle_feito(conn, user, args: str) -> str:
    if not args.strip().isdigit():
        return "Uso: /feito <id_da_instancia>"
    instance_id = int(args.strip())
    row = conn.execute(
        "SELECT * FROM task_instances WHERE id = ?", (instance_id,)
    ).fetchone()
    if row is None:
        return "Instância não encontrada."
    if row["status"] == "feito":
        return "Essa tarefa já estava concluída."
    if row["status"] == "aguardando_confirmacao":
        return "Essa tarefa já está aguardando confirmação de quem criou."

    task = conn.execute(
        "SELECT needs_confirmation FROM tasks WHERE id = ?", (row["task_id"],)
    ).fetchone()
    if task["needs_confirmation"]:
        conn.execute(
            """
            UPDATE task_instances
            SET status = 'aguardando_confirmacao', confirmation_requested_by = ?
            WHERE id = ?
            """,
            (user["id"], instance_id),
        )
        conn.commit()
        return f"Tarefa #{instance_id} marcada como feita, aguardando confirmação de quem criou. ⏳"

    conn.execute(
        """
        UPDATE task_instances
        SET status = 'feito', completed_by = ?, completed_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (user["id"], instance_id),
    )
    conn.commit()
    return f"Tarefa #{instance_id} marcada como concluída. ✅"


def handle_nova(conn, user, args: str) -> str:
    title, tag_names = extract_tags(args.strip())
    if not title:
        return "Uso: /nova <título> #tag1 #tag2"
    cur = conn.execute(
        "INSERT INTO tasks (title, type, created_by, assigned_to) VALUES (?, 'unica', ?, ?)",
        (title, user["id"], user["id"]),
    )
    task_id = cur.lastrowid
    cur = conn.execute(
        "INSERT INTO task_instances (task_id, status) VALUES (?, 'pendente')", (task_id,)
    )
    instance_id = cur.lastrowid
    if tag_names:
        set_task_tags(conn, task_id, tag_names)
    conn.commit()
    # O id mostrado precisa ser o da instância (task_instances.id), pois é
    # esse número que aparece em /tarefas e que /feito espera receber —
    # tasks.id é uma sequência diferente e confundia o usuário.
    tags_suffix = f" {' '.join('#' + t for t in tag_names)}" if tag_names else ""
    return f"Tarefa única criada: #{instance_id} {title}{tags_suffix}"


def handle_manual(conn, user, args: str) -> str:
    title = args.strip()
    if not title:
        return "Uso: /manual <título>"
    cur = conn.execute(
        "INSERT INTO tasks (title, type, created_by, assigned_to) VALUES (?, 'manual', ?, ?)",
        (title, user["id"], user["id"]),
    )
    conn.commit()
    return f"Tarefa manual criada: #{cur.lastrowid} {title}. Use /ativar {cur.lastrowid} quando precisar."


def handle_ativar(conn, args: str) -> str:
    if not args.strip().isdigit():
        return "Uso: /ativar <id_da_tarefa>"
    task_id = int(args.strip())
    task = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if task is None:
        return "Tarefa não encontrada."
    if task["type"] != "manual":
        return "Apenas tarefas do tipo manual podem ser ativadas."
    cur = conn.execute(
        "INSERT INTO task_instances (task_id, status) VALUES (?, 'pendente')", (task_id,)
    )
    conn.commit()
    return f"Ativada: #{cur.lastrowid} {task['title']}"


def handle_comentar(conn, user, args: str) -> str:
    parts = args.strip().split(maxsplit=1)
    if len(parts) < 2 or not parts[0].isdigit():
        return "Uso: /comentar <id> <texto>"
    instance_id = int(parts[0])
    text = parts[1].strip()
    if not text:
        return "Uso: /comentar <id> <texto>"

    instance = conn.execute(
        "SELECT task_id FROM task_instances WHERE id = ?", (instance_id,)
    ).fetchone()
    if instance is None:
        return "Tarefa não encontrada."

    conn.execute(
        "INSERT INTO task_comments (task_id, user_id, text) VALUES (?, ?, ?)",
        (instance["task_id"], user["id"], text),
    )
    conn.commit()
    return "Comentário adicionado. 💬"


def handle_ajuda() -> str:
    return (
        "Comandos disponíveis:\n"
        "/vincular <usuario> <pin> - vincula este chat à sua conta\n"
        "/tarefas <texto> #tag1 #tag2 - lista tarefas pendentes; texto busca no título "
        "(qualquer trecho), tags filtram por pelo menos uma delas\n"
        "/feito <id> - marca tarefa como concluída\n"
        "/nova <título> #tag1 #tag2 - cria tarefa única, com tags opcionais\n"
        "/manual <título> - cria tarefa de ativação manual\n"
        "/ativar <id_tarefa> - ativa uma instância de tarefa manual\n"
        "/comentar <id> <texto> - adiciona um comentário na tarefa\n"
    )


def process_message(token: str, message: dict):
    chat_id = message["chat"]["id"]
    text = (message.get("text") or "").strip()
    sender = message.get("from", {})
    sender_label = sender.get("username") or sender.get("first_name") or "desconhecido"
    log(f"[{chat_id} @{sender_label}] {text!r}")

    if not text.startswith("/"):
        return

    command, _, args = text.partition(" ")
    command = command.split("@")[0].lower()

    conn = get_connection()
    try:
        if command == "/start":
            send_message(
                token, chat_id,
                f"Bem-vindo(a) ao TaskAzRa! Seu chat_id é {chat_id}.\n"
                "Use /vincular <usuario> <pin> para associar este chat à sua conta.",
            )
            return

        if command == "/vincular":
            send_message(token, chat_id, handle_vincular(conn, chat_id, args))
            return

        user = get_user_by_chat_id(conn, chat_id)
        if user is None:
            send_message(token, chat_id, "Conta não vinculada. Use /vincular <usuario> <pin>.")
            return

        if command == "/tarefas":
            send_message(token, chat_id, handle_tarefas(conn, user, args))
        elif command == "/feito":
            send_message(token, chat_id, handle_feito(conn, user, args))
        elif command == "/nova":
            send_message(token, chat_id, handle_nova(conn, user, args))
        elif command == "/manual":
            send_message(token, chat_id, handle_manual(conn, user, args))
        elif command == "/ativar":
            send_message(token, chat_id, handle_ativar(conn, args))
        elif command == "/comentar":
            send_message(token, chat_id, handle_comentar(conn, user, args))
        elif command == "/ajuda":
            send_message(token, chat_id, handle_ajuda())
        else:
            send_message(token, chat_id, "Comando não reconhecido. Envie /ajuda.")
    finally:
        conn.close()


def run():
    config = load_config()
    token = config["telegram_bot_token"]
    if not token:
        raise RuntimeError("telegram_bot_token não configurado em config.json")

    init_db()
    offset = 0
    log("Bot Telegram iniciado (polling)...")
    while True:
        try:
            result = api_call(
                token, "getUpdates", offset=offset, timeout=config["bot_poll_timeout_seconds"]
            )
            for update in result.get("result", []):
                offset = update["update_id"] + 1
                message = update.get("message")
                if message:
                    process_message(token, message)
        except requests.RequestException as e:
            log(f"Erro de rede no bot, tentando novamente em 5s: {e}")
            time.sleep(5)
        except Exception as e:
            log(f"Erro inesperado no bot: {e}")
            time.sleep(5)


if __name__ == "__main__":
    run()
