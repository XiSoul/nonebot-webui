import json
import asyncio
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from cookiecutter.exceptions import OutputDirExistsException
from dotenv import set_key, dotenv_values

from nb_cli.config import ConfigManager
from nb_cli.cli.commands.project import ProjectContext
from nb_cli.handlers import create_project, create_virtualenv

from nb_cli_plugin_webui.app.config import Config
from nb_cli_plugin_webui.app.models.types import ModuleType
from nb_cli_plugin_webui.app.store.dependencies import get_store_items
from nb_cli_plugin_webui.app.models.base import ModuleInfo, NoneBotProjectMeta
from nb_cli_plugin_webui.app.utils.string_utils import generate_complexity_string
from nb_cli_plugin_webui.app.handlers import NoneBotProjectManager, call_pip_install
from nb_cli_plugin_webui.app.handlers.process import (
    CustomLog,
    LogStorage,
    ProcessManager,
    LogStorageFather,
    ProcessFuncWithLog,
)

from .exceptions import (
    ProjectDirectoryAlreadyExists,
    ProjectDirIsNotDir,
    ProjectNameAlreadyExists,
    ProjectPortAlreadyExists,
)
from .schemas import AddProjectData, CreateProjectData


def _driver_sort_key(driver: ModuleInfo) -> int:
    value = f"{driver.module_name} {driver.project_link} {driver.name}".lower()
    if "httpx" in value or "websocket" in value:
        return 10
    return 0


def _can_reset_project_dir(project_dir: Path, base_project_dir: Path) -> bool:
    try:
        project_dir.resolve().relative_to(base_project_dir.resolve())
    except ValueError:
        return False
    return project_dir.exists() and project_dir != base_project_dir


def _reset_failed_project_dir(project_dir: Path, base_project_dir: Path) -> bool:
    if not _can_reset_project_dir(project_dir, base_project_dir):
        return False

    shutil.rmtree(project_dir)
    return True


def normalize_project_name(project_name: str) -> str:
    return project_name.strip().replace(" ", "-")


def _normalize_project_name_key(project_name: str) -> str:
    return normalize_project_name(project_name).casefold()


def normalize_project_dir(project_dir: Path) -> str:
    return str(project_dir.expanduser().resolve()).casefold()


def parse_project_port(value: Any) -> int:
    try:
        port = int(str(value).strip())
    except Exception:
        return 0
    return port if 1024 <= port <= 65535 else 0


def _get_project_map() -> Dict[str, NoneBotProjectMeta]:
    try:
        return NoneBotProjectManager.get_project()
    except Exception:
        return {}


def ensure_project_name_is_unique(
    project_name: str, *, exclude_project_id: Optional[str] = None
) -> None:
    normalized_name = _normalize_project_name_key(project_name)
    if not normalized_name:
        return

    for current_project_id, meta in _get_project_map().items():
        if current_project_id == exclude_project_id:
            continue
        if _normalize_project_name_key(meta.project_name) == normalized_name:
            raise ProjectNameAlreadyExists(normalize_project_name(project_name))


def ensure_project_dir_is_unique(
    project_dir: Path, *, exclude_project_id: Optional[str] = None
) -> None:
    normalized_project_dir = normalize_project_dir(project_dir)
    for current_project_id, meta in _get_project_map().items():
        if current_project_id == exclude_project_id:
            continue
        if normalize_project_dir(Path(meta.project_dir)) == normalized_project_dir:
            raise ProjectDirectoryAlreadyExists(str(project_dir), meta.project_name)


def resolve_project_use_env(project_dir: Path) -> str:
    base_env = project_dir / ".env"
    if not base_env.is_file():
        return ".env"

    env_name = str(dotenv_values(base_env).get("ENVIRONMENT", "")).strip()
    if not env_name:
        return ".env"

    env_file_name = f".env.{env_name}"
    if (project_dir / env_file_name).is_file():
        return env_file_name
    return ".env"


def get_project_env_port(project_dir: Path, env_name: str) -> int:
    env_path = project_dir / env_name
    if not env_path.is_file():
        return 0
    return parse_project_port(dotenv_values(env_path).get("PORT"))


def get_project_port_usage(
    *, exclude_project_id: Optional[str] = None
) -> Dict[int, Tuple[str, str]]:
    result: Dict[int, Tuple[str, str]] = {}
    for current_project_id, meta in _get_project_map().items():
        if current_project_id == exclude_project_id:
            continue

        project_dir = Path(meta.project_dir)
        if not project_dir.exists():
            continue

        env_name = getattr(meta, "use_env", "") or resolve_project_use_env(project_dir)
        port = get_project_env_port(project_dir, env_name)
        if port:
            result.setdefault(port, (current_project_id, meta.project_name))
    return result


def ensure_project_port_is_unique(
    port: int, *, exclude_project_id: Optional[str] = None
) -> None:
    if port <= 0:
        return
    used_ports = get_project_port_usage(exclude_project_id=exclude_project_id)
    conflict = used_ports.get(port)
    if conflict:
        _, project_name = conflict
        raise ProjectPortAlreadyExists(port, project_name)


