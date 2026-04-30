import os
import webbrowser
from pathlib import Path
from typing import List, cast

import click
from pydantic import ValidationError
from nb_cli.i18n import _ as nb_cli_i18n
from noneprompt import Choice, ListPrompt, ConfirmPrompt, CancelledError
from nb_cli.cli import CLI_DEFAULT_STYLE, ClickAliasedGroup, run_sync, run_async

from nb_cli_plugin_webui.i18n import _
from nb_cli_plugin_webui.app.handlers.project import PROJECT_DATA_PATH
from nb_cli_plugin_webui.app.config import (
    CONFIG_FILE_PATH,
    Config,
    ensure_docker_config,
    generate_config,
)

from .token import token
from .config import config
from .docker import docker

STATIC_PATH = Path(__file__).resolve().parents[1] / "dist"


def _ensure_static_assets_ready() -> bool:
    if STATIC_PATH.exists():
        return True

    click.secho(
        _("WebUI dist directory not found, please reinstall to fix."), fg="red"
    )
    if "WEBUI_BUILD" in os.environ:
        click.secho(
            _(
                "If you mounted the source repo into /app, run `pnpm -C frontend run build-only` first or avoid overriding /app in the container."
            ),
            fg="yellow",
        )
    return False


def _prepare_runtime_config() -> bool:
    if "WEBUI_BUILD" in os.environ:
        generated_token = ensure_docker_config()
        if generated_token:
            Config.load(CONFIG_FILE_PATH)
            click.secho(_("Docker runtime config initialized."), fg="green")
            click.secho(
                _("WebUI URL: http://{host}:{port}/").format(
                    host=Config.host,
                    port=Config.port,
                ),
                fg="green",
            )
            click.secho(_("Token: {token}").format(token=generated_token), fg="yellow")
            click.secho(_("ATTENTION, TOKEN ONLY SHOW ONCE."), fg="red", bold=True)

    if not CONFIG_FILE_PATH.exists():
        return True

    try:
        Config.load(CONFIG_FILE_PATH)
    except ValidationError:
        click.secho(_("Config file is broken, run `nb ui clear` to fix."), fg="red")
        return False

    return True


@click.group(
    cls=ClickAliasedGroup, invoke_without_command=True, help=_("Start up NB CLI UI.")
)
@click.pass_context
@run_async
async def webui(ctx: click.Context):
    if not _prepare_runtime_config():
        return

    if ctx.invoked_subcommand is not None:
        return

    if not _ensure_static_assets_ready():
        return

    if not CONFIG_FILE_PATH.exists():
        if not Config.check_necessary_config():
            await generate_config()
            return

    command = cast(ClickAliasedGroup, ctx.command)

    choices: List[Choice[click.Command]] = list()
    for sub_cmd_name in await run_sync(command.list_commands)(ctx):
        if sub_cmd := await run_sync(command.get_command)(ctx, sub_cmd_name):
            choices.append(
                Choice(
                    sub_cmd.help
                    or nb_cli_i18n("Run subcommand {sub_cmd.name!r}").format(
                        sub_cmd=sub_cmd
                    ),
                    sub_cmd,
                )
            )

    try:
        result = await ListPrompt(
            nb_cli_i18n("What do you want to do?"), choices=choices
        ).prompt_async(style=CLI_DEFAULT_STYLE)
    except CancelledError:
        ctx.exit()

    sub_cmd = result.data
    await run_sync(ctx.invoke)(sub_cmd)


@webui.command(help=_("Run WebUI."))
@click.option(
    "-h",
    "--host",
    type=str,
    show_default=True,
    help=_("The host required to access NB CLI UI."),
    default=None,
)
@click.option(
    "-p",
    "--port",
    type=int,
    show_default=True,
    help=_("The port required to access NB CLI UI."),
    default=None,
)
@run_async
async def run(host: str, port: int):
    from nb_cli_plugin_webui import server

    if not _ensure_static_assets_ready():
        return

    if not _prepare_runtime_config():
        return

    if not host:
        host = Config.host
    if not port:
        port = int(Config.port)
    else:
        if port < 1024 or port > 49151:
            click.secho(
                _("Port must be between 1024 and 49151. (Recommend: > 10000)"), fg="red"
            )
            return

    try:
        webbrowser.open(f"http://{host}:{port}/")
    except webbrowser.Error:
        pass
    await server.run_server(host, port)


@webui.command(help=_("Clear WebUI data."))
@run_async
async def clear():
    clear_file = await ListPrompt(
        _("Which data do you want to clear?"),
        choices=[
            Choice(CONFIG_FILE_PATH.name, CONFIG_FILE_PATH),
            Choice(PROJECT_DATA_PATH.name, PROJECT_DATA_PATH),
        ],
    ).prompt_async(style=CLI_DEFAULT_STYLE)

    if not await ConfirmPrompt(_("Are you sure to clear?")).prompt_async(
        style=CLI_DEFAULT_STYLE
    ):
        return

    if not clear_file.data.exists():
        click.secho(_("File not found."), fg="yellow")
        return

    try:
        os.remove(clear_file.data)
    except Exception as e:
        click.secho(str(e), fg="red")
        return

    click.secho(_("File cleared."), fg="green")


webui.add_command(config)
webui.add_command(docker)
webui.add_command(token)
