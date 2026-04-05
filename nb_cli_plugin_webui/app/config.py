import os
import json
from enum import Enum
from typing import Any
from pathlib import Path

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
    generate_complexity_string,
)

CONFIG_FILE = "config.json"
CONFIG_FILE_PATH = get_config_file(CONFIG_FILE)


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
            str(Path.cwd() / "/projects") if "WEBUI_BUILD" in os.environ else str()
        ),
        description="Base directory used to create/manage bot projects.",
    )
    host: str = Field(default="localhost", description="WebUI bind host.")
    port: str = Field(default="12345", description="WebUI bind port.")
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
    container_runtime_profiles: list = Field(
        default_factory=list, description="Saved container runtime profiles."
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


async def generate_config():
    click.secho(_("Welcome to use NB CLI WebUI."), fg="green")
    click.secho("")
    click.secho(_("[Token Setting]"), fg="green")
    click.secho(_("Token is your key to access WebUI."))
    if await ConfirmPrompt(_("Do you want it generated?")).prompt_async(
        style=CLI_DEFAULT_STYLE
    ):
        token = generate_complexity_string(use_digits=True, use_punctuation=True)
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
    host = "localhost"
    port = "12345"
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
        secret_key=SecretStr(
            generate_complexity_string(32, use_digits=True, use_punctuation=True)
        ),
        salt=SecretStr(_salt),
        hashed_token=SecretStr(hashed_token),
    )
    CONFIG_FILE_PATH.write_text(user_config.to_json(), encoding="utf-8")

