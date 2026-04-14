import os
import sys
import socket
from typing import List
from pathlib import Path

from dotenv import dotenv_values
from nb_cli.config import SimpleInfo as CliSimpleInfo
from nb_cli.handlers import get_default_python, generate_run_script

from nb_cli_plugin_webui.app.config import Config
from nb_cli_plugin_webui.app.project import service as project_service
from nb_cli_plugin_webui.app.handlers.process import (
    Processor,
    ProcessManager,
    LogStorageFather,
    ProcessAlreadyRunning,
)
from nb_cli_plugin_webui.app.utils.bot_proxy import get_bot_proxy_env

from .exceptions import DriverNotFound, AdapterNotFound


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


async def run_nonebot_project(project: project_service.NoneBotProjectManager):
    project_meta = project.read()
    if not project_meta.adapters:
        raise AdapterNotFound()
    if not project_meta.drivers:
        raise DriverNotFound()

    project_dir = Path(project_meta.project_dir)
    env = get_bot_proxy_env(os.environ.copy(), project_meta=project_meta)

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

    env["TERM"] = "xterm-color"
    if sys.platform == "win32":
        venv_path = project_dir / Path(".venv/Scripts")
        env["PATH"] = f"{venv_path.absolute()};{env['PATH']}"
    else:
        venv_path = project_dir / Path(".venv/bin")
        env["PATH"] = f"{venv_path.absolute()}:{env['PATH']}"

    process = ProcessManager.get_process(project_meta.project_id)
    if process:
        if process.process_is_running:
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

        await process.start()
        LogStorageFather.add_storage(process.log_storage, project_meta.project_id)
        ProcessManager.add_process(process, project_meta.project_id)


async def restart_nonebot_project_if_running(
    project: project_service.NoneBotProjectManager,
) -> bool:
    process = ProcessManager.get_process(project.project_id)
    if not process or not process.process_is_running:
        return False

    await process.stop()
    await run_nonebot_project(project)
    return True
