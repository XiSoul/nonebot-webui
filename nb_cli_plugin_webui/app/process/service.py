import os
import sys
import socket
import asyncio
import shlex
from typing import Dict, List, Optional, Tuple
from pathlib import Path

from dotenv import dotenv_values
from nb_cli.config import SimpleInfo as CliSimpleInfo
from nb_cli.handlers import get_default_python, generate_run_script

from nb_cli_plugin_webui.app.config import Config
from nb_cli_plugin_webui.app.project import service as project_service
from nb_cli_plugin_webui.app.handlers.process import (
    Processor,
    CustomLog,
    LogStorage,
    ProcessManager,
    LogStorageFather,
    ProcessAlreadyRunning,
    ProcessNotRunning,
)
from nb_cli_plugin_webui.app.utils.bot_proxy import get_bot_proxy_env, get_pip_proxy_env

from .exceptions import DriverNotFound, AdapterNotFound


SHELL_COMMAND_DONE_MARKER = "__NB_WEBUI_CMD_DONE__:"
HTMLRENDER_DEPENDENCY_MARKERS = (
    "nonebot-plugin-htmlrender",
    "nonebot_plugin_htmlrender",
)
HTMLRENDER_PROJECT_FILES = (
    "pyproject.toml",
    "requirements.txt",
    "requirements-dev.txt",
    "requirements-prod.txt",
    "poetry.lock",
    "uv.lock",
    "Pipfile",
    "Pipfile.lock",
)


class ProjectShellSessionManager:
    sessions: Dict[str, Processor] = dict()

    @classmethod
    def get_session(cls, project_id: str) -> Optional[Processor]:
        session = cls.sessions.get(project_id)
        if session is None:
            return None
        if session.refresh_runtime_state():
            return session
        cls.sessions.pop(project_id, None)
        return None

    @classmethod
    def set_session(cls, project_id: str, session: Processor) -> None:
        cls.sessions[project_id] = session

    @classmethod
    async def stop_session(cls, project_id: str) -> bool:
        session = cls.sessions.pop(project_id, None)
        if session is None:
            return False

        try:
            await session.stop()
        except Exception:
            pass
        return True


def _is_port_available(port: int) -> bool:
    if port <= 0:
        return False
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("0.0.0.0", port))
            return True
        except OSError:
            return False


def _pick_available_port(project_id: str) -> int:
    base = 20000 + (sum(ord(ch) for ch in project_id) % 20000)
    reserved_ports = set(
        project_service.get_project_port_usage(exclude_project_id=project_id).keys()
    )
    for offset in range(0, 20000):
        candidate = base + offset
        if candidate > 65535:
            candidate = 1024 + (candidate - 65536)
        if candidate not in reserved_ports and _is_port_available(candidate):
            return candidate
    return 0


def _load_project_env_data(project_meta, project_dir: Path) -> dict:
    env_filename = str(getattr(project_meta, "use_env", "") or "").strip()
    if not env_filename:
        return {}

    env_file = project_dir / env_filename
    if not env_file.exists():
        return {}

    return dotenv_values(env_file)


def _resolve_runtime_path(project_dir: Path, raw_value: str) -> str:
    resolved = Path(os.path.expanduser(raw_value))
    if not resolved.is_absolute():
        resolved = project_dir / resolved
    return str(resolved.absolute())


def _project_mentions_htmlrender(project_meta, project_dir: Path) -> bool:
    project_plugins = getattr(project_meta, "plugins", None) or []
    for plugin in project_plugins:
        plugin_module = str(getattr(plugin, "module_name", "") or "").lower()
        plugin_link = str(getattr(plugin, "project_link", "") or "").lower()
        plugin_name = str(getattr(plugin, "name", "") or "").lower()
        if any(
            marker in value
            for marker in HTMLRENDER_DEPENDENCY_MARKERS
            for value in (plugin_module, plugin_link, plugin_name)
        ):
            return True

    for file_name in HTMLRENDER_PROJECT_FILES:
        candidate = project_dir / file_name
        if not candidate.is_file():
            continue
        try:
            content = candidate.read_text(encoding="utf-8").lower()
        except UnicodeDecodeError:
            content = candidate.read_text(encoding="utf-8", errors="ignore").lower()
        except Exception:
            continue

        if any(marker in content for marker in HTMLRENDER_DEPENDENCY_MARKERS):
            return True

    return False


