from typing import Dict, List, Callable, Optional, Awaitable

from fastapi.websockets import WebSocketState
import asyncio
from fastapi import Depends, APIRouter, WebSocket, HTTPException, status

from nb_cli_plugin_webui.app.config import Config
from nb_cli_plugin_webui.app.logging import logger
from nb_cli_plugin_webui.app.schemas import GenericResponse
from nb_cli_plugin_webui.app.auth.utils import websocket_auth
from nb_cli_plugin_webui.app.handlers.process.schemas import CustomLog
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
    ensure_project_runtime_log_storage,
    ensure_project_shell_log_storage,
    ensure_project_shell_session,
    get_active_terminal_process,
    get_project_runtime_log_key,
    get_project_shell_log_key,
)
from .exceptions import DriverNotFound, AdapterNotFound

router = APIRouter(tags=["process"])
log_listeners: Dict[WebSocket, Callable[[ProcessLog], Awaitable[None]]] = dict()
project_run_tasks: Dict[str, asyncio.Task] = {}


def is_project_starting(project_id: str) -> bool:
    task = project_run_tasks.get(project_id)
    return bool(task and not task.done())


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

    running_task = project_run_tasks.get(project_meta.project_id)
    if running_task and not running_task.done():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Project is already starting.",
        )

    log_storage = ensure_project_runtime_log_storage(project_meta.project_id)
    log_storage.logs.clear()

    async def _run_in_background() -> None:
        try:
            await run_nonebot_project(project)
        except asyncio.CancelledError:
            await log_storage.add_log(
                CustomLog(level="WARNING", message="实例启动已取消。")
            )
            raise
        except HTTPException as err:
            logger.warning(
                f"Background start rejected for project {project_meta.project_id}: {err.detail}"
            )
            await log_storage.add_log(
                CustomLog(level="ERROR", message=f"实例启动失败：{err.detail}")
            )
        except Exception:
            logger.exception(f"Failed to start project {project_meta.project_id}.")
            await log_storage.add_log(
                CustomLog(level="ERROR", message="实例启动失败，请查看最近日志定位原因。")
            )
        finally:
            project_run_tasks.pop(project_meta.project_id, None)

    project_run_tasks[project_meta.project_id] = asyncio.create_task(_run_in_background())
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
        pending_task = project_run_tasks.get(project.project_id)
        if pending_task and not pending_task.done():
            pending_task.cancel()
            project_run_tasks.pop(project.project_id, None)
            log_storage = ensure_project_runtime_log_storage(project.project_id)
            await log_storage.add_log(
                CustomLog(level="WARNING", message="已取消尚未完成的实例启动任务。")
            )
            return GenericResponse(detail="success")
        raise ProcessNotRunning()
    await process.stop()
    project_run_tasks.pop(project.project_id, None)
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
    - 为实例创建常驻 Shell 终端会话，可与运行中的机器人并存
    """
    await ensure_project_shell_session(project)
    return GenericResponse(detail="success")


@router.get("/terminal/log-key", response_model=GenericResponse[str])
async def get_terminal_log_key(
    project: NoneBotProjectManager = Depends(get_nonebot_project_manager),
) -> GenericResponse[str]:
    """
    - 获取实例维护 Shell 对应的日志 key
    """
    ensure_project_shell_log_storage(project.project_id)
    return GenericResponse(detail=get_project_shell_log_key(project.project_id))


@router.get("/runtime/log-key", response_model=GenericResponse[str])
async def get_runtime_log_key(
    project: NoneBotProjectManager = Depends(get_nonebot_project_manager),
) -> GenericResponse[str]:
    """
    - 获取实例运行日志对应的日志 key
    """
    ensure_project_runtime_log_storage(project.project_id)
    return GenericResponse(detail=get_project_runtime_log_key(project.project_id))


@router.post("/execute", response_model=GenericResponse[str])
async def execute_command(
    command: str,
    project: NoneBotProjectManager = Depends(get_nonebot_project_manager),
) -> GenericResponse[str]:
    """
    - 在实例目录中的独立 Shell 中执行一次命令，适用于手动安装依赖或排障
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
    log_id: str, log_count: Optional[str] = None
) -> GenericResponse[List[ProcessLog]]:
    """
    - 获取历史进程日志
    """
    log_storage = LogStorageFather.get_storage(log_id)
    if log_storage is None:
        return GenericResponse(detail=[])

    normalized_count = 200
    raw_log_count = str(log_count or "").strip()
    if raw_log_count:
        try:
            normalized_count = max(1, int(raw_log_count))
        except ValueError:
            normalized_count = 200

    result = log_storage.get_logs(count=normalized_count)
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