def create_nonebot_project(data: CreateProjectData) -> str:
    project_name = normalize_project_name(data.project_name)
    ensure_project_name_is_unique(project_name)
    base_project_dir = Path(Config.base_dir) / Path(data.project_dir)
    base_project_dir.mkdir(parents=True, exist_ok=True)
    project_dir = base_project_dir / project_name
    ensure_project_dir_is_unique(project_dir)
    sorted_drivers = sorted(data.drivers, key=_driver_sort_key)
    drivers = [driver.project_link for driver in sorted_drivers]
    adapters = [adapter.project_link for adapter in data.adapters]

    context = ProjectContext()
    context.variables["project_name"] = project_name
    context.variables["drivers"] = json.dumps(
        {driver.project_link: driver.dict() for driver in sorted_drivers}
    )
    context.packages.extend(drivers)
    context.variables["adapters"] = json.dumps(
        {adapter.project_link: adapter.dict() for adapter in data.adapters}
    )
    context.packages.extend(adapters)

    plugin_dirs = list()
    if not data.is_bootstrap:
        context.variables["use_src"] = data.use_src
        if data.use_src:
            plugin_dirs.append("src/plugins")
        else:
            plugin_dirs.append(f"{project_name}/plugins")

    config_manager = ConfigManager(working_dir=project_dir, use_venv=True)

    log = LogStorage(Config.process_log_destroy_seconds)
    log_key = generate_complexity_string(10)
    LogStorageFather.add_storage(log, log_key)

    process = ProcessFuncWithLog(log)
    process.add(asyncio.sleep, 1)
    process.add(log.add_log, CustomLog(message="Processing at 3s..."))
    process.add(asyncio.sleep, 3)
    process.add(log.add_log, CustomLog(message=f"Project name: {project_name}"))
    process.add(log.add_log, CustomLog(message=f"Project dir: {project_dir}"))
    process.add(log.add_log, CustomLog(message=f"Mirror url: {data.mirror_url}"))
    process.add(
        log.add_log, CustomLog(message=f"Project drivers: {', '.join(drivers)}")
    )
    process.add(
        log.add_log, CustomLog(message=f"Project adapters: {', '.join(adapters)}")
    )

    process.add(log.add_log, CustomLog(message="Generate NoneBot project..."))
    async def generate_project():
        try:
            await asyncio.to_thread(
                create_project,
                "bootstrap" if data.is_bootstrap else "simple",
                {"nonebot": context.variables},
                str(base_project_dir.absolute()),
            )
        except OutputDirExistsException:
            # Retry flow: keep going when the previous failed run already generated files.
            if (project_dir / "pyproject.toml").is_file():
                await log.add_log(
                    CustomLog(message=f"Project directory exists, reuse: {project_dir}")
                )
                return True
            if _reset_failed_project_dir(project_dir, base_project_dir):
                await log.add_log(
                    CustomLog(
                        message=f"Found incomplete project directory, cleaned and retry: {project_dir}"
                    )
                )
                await asyncio.to_thread(
                    create_project,
                    "bootstrap" if data.is_bootstrap else "simple",
                    {"nonebot": context.variables},
                    str(base_project_dir.absolute()),
                )
                return True
            raise
        return True

    process.add(generate_project)
    process.add(log.add_log, CustomLog(message="Finished generate."))

    process.add(log.add_log, CustomLog(message="Initialization dependencies..."))
    process.add(
        create_virtualenv, project_dir / ".venv", prompt=project_name, python_path=None
    )
    process.add(log.add_log, CustomLog(message="Finished initialization."))

    process.add(log.add_log, CustomLog(message="Install dependencies..."))

    async def install_dependencies():
        proc, _ = await call_pip_install(
            ["nonebot2", *context.packages],
            ["-i", data.mirror_url],
            python_path=config_manager.python_path,
            log_storage=log,
        )
        await proc.wait()
        return True

    process.add(install_dependencies)
    process.add(log.add_log, CustomLog(message="Finished install."))

    async def add_project_info():
        _adapters: List[ModuleInfo] = [
            ModuleInfo.parse_obj(adapter.dict()) for adapter in data.adapters
        ]
        _drivers: List[ModuleInfo] = [
            ModuleInfo.parse_obj(driver.dict()) for driver in sorted_drivers
        ]

        project_id = generate_complexity_string(6)
        manager = NoneBotProjectManager(project_id=project_id)
        env_file = project_dir / ".env"
        if not env_file.exists():
            env_file.write_text(str(), encoding="utf-8")
        set_key(
            env_file,
            "DRIVER",
            manager._build_driver_expr([driver.module_name for driver in _drivers]),
        )
        await manager.add_project(
            project_name=project_name,
            project_dir=project_dir,
            mirror_url=data.mirror_url,
            adapters=_adapters,
            drivers=_drivers,
            plugin_dirs=plugin_dirs,
        )

        manager.write_to_env(".env", "ENVIRONMENT", "prod")
        return True

    process.add(add_project_info)
    process.add(log.add_log, CustomLog(message="✨ Done!"))
    process.done()

    asyncio.get_event_loop().call_later(600, LogStorageFather.remove_storage, log_key)

    return log_key