def _default_nonebot2_data_dir(env: dict) -> Path:
    if sys.platform == "win32":
        local_app_data = str(env.get("LOCALAPPDATA") or "").strip()
        if local_app_data:
            return Path(local_app_data) / "nonebot2"
        home_dir = Path(str(env.get("USERPROFILE") or Path.home()))
        return home_dir / "AppData" / "Local" / "nonebot2"

    home_dir = Path(str(env.get("HOME") or Path.home()))
    if sys.platform == "darwin":
        return home_dir / "Library" / "Application Support" / "nonebot2"

    data_home = str(env.get("XDG_DATA_HOME") or "").strip()
    if data_home:
        return Path(data_home) / "nonebot2"
    return home_dir / ".local" / "share" / "nonebot2"


def _apply_htmlrender_browser_path(env: dict, project_meta, project_dir: Path) -> None:
    if str(env.get("PLAYWRIGHT_BROWSERS_PATH") or "").strip():
        return

    env_data = _load_project_env_data(project_meta, project_dir)

    explicit_browser_path = str(
        env_data.get("PLAYWRIGHT_BROWSERS_PATH")
        or env_data.get("playwright_browsers_path")
        or ""
    ).strip()
    if explicit_browser_path:
        env["PLAYWRIGHT_BROWSERS_PATH"] = _resolve_runtime_path(
            project_dir, explicit_browser_path
        )
        return

    htmlrender_storage_path = str(
        env_data.get("htmlrender_storage_path")
        or env_data.get("HTMLRENDER_STORAGE_PATH")
        or ""
    ).strip()
    if htmlrender_storage_path:
        env["PLAYWRIGHT_BROWSERS_PATH"] = _resolve_runtime_path(
            project_dir, htmlrender_storage_path
        )
        return

    if not _project_mentions_htmlrender(project_meta, project_dir):
        return

    env["PLAYWRIGHT_BROWSERS_PATH"] = str(
        (_default_nonebot2_data_dir(env) / "nonebot_plugin_htmlrender").absolute()
    )


def build_project_runtime_env(project_meta, *, pip_safe: bool = False) -> Tuple[dict, bool]:
    project_dir = Path(project_meta.project_dir)
    if pip_safe:
        env, socks_proxy_disabled = get_pip_proxy_env(
            os.environ.copy(), project_meta=project_meta
        )
    else:
        env = get_bot_proxy_env(os.environ.copy(), project_meta=project_meta)
        socks_proxy_disabled = False
    env["TERM"] = "xterm-color"

    if sys.platform == "win32":
        venv_path = project_dir / Path(".venv/Scripts")
        env["PATH"] = f"{venv_path.absolute()};{env.get('PATH', '')}"
    else:
        venv_path = project_dir / Path(".venv/bin")
        env["PATH"] = f"{venv_path.absolute()}:{env.get('PATH', '')}"

    virtual_env = project_dir / ".venv"
    if virtual_env.is_dir():
        env["VIRTUAL_ENV"] = str(virtual_env.absolute())

    _apply_htmlrender_browser_path(env, project_meta, project_dir)

    return env, socks_proxy_disabled


def _get_project_python_path(project_dir: Path) -> str:
    if sys.platform == "win32":
        python_path = project_dir / ".venv" / "Scripts" / "python.exe"
    else:
        python_path = project_dir / ".venv" / "bin" / "python"

    return str(python_path.absolute()) if python_path.exists() else "python"


