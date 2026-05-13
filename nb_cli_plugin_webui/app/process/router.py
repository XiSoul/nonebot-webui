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
    list_project_shell_sessions,
    ensure_project_log_storage,
    ensure_project_runtime_log_storage,
    ensure_project_shell_log_storage,
    ensure_project_shell_session,
    ProjectShellSessionManager,
    get_active_terminal_process,
    get_runtime_process,
    get_project_runtime_log_key,
    get_project_shell_log_key,
    resize_project_shell_session,
)
from .exceptions import DriverNotFound, AdapterNotFound
from .schemas import TerminalSessionInfo

router = APIRouter(tags=["process"])
log_listeners: Dict[WebSocket, Callable[[ProcessLog], Awaitable[None]]] = dict()
project_run_tasks: Dict[str, asyncio.Task] = {}


def _model_to_dict(model: object) -> dict:
    if hasattr(model, "model_dump"):
        return model.model_dump()  # type: ignore[no-any-return]
    if hasattr(model, "dict"):
        return model.dict()  # type: ignore[no-any-return]
    return dict(model) if isinstance(model, dict) else {}


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
    - 向 NoneBot 实例发送中断信号，优先执行优雅退出
    """
    process = get_runtime_process(project)
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

    await process.interrupt()
    for _ in range(20):
        if not process.refresh_runtime_state():
            break
        await asyncio.sleep(0.1)

    if process.refresh_runtime_state():
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
    session = await ensure_project_shell_session(project)
    return GenericResponse(detail=session.session_id if session else "")


@router.get("/terminal/sessions", response_model=GenericResponse[List[TerminalSessionInfo]])
async def get_terminal_sessions(
    project: NoneBotProjectManager = Depends(get_nonebot_project_manager),
) -> GenericResponse[List[TerminalSessionInfo]]:
    """
    - 获取实例维护终端会话列表
    """
    logger.info(f"Terminal sessions requested for project {project.project_id}")
    return GenericResponse(detail=list_project_shell_sessions(project.project_id))


@router.post("/terminal/session/create", response_model=GenericResponse[TerminalSessionInfo])
async def create_terminal_session(
    project: NoneBotProjectManager = Depends(get_nonebot_project_manager),
) -> GenericResponse[TerminalSessionInfo]:
    """
    - 创建新的维护终端会话
    """
    session = await ensure_project_shell_session(project, create_new=True)
    if session is None:
        raise ProcessNotRunning()

    exported = next(
        (
            item
            for item in list_project_shell_sessions(project.project_id)
            if item.session_id == session.session_id
        ),
        None,
    )
    if exported is None:
        raise ProcessNotRunning()
    return GenericResponse(detail=exported)


@router.post("/terminal/session/switch", response_model=GenericResponse[str])
async def switch_terminal_session(
    session_id: str,
    project: NoneBotProjectManager = Depends(get_nonebot_project_manager),
) -> GenericResponse[str]:
    """
    - 切换当前维护终端活动会话
    """
    switched = ProjectShellSessionManager.set_active_session(
        project.project_id, session_id
    )
    if not switched:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Session not found."
        )
    return GenericResponse(detail="success")


@router.delete("/terminal/session/delete", response_model=GenericResponse[str])
async def delete_terminal_session(
    session_id: str,
    project: NoneBotProjectManager = Depends(get_nonebot_project_manager),
) -> GenericResponse[str]:
    """
    - 关闭指定维护终端会话
    """
    deleted = await ProjectShellSessionManager.stop_session(
        project.project_id, session_id=session_id
    )
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Session not found."
        )
    return GenericResponse(detail="success")


@router.get("/terminal/log-key", response_model=GenericResponse[str])
async def get_terminal_log_key(
    session_id: Optional[str] = None,
    project: NoneBotProjectManager = Depends(get_nonebot_project_manager),
) -> GenericResponse[str]:
    """
    - 获取实例维护 Shell 对应的日志 key
    """
    if session_id:
        session = await ensure_project_shell_session(project, session_id=session_id)
        if session is None:
            raise ProcessNotRunning()
        return GenericResponse(
            detail=get_project_shell_log_key(project.project_id, session_id=session.session_id)
        )

    ensure_project_shell_log_storage(project.project_id)
    active_session_id = ProjectShellSessionManager.get_active_session_id(project.project_id)
    if active_session_id:
        return GenericResponse(
            detail=get_project_shell_log_key(project.project_id, session_id=active_session_id)
        )
    return GenericResponse(detail=get_project_shell_log_key(project.project_id))


@router.post("/terminal/resize", response_model=GenericResponse[str])
async def resize_terminal(
    cols: int,
    rows: int,
    session_id: Optional[str] = None,
    project: NoneBotProjectManager = Depends(get_nonebot_project_manager),
) -> GenericResponse[str]:
    """
    - 调整实例维护终端的窗口尺寸
    """
    resized = await resize_project_shell_session(
        project, cols=cols, rows=rows, session_id=session_id
    )
    if not resized:
        session = await ensure_project_shell_session(project, session_id=session_id)
        if session is not None:
            await resize_project_shell_session(
                project,
                cols=cols,
                rows=rows,
                session_id=session.session_id,
            )
    return GenericResponse(detail="success")


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
    session_id: Optional[str] = None,
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
        await execute_project_command(project, stripped, session_id=session_id)
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


@router.websocket("/terminal/ws")
async def project_terminal_socket(
    websocket: WebSocket,
):
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

    session = None
    session_listener_registered = False

    async def publish_log(log: ProcessLog):
        await websocket.send_json({"type": "output", "data": log.message})

    async def attach_session(project_id: str, session_id: Optional[str], create_new: bool = False):
        nonlocal session, session_listener_registered
        if session is not None and session_listener_registered:
            try:
                session.process.log_storage.unregister_listener(publish_log)
            except Exception:
                pass
            session_listener_registered = False

        project = get_nonebot_project_manager(project_id)
        session = await ensure_project_shell_session(
            project, session_id=session_id, create_new=create_new
        )
        if session is None:
            return None

        ProjectShellSessionManager.set_active_session(project_id, session.session_id)
        session.process.log_storage.register_listener(publish_log)
        session_listener_registered = True
        await websocket.send_json(
            {
                "type": "ready",
                "session_id": session.session_id,
                "sessions": [_model_to_dict(item) for item in list_project_shell_sessions(project_id)],
            }
        )
        history = session.process.log_storage.get_logs(count=200)
        for item in history:
            await websocket.send_json({"type": "output", "data": item.message})
        return session

    try:
        while websocket.client_state == WebSocketState.CONNECTED:
            recv = await websocket.receive_json()
            message_type = recv.get("type")
            project_id = str(recv.get("project_id") or "").strip()
            requested_session_id = str(recv.get("session_id") or "").strip() or None

            if message_type == "attach":
                if not project_id:
                    continue
                await attach_session(project_id, requested_session_id)
                continue

            if message_type == "create":
                if not project_id:
                    continue
                await attach_session(project_id, None, create_new=True)
                continue

            if message_type == "switch":
                if not project_id or not requested_session_id:
                    continue
                await attach_session(project_id, requested_session_id)
                continue

            if message_type == "close":
                if not project_id or not requested_session_id:
                    continue
                deleted = await ProjectShellSessionManager.stop_session(
                    project_id, session_id=requested_session_id
                )
                if deleted:
                    active_session_id = ProjectShellSessionManager.get_active_session_id(
                        project_id
                    )
                    await websocket.send_json(
                        {
                            "type": "sessions",
                            "session_id": active_session_id,
                            "sessions": [
                                _model_to_dict(item)
                                for item in list_project_shell_sessions(project_id)
                            ],
                        }
                    )
                    if active_session_id:
                        await attach_session(project_id, active_session_id)
                    else:
                        session = None
                continue

            if message_type == "list":
                if not project_id:
                    continue
                await websocket.send_json(
                    {
                        "type": "sessions",
                        "session_id": ProjectShellSessionManager.get_active_session_id(
                            project_id
                        ),
                        "sessions": [
                            _model_to_dict(item)
                            for item in list_project_shell_sessions(project_id)
                        ],
                    }
                )
                continue

            if message_type == "input":
                if session is None:
                    continue
                data = str(recv.get("data") or "")
                if data:
                    await session.process.write_stdin(data.encode())
                continue

            if message_type == "resize":
                if not project_id:
                    continue
                project = get_nonebot_project_manager(project_id)
                cols = int(recv.get("cols") or 0)
                rows = int(recv.get("rows") or 0)
                await resize_project_shell_session(
                    project,
                    cols=cols,
                    rows=rows,
                    session_id=requested_session_id or (session.session_id if session else None),
                )
                continue

            if message_type == "interrupt":
                if session is None:
                    continue
                await session.process.interrupt()
    except Exception as err:
        logger.debug(f"Project Terminal: websocket exception {err=}")
    finally:
        if session is not None and session_listener_registered:
            try:
                session.process.log_storage.unregister_listener(publish_log)
            except Exception:
                pass
