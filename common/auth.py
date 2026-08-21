import hashlib
import secrets


def hash_pin(pin: str) -> str:
    salt = secrets.token_hex(8)
    digest = hashlib.sha256((salt + pin).encode("utf-8")).hexdigest()
    return f"{salt}${digest}"


def verify_pin(pin: str, stored: str) -> bool:
    try:
        salt, digest = stored.split("$", 1)
    except ValueError:
        return False
    return hashlib.sha256((salt + pin).encode("utf-8")).hexdigest() == digest


def generate_session_token() -> str:
    return secrets.token_urlsafe(32)