def _build_shell_bootstrap_script(
    project_dir: Path, proxy_env: Optional[Dict[str, str]] = None
) -> str:
    project_python = _get_project_python_path(project_dir)
    quoted_python = shlex.quote(project_python)
    proxy_env = proxy_env or {}
    saved_http_proxy = shlex.quote(
        str(proxy_env.get("HTTP_PROXY") or proxy_env.get("http_proxy") or "")
    )
    saved_https_proxy = shlex.quote(
        str(proxy_env.get("HTTPS_PROXY") or proxy_env.get("https_proxy") or "")
    )
    saved_all_proxy = shlex.quote(
        str(proxy_env.get("ALL_PROXY") or proxy_env.get("all_proxy") or "")
    )
    saved_no_proxy = shlex.quote(
        str(proxy_env.get("NO_PROXY") or proxy_env.get("no_proxy") or "")
    )
    return (
        f"__nb_webui_python={quoted_python}\n"
        f"__nb_webui_saved_http_proxy={saved_http_proxy}\n"
        f"__nb_webui_saved_https_proxy={saved_https_proxy}\n"
        f"__nb_webui_saved_all_proxy={saved_all_proxy}\n"
        f"__nb_webui_saved_no_proxy={saved_no_proxy}\n"
        "pip() {\n"
        '  case "${HTTP_PROXY:-${http_proxy:-}} ${HTTPS_PROXY:-${https_proxy:-}} ${ALL_PROXY:-${all_proxy:-}}" in\n'
        "    *socks4://*|*socks4a://*|*socks5://*|*socks5h://*)\n"
        '      env -u HTTP_PROXY -u HTTPS_PROXY -u ALL_PROXY -u http_proxy -u https_proxy -u all_proxy "$__nb_webui_python" -m pip "$@"\n'
        "      ;;\n"
        "    *)\n"
        '      "$__nb_webui_python" -m pip "$@"\n'
        "      ;;\n"
        "  esac\n"
        "}\n"
        "playwright() {\n"
        '  if [ -n "${__nb_webui_saved_http_proxy:-}" ]; then export HTTP_PROXY="$__nb_webui_saved_http_proxy"; export http_proxy="$__nb_webui_saved_http_proxy"; fi\n'
        '  if [ -n "${__nb_webui_saved_https_proxy:-}" ]; then export HTTPS_PROXY="$__nb_webui_saved_https_proxy"; export https_proxy="$__nb_webui_saved_https_proxy"; fi\n'
        '  if [ -n "${__nb_webui_saved_all_proxy:-}" ]; then export ALL_PROXY="$__nb_webui_saved_all_proxy"; export all_proxy="$__nb_webui_saved_all_proxy"; fi\n'
        '  if [ -n "${__nb_webui_saved_no_proxy:-}" ]; then export NO_PROXY="$__nb_webui_saved_no_proxy"; export no_proxy="$__nb_webui_saved_no_proxy"; fi\n'
        '  "$__nb_webui_python" -m playwright "$@"\n'
        "}\n"
    )


def _wrap_shell_command(command: str) -> str:
    stripped = command.rstrip("\r\n")
    if not stripped:
        return command
    return f"{stripped}\nprintf '{SHELL_COMMAND_DONE_MARKER}%s\\n' \"$?\"\n"


def ensure_project_log_storage(project_id: str) -> LogStorage:
    log_storage = LogStorageFather.get_storage(project_id)
    if log_storage is not None:
        return log_storage

    log_storage = LogStorage(Config.process_log_destroy_seconds)
    LogStorageFather.add_storage(log_storage, project_id)
    return log_storage


async def stop_project_shell_session(project_id: str) -> bool:
    return await ProjectShellSessionManager.stop_session(project_id)


async def ensure_project_shell_session(
    project: project_service.NoneBotProjectManager,
) -> Optional[Processor]:
    project_meta = project.read()
    runtime_process = ProcessManager.get_process(project_meta.project_id)
    if runtime_process and runtime_process.refresh_runtime_state():
        return None

    existing_session = ProjectShellSessionManager.get_session(project_meta.project_id)
    if existing_session is not None:
        return existing_session

    raw_proxy_env, _ = build_project_runtime_env(project_meta, pip_safe=False)
    env, socks_proxy_disabled = build_project_runtime_env(project_meta, pip_safe=True)
    env["PYTHONUNBUFFERED"] = "1"
    env.setdefault("PIP_DISABLE_PIP_VERSION_CHECK", "1")

    if sys.platform == "win32":
        args = ("cmd",)
    else:
        preferred_shell = Path("/bin/bash")
        shell = (
            str(preferred_shell)
            if preferred_shell.is_file()
            else os.environ.get("SHELL") or "/bin/sh"
        )
        args = (shell,)

    process = Processor(
        *args,
        cwd=Path(project_meta.project_dir),
        env=env,
        log_destroy_seconds=Config.process_log_destroy_seconds,
        project_id=project_meta.project_id,
        project_name=project_meta.project_name,
    )
    process.log_storage = ensure_project_log_storage(project_meta.project_id)
    await process.start()
    ProjectShellSessionManager.set_session(project_meta.project_id, process)
    bootstrap_script = _build_shell_bootstrap_script(
        Path(project_meta.project_dir), proxy_env=raw_proxy_env
    )
    await process.write_stdin(bootstrap_script.encode())

    await process.log_storage.add_log(
        CustomLog(level="INFO", message="项目终端 Shell 已连接，可直接连续输入命令。")
    )
    if socks_proxy_disabled:
        await process.log_storage.add_log(
            CustomLog(
                level="WARNING",
                message="检测到 SOCKS 代理：终端中的 pip 会临时跳过代理，playwright 等其他命令仍保留原代理环境。",
            )
        )
    return process


