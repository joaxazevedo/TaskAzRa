import os

os.environ.setdefault("PYTHONUNBUFFERED", "1")  # saída em tempo real, sem buffer, nos 3 processos

import multiprocessing as mp
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from common.config import load_config
from common.db import init_db


def run_api():
    import uvicorn

    config = load_config()
    uvicorn.run("backend.main:app", host=config["api_host"], port=config["api_port"], log_level="info")


def run_bot():
    from bot.telegram_bot import run

    run()


def run_scheduler():
    from scheduler.scheduler import run

    run()


def main():
    init_db()

    processes = {
        "api": mp.Process(target=run_api, name="api"),
        "bot": mp.Process(target=run_bot, name="bot"),
        "scheduler": mp.Process(target=run_scheduler, name="scheduler"),
    }

    for name, proc in processes.items():
        proc.start()
        print(f"[orchestrator] processo '{name}' iniciado (pid={proc.pid})", flush=True)

    try:
        while True:
            for name, proc in processes.items():
                if not proc.is_alive():
                    print(f"[orchestrator] processo '{name}' morreu, encerrando os demais...", flush=True)
                    raise SystemExit(1)
            time.sleep(2)
    except KeyboardInterrupt:
        print("\n[orchestrator] encerrando...", flush=True)
    finally:
        for proc in processes.values():
            if proc.is_alive():
                proc.terminate()
        for proc in processes.values():
            proc.join(timeout=5)


if __name__ == "__main__":
    mp.set_start_method("spawn", force=True)
    sys.exit(main())
