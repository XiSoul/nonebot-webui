import os
from pathlib import Path

from starlette.types import Send, Scope, Receive
from fastapi import FastAPI, HTTPException, status
from fastapi.security.utils import get_authorization_scheme_param
from starlette.responses import Response, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles as BaseStaticFiles
from starlette.exceptions import HTTPException as StarlettleHTTPException
from starlette.middleware.cors import CORSMiddleware

from nb_cli_plugin_webui import get_version
from nb_cli_plugin_webui.app.backup.service import configure_backup_scheduler
from nb_cli_plugin_webui.app.utils.global_log import (
    LOG_CLEANUP_JOB_ID,
    cleanup_old_logs,
)

from .config import Config
from .logging import logger as log
from .utils.security import jwt
from .auth.utils import ensure_login_token_is_active
from .utils.scheduler import scheduler
from .utils.container import (
    apply_container_runtime_config,
    maybe_auto_select_best_source_preset,
)
from .router import router as api_router
from .handlers.process import ProcessManager
from .process.service import ProjectShellSessionManager
from .handlers import driver_store_manager, plugin_store_manager, adapter_store_manager

STATIC_PATH = Path(__file__).parent.parent / "dist"
AUTH_ROUTES = ["/api", "/v1"]
PASS_PATHS = [
    "/api/v1/auth/login",
    "/api/v1/auth/verify",
    "/v1/auth/login",
    "/v1/auth/verify",
    "/api/docs",
    "/api/docs/openapi.json",
]


class StaticFiles(BaseStaticFiles):
    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "websocket":
            await send(
                {
                    "type": "websocket.close",
                    "code": status.WS_1008_POLICY_VIOLATION,
                    "reason": "WebSocket connection is forbidden.",
                }
            )
            return

        assert scope["type"] == "http"

        if not self.config_checked:
            await self.check_config()
            self.config_checked = True

        path = self.get_path(scope)
        response = await self.get_response(path, scope)
        await response(scope, receive, send)

    async def get_response(self, path: str, scope: Scope) -> Response:
        try:
            return await super().get_response(path, scope)
        except (HTTPException, StarlettleHTTPException) as err:
            if err.status_code == 404 and err.detail == "Not Found":
                return await super().get_response("index.html", scope)
            else:
                raise err


api = FastAPI(
    debug=bool(Config.debug),
    title="NoneBot CLI WebUI",
    description="WebUI for NoneBot CLI",
    version=get_version(),
    openapi_url="/docs/openapi.json",
    root_path="/api",
    docs_url=None,
    redoc_url="/docs",
)
api.include_router(api_router, prefix="/v1")
app = FastAPI(openapi_url="")
app.mount("/api", app=api)
app.include_router(api_router, prefix="/v1")
app.mount("/assets", StaticFiles(directory=STATIC_PATH / "assets", html=False), "NoneBot WebUI Assets")


@app.get("/", include_in_schema=False)
async def serve_frontend_root():
    return FileResponse(STATIC_PATH / "index.html")


@app.get("/{full_path:path}", include_in_schema=False)
async def serve_frontend_app(full_path: str):
    normalized = str(full_path or "").lstrip("/")
    if normalized.startswith(("v1/", "api/")):
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"detail": [{"msg": "Not Found"}]},
        )

    candidate = (STATIC_PATH / normalized).resolve()
    try:
        candidate.relative_to(STATIC_PATH.resolve())
    except ValueError:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"detail": [{"msg": "Not Found"}]},
        )

    if candidate.is_file():
        return FileResponse(candidate)

    return FileResponse(STATIC_PATH / "index.html")


@app.middleware("http")
async def auth(request, call_next):
    request_path = request.url.path

    if request_path in PASS_PATHS:
        return await call_next(request)

    authorization = request.headers.get("Authorization")
    _, param = get_authorization_scheme_param(authorization)
    if any(request_path.startswith(route) for route in AUTH_ROUTES):
        secret_key = Config.secret_key.get_secret_value()
        try:
            ensure_login_token_is_active()
            jwt.verify_and_read_jwt(param, secret_key)
        except Exception as err:
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN, content={"detail": str(err)}
            )

    return await call_next(request)


app.add_middleware(
    CORSMiddleware,
    allow_origins=Config.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    if "WEBUI_BUILD" in os.environ:
        log.info("Running in docker.")
        await maybe_auto_select_best_source_preset()
        apply_container_runtime_config()

    log.info("Starting NoneBot CLI WebUI.")
    log.info(f"NoneBot CLI WebUI version: {get_version()}")
    if Config.debug:
        log.debug("Debug mode is enabled.")

    scheduler.start()
    configure_backup_scheduler()
    cleanup_old_logs()
    try:
        scheduler.remove_job(LOG_CLEANUP_JOB_ID)
    except Exception:
        pass
    scheduler.add_job(
        cleanup_old_logs,
        "interval",
        hours=24,
        id=LOG_CLEANUP_JOB_ID,
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )

    await plugin_store_manager.load_item()
    await adapter_store_manager.load_item()
    await driver_store_manager.load_item()


@app.on_event("shutdown")
async def shutdown_event():
    scheduler.shutdown()

    log.info("Check and stop all running processes.")
    for process_id in list(ProcessManager.processes):
        process = ProcessManager.get_process(process_id)
        if process and process.process_is_running:
            await process.stop()

    for project_id in list(ProjectShellSessionManager.sessions):
        await ProjectShellSessionManager.stop_session(project_id)


@app.exception_handler(404)
async def not_found(request, exc):
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"detail": [{"msg": "Not Found"}]},
    )