async def get_active_terminal_process(
    project: project_service.NoneBotProjectManager,
    *,
    create_shell: bool = False,
) -> Optional[Processor]:
    runtime_process = ProcessManager.get_process(project.project_id)
    if runtime_process and runtime_process.refresh_runtime_state():
        return runtime_process

    shell_session = ProjectShellSessionManager.get_session(project.project_id)
    if shell_session is not None:
        return shell_session

    if create_shell:
        return await ensure_project_shell_session(project)

    return None


async def execute_project_command(
    project: project_service.NoneBotProjectManager, command: str
) -> None:
    process = await get_active_terminal_process(project, create_shell=True)
    if process is None:
        raise ProcessNotRunning()
    runtime_process = ProcessManager.get_process(project.project_id)
    if (
        runtime_process is not None
        and runtime_process is process
        and runtime_process.refresh_runtime_state()
    ):
        await process.write_stdin(command.encode())
        return

    wrapped_command = _wrap_shell_command(command)
    await process.write_stdin(wrapped_command.encode())


async def run_nonebot_project(project: project_service.NoneBotProjectManager):
    project_meta = project.read()
    if not project_meta.adapters:
        raise AdapterNotFound()
    if not project_meta.drivers:
        raise DriverNotFound()

    await stop_project_shell_session(project_meta.project_id)

    project_dir = Path(project_meta.project_dir)
    env, _ = build_project_runtime_env(project_meta)

    env_file = project_dir / project_meta.use_env
    env_data = dotenv_values(env_file) if env_file.exists() else {}
    configured_host = str(env_data.get("HOST", "")).strip()
    configured_port = project_service.parse_project_port(env_data.get("PORT"))
    reserved_ports = project_service.get_project_port_usage(
        exclude_project_id=project_meta.project_id
    )
    configured_port_available = (
        configured_port > 0
        and configured_port not in reserved_ports
        and _is_port_available(configured_port)
    )
    run_port = (
        configured_port
        if configured_port_available
        else _pick_available_port(project_meta.project_id)
    )
    if run_port:
        env["PORT"] = str(run_port)
        project.write_to_env(project_meta.use_env, "PORT", str(run_port))
    host = configured_host or "0.0.0.0"
    env["HOST"] = host
    if not configured_host:
        project.write_to_env(project_meta.use_env, "HOST", host)

    process = ProcessManager.get_process(project_meta.project_id)
    if process:
        if process.refresh_runtime_state():
            raise ProcessAlreadyRunning()
        else:
            await process.start()
    else:
        python_path = project.config_manager.python_path
        if python_path is None:
            python_path = await get_default_python()

        raw_adapters = project_meta.adapters
        adapters: List[CliSimpleInfo] = list()
        for adapter in raw_adapters:
            adapters.append(
                CliSimpleInfo(name=adapter.name, module_name=adapter.module_name)
            )
        run_script = await generate_run_script(
            adapters=adapters,
            builtin_plugins=project_meta.builtin_plugins,
        )

        log_destroy_time = Config.process_log_destroy_seconds
        if project_meta.use_run_script:
            run_script_file = project_dir / project_meta.run_script_name
            if not run_script_file.exists():
                run_script_file.write_text(run_script, encoding="utf-8")

            process = Processor(
                python_path,
                run_script_file,
                cwd=project_dir,
                env=env,
                log_destroy_seconds=log_destroy_time,
                project_id=project_meta.project_id,
                project_name=project_meta.project_name,
            )
        else:
            process = Processor(
                python_path,
                "-c",
                run_script,
                cwd=project_dir,
                env=env,
                log_destroy_seconds=log_destroy_time,
                project_id=project_meta.project_id,
                project_name=project_meta.project_name,
            )

        process.log_storage = ensure_project_log_storage(project_meta.project_id)
        await process.start()
        ProcessManager.add_process(process, project_meta.project_id)


async def restart_nonebot_project_if_running(
    project: project_service.NoneBotProjectManager,
) -> bool:
    process = ProcessManager.get_process(project.project_id)
    if not process or not process.refresh_runtime_state():
        return False

    await process.stop()
    await run_nonebot_project(project)
    return True
