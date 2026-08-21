import json
from pathlib import Path

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.json"

_DEFAULTS = {
    "telegram_bot_token": "",
    "api_host": "127.0.0.1",
    "api_port": 8284,
    "scheduler_interval_seconds": 60,
    "bot_poll_timeout_seconds": 30,
}


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        return dict(_DEFAULTS)
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    merged = {**_DEFAULTS, **data}
    return merged
