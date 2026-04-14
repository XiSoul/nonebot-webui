from fastapi import APIRouter, Query

from nb_cli_plugin_webui.app.config import CONFIG_FILE_PATH, Config
from nb_cli_plugin_webui.app.schemas import GenericResponse
from nb_cli_plugin_webui.app.utils.global_log import (
    append_ui_event,
    cleanup_old_logs,
    get_log_settings_response,
    list_log_dates,
    read_log_entries,
)

from .schemas import (
    GlobalLogCatalogResponse,
    GlobalLogEntriesResponse,
    GlobalLogEntry,
    GlobalLogEventRequest,
    GlobalLogSettingsResponse,
    GlobalLogSettingsUpdateRequest,
    LogKind,
)

router = APIRouter(tags=["log-center"])


@router.get("/settings", response_model=GenericResponse[GlobalLogSettingsResponse])
async def get_global_log_settings() -> GenericResponse[GlobalLogSettingsResponse]:
    return GenericResponse(detail=GlobalLogSettingsResponse(**get_log_settings_response()))


@router.put("/settings", response_model=GenericResponse[str])
async def put_global_log_settings(
    data: GlobalLogSettingsUpdateRequest,
) -> GenericResponse[str]:
    Config.global_log_min_level = data.min_level
    Config.global_log_retention_days = data.retention_days
    Config.store(CONFIG_FILE_PATH)
    cleanup_old_logs()
    return GenericResponse(detail="success")


@router.get("/catalog", response_model=GenericResponse[GlobalLogCatalogResponse])
async def get_global_log_catalog(
    kind: LogKind = Query(...),
    project_id: str = Query(default=""),
    project_name: str = Query(default=""),
) -> GenericResponse[GlobalLogCatalogResponse]:
    dates = list_log_dates(kind, project_id=project_id, project_name=project_name)
    return GenericResponse(detail=GlobalLogCatalogResponse(kind=kind, dates=dates))


@router.get("/entries", response_model=GenericResponse[GlobalLogEntriesResponse])
async def get_global_log_entries(
    kind: LogKind = Query(...),
    date: str = Query(...),
    level: str = Query(default="DEBUG"),
    search: str = Query(default=""),
    project_id: str = Query(default=""),
    project_name: str = Query(default=""),
) -> GenericResponse[GlobalLogEntriesResponse]:
    items = read_log_entries(
        kind,
        date=date,
        level=level,
        search=search,
        project_id=project_id,
        project_name=project_name,
    )
    return GenericResponse(
        detail=GlobalLogEntriesResponse(
            kind=kind,
            date=date,
            total=len(items),
            items=[GlobalLogEntry(**item) for item in items],
        )
    )


@router.post("/event", response_model=GenericResponse[str])
async def post_global_log_event(data: GlobalLogEventRequest) -> GenericResponse[str]:
    append_ui_event(
        level=data.level,
        message=data.message,
        detail=data.detail,
        source=data.source,
        project_id=data.project_id,
        project_name=data.project_name,
    )
    return GenericResponse(detail="success")
