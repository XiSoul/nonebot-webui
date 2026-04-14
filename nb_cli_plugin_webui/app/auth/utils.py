import asyncio
from datetime import datetime, timezone
from typing import Tuple

from fastapi import WebSocket

from nb_cli_plugin_webui.app.config import CONFIG_FILE_PATH, Config, generate_secret_key
from nb_cli_plugin_webui.app.logging import logger
from nb_cli_plugin_webui.app.utils.string_utils import generate_access_token
from pydantic import SecretStr

from nb_cli_plugin_webui.app.utils.security import jwt


def normalize_login_token_mode(value: object) -> str:
    normalized = value.strip().lower() if isinstance(value, str) else ""
    return normalized if normalized in {"permanent", "random"} else "permanent"


def normalize_random_token_expire_hours(value: object) -> int:
    try:
        hours = int(value)
    except Exception:
        return 24
    return min(720, max(1, hours))


def get_login_token_expires_at() -> int:
    try:
        return int(getattr(Config, "login_token_expires_at", 0) or 0)
    except Exception:
        return 0


def is_random_login_token_expired() -> bool:
    if normalize_login_token_mode(getattr(Config, "login_token_mode", "permanent")) != "random":
        return False

    expires_at = get_login_token_expires_at()
    if expires_at <= 0:
        return False
    return int(datetime.now(timezone.utc).timestamp()) >= expires_at


def configure_random_login_token(
    *,
    expire_hours: object = 24,
    reason: str = "updated",
    persist: bool = True,
) -> Tuple[str, int]:
    normalized_hours = normalize_random_token_expire_hours(expire_hours)
    token = generate_access_token()
    Config.set_random_login_token(token, normalized_hours)
    Config.secret_key = SecretStr(generate_secret_key())
    expires_at = get_login_token_expires_at()
    if persist:
        Config.store(CONFIG_FILE_PATH)

    expires_at_text = datetime.fromtimestamp(
        expires_at, tz=timezone.utc
    ).astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
    logger.warning(
        f"Random login token {reason} and has been written to Docker/service logs. "
        f"token={token} expires_at={expires_at_text} ttl_hours={normalized_hours}"
    )
    return token, expires_at


def ensure_login_token_is_active() -> None:
    if not is_random_login_token_expired():
        return

    configure_random_login_token(reason="expired and was regenerated automatically")
    raise ValueError(
        "Random login token expired. A new random token has been generated and written to Docker/service logs. Please sign in again."
    )


async def websocket_auth(websocket: WebSocket, *, secret_key: str) -> bool:
    try:
        ensure_login_token_is_active()
        recv = await asyncio.wait_for(websocket.receive(), 5)
        token = recv.get("text", "unknown")
        jwt.verify_and_read_jwt(token, secret_key)
    except Exception:
        return False
    return True
