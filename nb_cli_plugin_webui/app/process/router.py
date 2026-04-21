from typing import Dict, List, Callable, Optional, Awaitable

from fastapi.websockets import WebSocketState
from fastapi import Depends, APIRouter, WebSocket, HTTPException, status

from nb_cli_plugin_webui.app.config import Config
from nb_cli_plugin_webui.app.logging import logger
from nb_cli_plugin_webui.app.schemas import GenericResponse
from nb_cli_plugin_webui.app.auth.utils import websocket_auth
from nb_cli_plugin_webui.app.project import (
    NoneBotProjectManager,
    get_nonebot_project_manager,
)
from nb_cli_plugin_webui.app.handlers.process import (
    LogStorage,
    LogStorageFather,
    ProcessLog,
    ProcessNotRunning,
)

from .service import (
    run_nonebot_project,
    execute_project_command,
    ensure_project_log_storage,
    ensure_project_shell_session,
    get_active_terminal_process,
)
from .exceptions import DriverNotFound, AdapterNotFound

router = APIRouter(tags=["process"])
log_listeners: Dict[WebSocket, Callable[[ProcessLog], Awaitable[None]]] = dict()


@router.post("/run", response_model=GenericResponse[str])
async def run_process(
    project: NoneBotProjectManager = Depends(get_nonebot_project_manager),
) -> GenericResponse[str]:
    """
    - 运行 NoneBot 实例
    """
    project_meta = project.read()
    if not project_meta.adapters:
        raise AdapterNotFound()
    if not project_meta.drivers:
        raise DriverNotFound()

    try:
        await run_nonebot_project(project)
    except HTTPException:
        raise
    except Exception as err:
        logger.exception(f"Failed to start project {project_meta.project_id}.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(err) or err.__class__.__name__,
        ) from err
    return GenericResponse(detail="success")


@router.post("/stop", response_model=GenericResponse[str])
async def _stop_process(
    project: NoneBotProjectManager = Depends(get_nonebot_project_manager),
) -> GenericResponse[str]:
    """
    - 终止 NoneBot 实例
    """
    process = await get_active_terminal_process(project, create_shell=False)
    if process is None:
        raise ProcessNotRunning()
    await process.stop()
    return GenericResponse(detail="success")


@router.post("/write", response_model=GenericResponse[int])
async def write_to_process(
    content: str,
    project: NoneBotProjectManager = Depends(get_nonebot_project_manager),
) -> GenericResponse[int]:
    """
    - 向当前实例活动终端写入数据
    """
    process = await get_active_terminal_process(project, create_shell=True)
    if process is None:
        raise ProcessNotRunning()

    await execute_project_command(project, content)
    return GenericResponse(detail=len(content.encode()))


@router.post("/interrupt", response_model=GenericResponse[str])
async def interrupt_process(
    project: NoneBotProjectManager = Depends(get_nonebot_project_manager),
) -> GenericResponse[str]:
    """
    - 向当前实例活动终端发送中断信号
    """
    process = await get_active_terminal_process(project, create_shell=False)
    if process is None:
        raise ProcessNotRunning()
    await process.interrupt()
    return GenericResponse(detail="success")


@router.post("/terminal/open", response_model=GenericResponse[str])
async def open_terminal(
    project: NoneBotProjectManager = Depends(get_nonebot_project_manager),
) -> GenericResponse[str]:
    """
    - 为未运行实例创建常驻 Shell 终端会话
    """
    await ensure_project_shell_session(project)
    return GenericResponse(detail="success")


@router.post("/execute", response_model=GenericResponse[str])
async def execute_command(
    command: str,
    project: NoneBotProjectManager = Depends(get_nonebot_project_manager),
) -> GenericResponse[str]:
    """
    - 在实例目录中执行一次命令, 适用于实例未运行时手动安装依赖
    """
    stripped = command.strip()
    if not stripped:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Command is empty."
        )

    try:
        await execute_project_command(project, stripped)
    except HTTPException:
        raise
    except Exception as err:
        project_meta = project.read()
        logger.exception(
            f"Failed to execute command in project {project_meta.project_id}."
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(err) or err.__class__.__name__,
        ) from err

    return GenericResponse(detail="success")


@router.get("/log/history", response_model=GenericResponse[List[ProcessLog]])
async def get_log_history(
    log_count: int, log_id: str
) -> GenericResponse[List[ProcessLog]]:
    """
    - 获取历史进程日志
    """
    log_storage = LogStorageFather.get_storage(log_id)
    if log_storage is None:
        return GenericResponse(detail=[])

    result = log_storage.get_logs(count=log_count)
    return GenericResponse(detail=result)


@router.websocket("/log/ws")
async def get_process_log(websocket: WebSocket):
    await websocket.accept()

    auth = await websocket_auth(
        websocket, secret_key=Config.secret_key.get_secret_value()
    )
    if not auth:
        try:
            await websocket.close()
        except Exception:
            pass
        return

    log_storage: Optional[LogStorage[ProcessLog]] = None

    def unregister_listener(log_storage: LogStorage[ProcessLog]):
        listener = log_listeners.get(websocket)
        if listener is not None:
            log_storage.unregister_listener(listener)
            log_listeners.pop(websocket)

    async def log_listener(log: ProcessLog):
        await websocket.send_text(log.json())

    async def receive_listener(recv: dict):
        nonlocal log_storage

        if recv.get("type") != "log":
            return

        if log_storage is not None:
            unregister_listener(log_storage)

        log_key = recv.get("log_key", str())
        if not log_key:
            return

        log_storage = ensure_project_log_storage(log_key)

        log_storage.register_listener(log_listener)
        log_listeners[websocket] = log_listener

    try:
        while websocket.client_state == WebSocketState.CONNECTED:
            recv = await websocket.receive_json()
            await receive_listener(recv)
    except Exception as err:
        logger.debug(f"Process Log: websocket exception {err=}")
    finally:
        if log_storage is not None:
            unregister_listener(log_storage)