async def add_nonebot_project(data: AddProjectData) -> str:
    project_name = normalize_project_name(data.project_name)
    ensure_project_name_is_unique(project_name)
    project_dir = Path(data.project_dir)
    if not project_dir.is_dir():
        raise ProjectDirIsNotDir()
    ensure_project_dir_is_unique(project_dir)

    current_env = resolve_project_use_env(project_dir)
    configured_port = get_project_env_port(project_dir, current_env)
    ensure_project_port_is_unique(configured_port)

    store_plugin_data = get_store_items(ModuleType.PLUGIN, is_search=False)
    store_adapter_data = get_store_items(ModuleType.ADAPTER, is_search=False)

    installed_plugins = list()
    for plugin in store_plugin_data:
        if plugin.module_name in data.plugins:
            installed_plugins.append(plugin)

    installed_adapters = list()
    for adapter in store_adapter_data:
        if adapter.module_name in data.adapters:
            installed_adapters.append(adapter)

    context = ProjectContext()
    context.variables["project_name"] = project_name
    context.variables["adapters"] = json.dumps(
        {adapter.project_link: adapter.dict() for adapter in installed_adapters}
    )
    context.packages.extend([adapter.project_link for adapter in installed_adapters])

    config_manager = ConfigManager(working_dir=project_dir, use_venv=True)

    log = LogStorage(Config.process_log_destroy_seconds)
    log_key = generate_complexity_string(10)
    LogStorageFather.add_storage(log, log_key)

    process = ProcessFuncWithLog(log)
    process.add(asyncio.sleep, 1)
    process.add(log.add_log, CustomLog(message="Processing at 3s..."))
    process.add(asyncio.sleep, 3)
    process.add(log.add_log, CustomLog(message=f"Project name: {project_name}"))
    process.add(log.add_log, CustomLog(message=f"Project dir: {project_dir}"))
    process.add(log.add_log, CustomLog(message=f"Mirror url: {data.mirror_url}"))
    process.add(
        log.add_log, CustomLog(message=f"Project plugins: {', '.join(data.plugins)}")
    )
    process.add(
        log.add_log, CustomLog(message=f"Project adapters: {', '.join(data.adapters)}")
    )
    process.add(log.add_log, CustomLog(message=str()))

    venv_path = project_dir / ".venv"
    if not venv_path.is_dir():
        process.add(
            log.add_log,
            CustomLog(message=f"Not found virtualenv in {venv_path.absolute()}"),
        )
        process.add(log.add_log, CustomLog(message="Initialization dependencies..."))
        process.add(
            create_virtualenv,
            project_dir / ".venv",
            prompt=project_name,
            python_path=None,
        )
    process.add(log.add_log, CustomLog(message="Finished initialization."))

    process.add(log.add_log, CustomLog(message="Install dependencies..."))

    async def install_dependencies():
        proc, _ = await call_pip_install(
            ["nonebot2", *context.packages],
            ["-i", data.mirror_url],
            python_path=config_manager.python_path,
            log_storage=log,
        )
        await proc.wait()
        return True

    process.add(install_dependencies)
    process.add(log.add_log, CustomLog(message="Finished install."))

    project_id = generate_complexity_string(6)
    manager = NoneBotProjectManager(project_id=project_id)
    await manager.add_project(
        project_name=project_name,
        project_dir=project_dir,
        mirror_url=data.mirror_url,
        adapters=installed_adapters,
        plugins=installed_plugins,
    )
    manager.read()
    for plugin in installed_plugins:
        await manager.add_plugin(plugin)

    env_path = project_dir / ".env"
    if not env_path.exists() or not env_path.is_file():
        manager.write_to_env(".env", "ENVIRONMENT", "prod")

    process.add(log.add_log, CustomLog(message="✨ Done!"))
    process.done()

    asyncio.get_event_loop().call_later(600, LogStorageFather.remove_storage, log_key)

    return log_key


def list_nonebot_project() -> Dict[str, NoneBotProjectMeta]:
    try:
        project = NoneBotProjectManager.get_project()
    except Exception:
        project = dict()

    if not project:
        return project

    processes = ProcessManager.processes
    result: Dict[str, NoneBotProjectMeta] = dict()
    for project_id in project:
        _project = project.get(project_id)
        if _project is None:
            continue

        if not Path(_project.project_dir).exists():
            npm = NoneBotProjectManager(project_id=project_id)
            npm.remove_project()
            continue

        is_running = False
        for process_id in processes:
            process = processes.get(process_id)
            if process is None:
                continue

            if _project.project_id == process_id and process.process_is_running:
                is_running = True
                break

        _project.is_running = is_running
        result[project_id] = _project

    return result
