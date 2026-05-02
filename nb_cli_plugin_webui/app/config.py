import os
import json
from enum import Enum
from typing import Any, Dict, Optional, Tuple
from pathlib import Path
from datetime import datetime, timezone

import click
from nb_cli.cli import CLI_DEFAULT_STYLE
from pydantic import Field, BaseModel, SecretStr
from noneprompt import InputPrompt, ConfirmPrompt

from nb_cli_plugin_webui.i18n import _

from .utils.security import salt
from .utils.storage import get_config_file
from .utils.string_utils import (
    TokenComplexityError,
    check_string_complexity,
    generate_access_token,
    generate_complexity_string,
)

CONFIG_FILE = "config.json"
CONFIG_FILE_PATH = get_config_file(CONFIG_FILE)
DEFAULT_LOCAL_HOST = "localhost"
DEFAULT_LOCAL_PORT = "12345"
DEFAULT_DOCKER_HOST = "0.0.0.0"
DEFAULT_DOCKER_PORT = "18080"
DEFAULT_DOCKER_BASE_DIR = "/projects"


class LogLevels(Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class SpecialTypeJSONEncoder(json.JSONEncoder):
    def default(self, o: Any) -> Any:
        if isinstance(o, SecretStr):
            return o.get_secret_value()
        if isinstance(o, Enum):
            return o.value
        return super().default(o)


class AppConfig(BaseModel):
    base_dir: str = Field(
        default_factory=lambda: (
            DEFAULT_DOCKER_BASE_DIR if "WEBUI_BUILD" in os.environ else str()
        ),
        description="Base directory used to create/manage bot projects.",
    )
    host: str = Field(
        default_factory=lambda: (
            os.environ.get("HOST", DEFAULT_DOCKER_HOST).strip()
            if "WEBUI_BUILD" in os.environ
            else DEFAULT_LOCAL_HOST
        ),
        description="WebUI bind host.",
    )
    port: str = Field(
        default_factory=lambda: (
            os.environ.get("PORT", DEFAULT_DOCKER_PORT).strip()
            if "WEBUI_BUILD" in os.environ
            else DEFAULT_LOCAL_PORT
        ),
        description="WebUI bind port.",
    )
    debug: int = Field(default=0, description="Enable debug mode.")
    enable_api_document: bool = Field(
        default=False, description="Enable API document endpoint."
    )

    log_level: LogLevels = Field(default=LogLevels.INFO, description="Log level.")
    log_is_store: bool = Field(default=False, description="Enable log persistence.")

    secret_key: SecretStr = Field(
        default=SecretStr(str()), description="JWT signing secret key."
    )
    hashed_token: SecretStr = Field(
        default=SecretStr(str()), description="Hashed login token."
    )
    salt: SecretStr = Field(default=SecretStr(str()), description="Token hash salt.")
    login_token_mode: str = Field(
        default="permanent",
        description="Login token mode: permanent or random.",
    )
    login_token_expires_at: int = Field(
        default=0,
        description="Unix timestamp when the current login token expires. 0 means no expiration.",
    )
    login_token_random_expire_hours: int = Field(
        default=24,
        description="How many hours a random login token remains valid.",
    )

    allowed_origins: list = Field(
        default=["*"],
        description="CORS allowed origins.",
    )

    process_log_destroy_seconds: int = Field(
        default=5 * 60, description="Retention in seconds for process logs."
    )

    extension_store_visible_items: int = Field(
        default=12, description="Store page size."
    )

    container_proxy_url: str = Field(
        default="", description="Container shared proxy URL."
    )
    container_http_proxy: str = Field(
        default="", description="Container HTTP proxy URL."
    )
    container_https_proxy: str = Field(
        default="", description="Container HTTPS proxy URL."
    )
    container_all_proxy: str = Field(
        default="", description="Container ALL_PROXY URL."
    )
    container_no_proxy: str = Field(
        default="", description="Container NO_PROXY values."
    )
    container_debian_mirror: str = Field(
        default="", description="Container Debian/APT mirror base URL."
    )
    container_pip_index_url: str = Field(
        default="", description="Container pip index-url."
    )
    container_pip_extra_index_url: str = Field(
        default="", description="Container pip extra-index-url."
    )
    container_pip_trusted_host: str = Field(
        default="", description="Container pip trusted-host."
    )
    github_proxy_base_url: str = Field(
        default="",
        description="Prefix used to proxy GitHub URLs, for example https://github.xisoul.cn",
    )
    container_runtime_profiles: list = Field(
        default_factory=list, description="Saved container runtime profiles."
    )
    bot_http_proxy: str = Field(
        default="", description="Bot/plugin runtime HTTP proxy URL."
    )
    bot_https_proxy: str = Field(
        default="", description="Bot/plugin runtime HTTPS proxy URL."
    )
    bot_all_proxy: str = Field(
        default="", description="Bot/plugin runtime ALL_PROXY URL."
    )
    bot_no_proxy: str = Field(
        default="", description="Bot/plugin runtime NO_PROXY values."
    )
    bot_proxy_protocol: str = Field(
        default="http", description="Bot proxy builder protocol."
    )
    bot_proxy_host: str = Field(
        default="", description="Bot proxy builder host."
    )
    bot_proxy_port: str = Field(
        default="", description="Bot proxy builder port."
    )
    bot_proxy_username: str = Field(
        default="", description="Bot proxy builder username."
    )
    bot_proxy_password: str = Field(
        default="", description="Bot proxy builder password."
    )
    bot_proxy_apply_target: str = Field(
        default="http_https", description="Bot proxy builder apply target."
    )
    bot_proxy_instances: str = Field(
        default="",
        description="Comma/newline separated project names that should use global bot proxy.",
    )
    backup_webdav_url: str = Field(
        default="", description="WebDAV endpoint used for backup storage."
    )
    backup_webdav_username: str = Field(
        default="", description="WebDAV username used for backup storage."
    )
    backup_webdav_password: str = Field(
        default="", description="WebDAV password used for backup storage."
    )
    backup_webdav_base_path: str = Field(
        default="/",
        description="WebDAV base path used to store backup archives.",
    )
    backup_s3_endpoint: str = Field(
        default="", description="S3 endpoint used for backup storage."
    )
    backup_s3_region: str = Field(
        default="us-east-1", description="S3 region used for backup storage."
    )
    backup_s3_bucket: str = Field(
        default="", description="S3 bucket used for backup storage."
    )
    backup_s3_access_key: str = Field(
        default="", description="S3 access key used for backup storage."
    )
    backup_s3_secret_key: str = Field(
        default="", description="S3 secret key used for backup storage."
    )
    backup_s3_prefix: str = Field(
        default="", description="Prefix path used when writing backups to S3."
    )
    backup_s3_force_path_style: bool = Field(
        default=True,
        description="Whether S3 backup requests should use path-style URLs.",
    )
    backup_auto_enabled: bool = Field(
        default=False, description="Whether scheduled backup is enabled."
    )
    backup_auto_interval_hours: int = Field(
        default=24, description="Scheduled backup interval in hours."
    )
    backup_keep_count: int = Field(
        default=10, description="How many remote backups to keep per project."
    )
    backup_archive_password: str = Field(
        default="",
        description="Optional password used to encrypt backup archives.",
    )
    backup_include_logs: bool = Field(
        default=False,
        description="Whether selected instance logs should be included in backups.",
    )
    backup_log_project_ids: list = Field(
        default_factory=list,
        description="Project ids whose instance logs should be included in backups.",
    )
    global_log_min_level: LogLevels = Field(
        default=LogLevels.DEBUG,
        description="Minimum level to keep frontend notification events.",
    )
    global_log_retention_days: int = Field(
        default=7, description="How many days global logs should be kept."
    )

    @property
    def log_level_str(self) -> str:
        return self.log_level.value

    def to_json(self) -> str:
        return json.dumps(self.dict(), cls=SpecialTypeJSONEncoder)

    def reset_token(self, token: str) -> None:
        self.salt = SecretStr(salt.gen_salt())
        self.hashed_token = SecretStr(
            salt.get_token_hash(self.salt.get_secret_value() + token)
        )

    def set_permanent_login_token(self, token: str) -> None:
        self.reset_token(token)
        self.login_token_mode = "permanent"
        self.login_token_expires_at = 0

    def set_random_login_token(self, token: str, expire_hours: int) -> None:
        self.reset_token(token)
        self.login_token_mode = "random"
        self.login_token_random_expire_hours = expire_hours
        self.login_token_expires_at = int(
            datetime.now(timezone.utc).timestamp() + (expire_hours * 60 * 60)
        )

    def check_necessary_config(self) -> bool:
        return bool(
            self.base_dir and self.secret_key and self.hashed_token and self.salt
        )

    def get_description(self, field_name: str) -> str:
        return self.__fields__[field_name].field_info.description


class ConfigParser(AppConfig):
    def load(self, path: Path):
        new_conf = self.parse_file(path)
        self.__dict__.update(new_conf.__dict__)

    def store(self, path: Path):
        path.write_text(self.to_json(), encoding="utf-8")


Config = ConfigParser()


def generate_secret_key(length: int = 32) -> str:
    return generate_complexity_string(
        length, use_digits=True, use_punctuation=True
    ).replace('"', "'")


def create_access_credentials(token: Optional[str] = None) -> Tuple[str, str, str]:
    access_token = (token or generate_access_token()).replace('"', "'")
    token_salt = salt.gen_salt()
    hashed_token = salt.get_token_hash(token_salt + access_token)
    return access_token, token_salt, hashed_token


def _build_runtime_config(
    raw_config: Optional[Dict[str, Any]] = None,
) -> Tuple[AppConfig, Optional[str]]:
    raw_config = raw_config or {}

    host = str(raw_config.get("host") or "").strip() or os.environ.get(
        "HOST",
        DEFAULT_DOCKER_HOST if "WEBUI_BUILD" in os.environ else DEFAULT_LOCAL_HOST,
    ).strip()
    port = str(raw_config.get("port") or "").strip() or os.environ.get(
        "PORT",
        DEFAULT_DOCKER_PORT if "WEBUI_BUILD" in os.environ else DEFAULT_LOCAL_PORT,
    ).strip()
    base_dir = str(raw_config.get("base_dir") or "").strip() or (
        DEFAULT_DOCKER_BASE_DIR if "WEBUI_BUILD" in os.environ else str()
    )
    secret_key = str(raw_config.get("secret_key") or "").strip()
    token_salt = str(raw_config.get("salt") or "").strip()
    hashed_token = str(raw_config.get("hashed_token") or "").strip()
    generated_token: Optional[str] = None
    if not (secret_key and token_salt and hashed_token):
        generated_token, token_salt, hashed_token = create_access_credentials()
        secret_key = generate_secret_key()

    config_data = dict(raw_config)
    config_data.update(
        {
            "base_dir": base_dir,
            "host": host,
            "port": port,
            "secret_key": secret_key,
            "salt": token_salt,
            "hashed_token": hashed_token,
        }
    )
    return AppConfig.parse_obj(config_data), generated_token


def ensure_docker_config() -> Optional[str]:
    if "WEBUI_BUILD" not in os.environ:
        return None

    raw_config: Dict[str, Any] = {}
    if CONFIG_FILE_PATH.exists():
        try:
            raw_text = CONFIG_FILE_PATH.read_text(encoding="utf-8")
            if raw_text.strip():
                raw_config = json.loads(raw_text)
        except (OSError, json.JSONDecodeError):
            raise RuntimeError(
                "Config file exists but is not valid JSON. Refusing to regenerate login credentials automatically. "
                "Please fix /app/config.json or clear it intentionally before restart."
            )

    has_runtime_defaults = all(
        str(raw_config.get(key) or "").strip() for key in ("base_dir", "host", "port")
    )
    has_auth_config = all(
        str(raw_config.get(key) or "").strip()
        for key in ("secret_key", "salt", "hashed_token")
    )
    if has_runtime_defaults and has_auth_config:
        return None

    if raw_config and not has_auth_config:
        raise RuntimeError(
            "Config file exists but login credential fields are incomplete. Refusing to regenerate token automatically. "
            "Please restore secret_key/salt/hashed_token or clear /app/config.json intentionally."
        )

    runtime_config, token = _build_runtime_config(raw_config)
    CONFIG_FILE_PATH.write_text(runtime_config.to_json(), encoding="utf-8")
    return token


async def generate_config():
    click.secho(_("Welcome to use NB CLI WebUI."), fg="green")
    click.secho("")
    click.secho(_("[Token Setting]"), fg="green")
    click.secho(_("Token is your key to access WebUI."))
    if await ConfirmPrompt(_("Do you want it generated?")).prompt_async(
        style=CLI_DEFAULT_STYLE
    ):
        token = generate_access_token()
    else:
        token = await InputPrompt(_("Please enter token:")).prompt_async(
            style=CLI_DEFAULT_STYLE
        )
        while True:
            try:
                check_string_complexity(token)
                break
            except TokenComplexityError as err:
                click.secho(str(err))

            token = await InputPrompt(_("Please enter again:")).prompt_async(
                style=CLI_DEFAULT_STYLE
            )

    token = token.replace('"', "'")

    click.secho(_("Your token is:"))
    click.secho(f"\n{token}\n", fg="green")
    click.secho(_("ATTENTION, TOKEN ONLY SHOW ONCE."), fg="red", bold=True)

    click.secho("")
    click.secho(_("[Server Setting]"), fg="green")
    host = DEFAULT_LOCAL_HOST
    port = DEFAULT_LOCAL_PORT
    if await ConfirmPrompt(
        _("Do you want to decide (host) and (port) by yourself?")
    ).prompt_async(style=CLI_DEFAULT_STYLE):
        host = await InputPrompt(_("Please enter host:")).prompt_async(
            style=CLI_DEFAULT_STYLE
        )
        port = await InputPrompt(_("Please enter port:")).prompt_async(
            style=CLI_DEFAULT_STYLE
        )
        while True:
            try:
                if int(port) < 1024 or int(port) > 49151:
                    raise ValueError
                break
            except ValueError:
                click.secho(
                    _("Port must be between 1024 and 49151. (Recommend: > 10000)")
                )
                port = await InputPrompt(_("Please enter port:")).prompt_async(
                    style=CLI_DEFAULT_STYLE
                )

        click.secho(_("Your webui url will be:"))
        click.secho(f"http://{host}:{port}/", fg="green")
    else:
        click.secho(_("Your webui url will decide by nb-cli."))

    click.secho("")
    click.secho(_("[General Setting]"), fg="green")
    click.secho(_("- Docker will ignore this and use current directory."), fg="yellow")
    click.secho(_("- Base directory. Example:"))
    click.secho(("  * Linux: /home/(user)/"))
    click.secho(("  * MacOS: /Users/(user)/"))
    click.secho(("  * Windows: C:/Users/Public/Pictures"))
    click.secho(_("- NoneBot will be stored here."))
    while True:
        base_dir = await InputPrompt(_("Please enter base directory:")).prompt_async(
            style=CLI_DEFAULT_STYLE
        )
        path = Path(base_dir)

        if base_dir and path.is_absolute() and path.is_dir():
            break

        if not base_dir:
            click.secho(_("Directory must not be empty."))
        if not path.exists():
            click.secho(_("Directory does not exist."))
        if not path.is_absolute():
            click.secho(_("Path must be absolute."))
        if not path.is_dir():
            click.secho(_("Path must be folder."))

    click.secho("")
    click.secho(_("[Setting Overview]"), fg="green")
    click.secho(_("Token: {token}").format(token=token))
    click.secho(_("WebUI URL: http://{host}:{port}/").format(host=host, port=port))
    click.secho(_("Base directory: {base_dir}").format(base_dir=base_dir))
    if not await ConfirmPrompt(_("Are you sure?")).prompt_async(
        style=CLI_DEFAULT_STYLE
    ):
        click.secho(_("Cleaning..."))
        return

    _salt = salt.gen_salt()
    hashed_token = salt.get_token_hash(_salt + token)

    user_config = AppConfig(
        base_dir=base_dir,
        host=host,
        port=port,
        secret_key=SecretStr(generate_secret_key()),
        salt=SecretStr(_salt),
        hashed_token=SecretStr(hashed_token),
    )
    CONFIG_FILE_PATH.write_text(user_config.to_json(), encoding="utf-8")

