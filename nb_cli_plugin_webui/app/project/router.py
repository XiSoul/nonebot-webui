import shutil
from pathlib import Path
from typing import List

from fastapi import Depends, APIRouter

from nb_cli_plugin_webui.app.logging import logger as log
from nb_cli_plugin_webui.app.handlers import NoneBotProjectManager
from nb_cli_plugin_webui.app.handlers.process import (
    ProcessManager,
    LogStorageFather,
)
from nb_cli_plugin_webui.app.models.base import Plugin, ModuleInfo, NoneBotProjectMeta

from .exceptions import ProjectDeleteFailed
from .config.router import router as config_router
from .dependencies import get_nonebot_project_toml, get_nonebot_project_manager
from .service import (
    add_nonebot_project,
    list_nonebot_project,
    create_nonebot_project,
    is_managed_project_dir,
)
from ..process.service import stop_project_shell_session
from ..process.service import get_project_runtime_log_key, get_project_shell_log_key
from .schemas import (
    AddProjectData,
    GenericResponse,
    CreateProjectData,
    ProjectTomlDetail,
    ListProjectResponse,
)

router = APIRouter(tags=["project"])
router.include_router(config_router, prefix="/config")


@router.post("/create", response_model=GenericResponse[str])
async def create_project(data: CreateProjectData) -> GenericResponse[str]:
    """
    - 创建 NoneBot 实例
    - 返回对应的日志密钥, 用于日志展现
    """
    result = create_nonebot_project(data)
    return GenericResponse(detail=result)


@router.post("/add", response_model=GenericResponse[str])
async def add_project(data: AddProjectData) -> GenericResponse[str]:
    """
    - 添加 NoneBot 实例
    - 返回对应的日志密钥, 用于日志展现
    """
    result = await add_nonebot_project(data)
    return GenericResponse(detail=result)


@router.get("/profile", response_model=GenericResponse[NoneBotProjectMeta])
async def get_project_profile(
    project: NoneBotProjectManager = Depends(get_nonebot_project_manager),
) -> GenericResponse[NoneBotProjectMeta]:
    """
    - 获取 NoneBot 实例的配置信息
    """
    result = project.read()
    return GenericResponse(detail=result)


@router.delete("/delete", response_model=GenericResponse[str])
async def delete_project(
    delete_fully: bool = False,
    project: NoneBotProjectManager = Depends(get_nonebot_project_manager),
) -> GenericResponse[str]:
    """
    - 删除 NoneBot 实例
    """
    data = project.read()
    process = ProcessManager.get_process(data.project_id)
    if process and process.process_is_running:
        try:
            await process.stop()
        except Exception as err:
            log.warning(f"Stop project process before delete failed: {err}")
    try:
        ProcessManager.remove_process(data.project_id)
    except Exception:
        pass
    try:
        await stop_project_shell_session(data.project_id)
    except Exception:
        pass
    try:
        LogStorageFather.remove_storage(get_project_runtime_log_key(data.project_id))
    except Exception:
        pass
    try:
        LogStorageFather.remove_storage(get_project_shell_log_key(data.project_id))
    except Exception:
        pass

    should_delete_project_dir = delete_fully and is_managed_project_dir(
        Path(data.project_dir)
    )

    if delete_fully and not should_delete_project_dir:
        log.warning(
            "Skip physical delete for external project directory: "
            f"{data.project_dir}"
        )

    if should_delete_project_dir:
        try:
            shutil.rmtree(data.project_dir)
        except OSError as err:
            log.error(f"Delete nonebot project failed: {err}")
            log.exception(err)
            raise ProjectDeleteFailed()
    project.remove_project()
    return GenericResponse(detail="success")


@router.get("/list", response_model=ListProjectResponse)
async def list_project() -> ListProjectResponse:
    """
    - 获取所有 NoneBot 实例基本信息
    """
    result = list_nonebot_project()
    return ListProjectResponse(detail=result)


@router.post("/check_toml", response_model=GenericResponse[ProjectTomlDetail])
async def check_project_toml(
    toml_data: ProjectTomlDetail = Depends(get_nonebot_project_toml),
) -> GenericResponse[ProjectTomlDetail]:
    """
    - 检查 NoneBot 实例的 toml 文件并从中获取所需信息
    """

    return GenericResponse(detail=toml_data)


@router.get("/plugins", response_model=GenericResponse[List[Plugin]])
async def get_plugins(
    project: NoneBotProjectManager = Depends(get_nonebot_project_manager),
) -> GenericResponse[List[Plugin]]:
    """
    - 获取实例的插件列表
    """
    project_metadata = project.read()
    process = ProcessManager.get_process(project_metadata.project_id)
    if process and process.refresh_runtime_state():
        await project.update_plugin_config()
        project_metadata = project.read()
    return GenericResponse(detail=project_metadata.plugins)


@router.get("/adapters", response_model=GenericResponse[List[ModuleInfo]])
async def get_adapters(
    project: NoneBotProjectManager = Depends(get_nonebot_project_manager),
) -> GenericResponse[List[ModuleInfo]]:
    """
    - 获取实例的适配器列表
    """
    project_metadata = project.read()
    return GenericResponse(detail=project_metadata.adapters)


@router.get("/drivers", response_model=GenericResponse[List[ModuleInfo]])
async def get_drivers(
    project: NoneBotProjectManager = Depends(get_nonebot_project_manager),
) -> GenericResponse[List[ModuleInfo]]:
    """
    - 获取实例的驱动器列表
    """
    project_metadata = project.read()
    return GenericResponse(detail=project_metadata.drivers)
