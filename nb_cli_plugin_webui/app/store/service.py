import re
import asyncio
from typing import Union, Annotated

from pydantic import Field
from nb_cli.handlers import call_pip_uninstall

from nb_cli_plugin_webui.app.config import Config
from nb_cli_plugin_webui.app.models.types import ModuleType
from nb_cli_plugin_webui.app.handlers import call_pip_install
from nb_cli_plugin_webui.app.models.store import Plugin, ModuleInfo
from nb_cli_plugin_webui.app.project import service as project_service
from nb_cli_plugin_webui.app.process.service import run_nonebot_project
from nb_cli_plugin_webui.app.utils.string_utils import generate_complexity_string
from nb_cli_plugin_webui.app.project.exceptions import WriteNoneBotProjectProfileFailed
from nb_cli_plugin_webui.app.handlers.process import (
    CustomLog,
    LogStorage,
    LogStorageFather,
    ProcessManager,
    ProcessFuncWithLog,
)

from .exception import (
    ModuleNotFound,
    ModuleIsExisted,
    ModuleTypeNotFound,
    ProjectIsRunning,
)


def _ensure_project_is_stopped(project: project_service.NoneBotProjectManager) -> None:
    process = ProcessManager.get_process(project.project_id)
    if process and process.process_is_running:
        raise ProjectIsRunning()


def install_nonebot_module(
    project: project_service.NoneBotProjectManager,
    env: str,
    module: Annotated[Union[ModuleInfo, Plugin], Field(discriminator="module_type")],
) -> str:
    running_process = ProcessManager.get_process(project.project_id)
    should_restart_after_install = bool(
        running_process and running_process.process_is_running
    )
    project_meta = project.read()
    if isinstance(module, Plugin):
        for plugin in project_meta.plugins:
            if module.module_name == plugin.module_name:
                raise ModuleIsExisted()
    elif isinstance(module, ModuleInfo):
        for adapter in project_meta.adapters:
            if module.module_name == adapter.module_name:
                raise ModuleIsExisted()
        for driver in project_meta.drivers:
            if module.module_name == driver.module_name:
                raise ModuleIsExisted()

    if module.module_type == ModuleType.MODULE:
        module_type = "driver"
        if "~" not in module.module_name:
            pattern = r"nonebot-(.*?)-"
            _match = re.search(pattern, module.project_link)
            if _match is None:
                raise ModuleTypeNotFound()
            module_type = _match.group(1)
    else:
        module_type = module.module_type

    log = LogStorage(Config.process_log_destroy_seconds)
    log_key = generate_complexity_string(8)
    LogStorageFather.add_storage(log, log_key)

    process = ProcessFuncWithLog(log)
    process.add(asyncio.sleep, 1)
    process.add(log.add_log, CustomLog(message="Processing at 3s..."))
    process.add(asyncio.sleep, 3)
    process.add(
        log.add_log, CustomLog(message=f"Install module name: {module.module_name}")
    )
    if should_restart_after_install:
        process.add(
            log.add_log,
            CustomLog(message="实例当前正在运行，将先停止实例，安装完成后再自动启动。"),
        )

    async def stop_project_if_needed():
        if not should_restart_after_install:
            return True

        running_process = ProcessManager.get_process(project.project_id)
        if running_process and running_process.process_is_running:
            await log.add_log(CustomLog(message="正在停止实例..."))
            await running_process.stop()
            await log.add_log(CustomLog(message="实例已停止，开始安装模块。"))
        return True

    process.add(stop_project_if_needed)

    async def install_module():
        proc, _ = await call_pip_install(
            module.project_link,
            ["-i", project_meta.mirror_url],
            log_storage=log,
            python_path=project.config_manager.python_path,
            project_meta=project_meta,
        )
        return_code = await proc.wait()
        if return_code != 0:
            raise RuntimeError(
                f"Install failed for {module.project_link} (exit code: {return_code})."
            )
        return True

    process.add(install_module)

    async def write_to_project_profile():
        if module_type == "plugin" and isinstance(module, Plugin):
            await project.add_plugin(module)
        elif module_type == "adapter":
            project.add_adapter(module)
        elif module_type == "driver":
            project.add_driver(env, module)
        return True

    process.add(write_to_project_profile)

    async def restart_project_if_needed():
        if not should_restart_after_install:
            return True

        await log.add_log(CustomLog(message="安装完成，正在重新启动实例以加载新模块..."))
        await run_nonebot_project(project)
        await log.add_log(CustomLog(message="实例已重新启动。"))
        return True

    process.add(restart_project_if_needed)
    process.add(log.add_log, CustomLog(message="✨ Done!"))
    process.done()

    return log_key


async def uninstall_nonebot_module(
    project: project_service.NoneBotProjectManager,
    env: str,
    module: Annotated[Union[ModuleInfo, Plugin], Field(discriminator="module_type")],
) -> None:
    _ensure_project_is_stopped(project)
    if isinstance(module, Plugin):
        for plugin in project.read().plugins:
            if module.module_name == plugin.module_name:
                break
        else:
            raise ModuleNotFound()
    elif isinstance(module, ModuleInfo):
        for adapter in project.read().adapters:
            if module.module_name == adapter.module_name:
                break
        else:
            for driver in project.read().drivers:
                if module.module_name == driver.module_name:
                    break
            else:
                raise ModuleNotFound()

    async def _call_pip_uninstall(package) -> None:
        proc = await call_pip_uninstall(
            package,
            ["-y"],
            python_path=project.config_manager.python_path,
            stdout=asyncio.subprocess.PIPE,
        )
        await proc.wait()

    project_meta = project.read()
    package: str = module.project_link
    if package.startswith("nonebot2[") and package.endswith("]"):
        package = package[9:-1]

    onebot_adapter_prefix = "nonebot.adapters.onebot"
    if module.module_name.startswith(onebot_adapter_prefix):
        onebot_adapter_count = int()
        for adapter in project_meta.adapters:
            if adapter.module_name.startswith(onebot_adapter_prefix):
                onebot_adapter_count += 1

        if onebot_adapter_count == 1:
            await _call_pip_uninstall(package)
    else:
        await _call_pip_uninstall(package)

    module_type = None
    pattern = r"nonebot-(.*?)-"
    _match = re.search(pattern, package)
    if _match:
        module_type = _match.group(1)

    pattern = r"~(.*?)"
    _match = re.search(pattern, module.module_name)
    if _match:
        module_type = "driver"

    if module_type is None:
        raise ModuleTypeNotFound()

    try:
        if module_type == "plugin" and isinstance(module, Plugin):
            project.remove_plugin(module)
        elif module_type == "adapter":
            project.remove_adapter(module)
        elif module_type == "driver":
            project.remove_driver(env, module)
    except Exception:
        raise WriteNoneBotProjectProfileFailed()
