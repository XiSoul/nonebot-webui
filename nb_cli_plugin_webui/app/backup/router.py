import asyncio
import os
import tempfile
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, Header, Query, Request
from fastapi.responses import FileResponse

from nb_cli_plugin_webui.app.config import Config
from nb_cli_plugin_webui.app.handlers import NoneBotProjectManager
from nb_cli_plugin_webui.app.project import get_nonebot_project_manager
from nb_cli_plugin_webui.app.schemas import GenericResponse

from .schemas import (
    BackupArchiveResponse,
    BackupConnectivityRequest,
    BackupConnectivityResponse,
    BackupRemoteListResponse,
    BackupRestoreRemoteRequest,
    BackupRestoreResponse,
    BackupSettingsResponse,
    BackupSettingsUpdateRequest,
    BackupSource,
)
from .service import (
    build_backup_filename,
    create_backup_archive,
    download_remote_backup,
    configure_backup_scheduler,
    get_backup_settings_response,
    list_remote_backups,
    remove_temp_file,
    restore_project_from_archive,
    test_backup_connectivity,
    update_backup_settings,
    upload_backup_to_remote,
    prune_remote_backups,
)

router = APIRouter(tags=["backup"])


@router.get("/settings", response_model=GenericResponse[BackupSettingsResponse])
async def get_backup_settings() -> GenericResponse[BackupSettingsResponse]:
    return GenericResponse(detail=BackupSettingsResponse(**get_backup_settings_response()))


@router.put("/settings", response_model=GenericResponse[str])
async def put_backup_settings(
    data: BackupSettingsUpdateRequest,
) -> GenericResponse[str]:
    update_backup_settings(data)
    configure_backup_scheduler()
    return GenericResponse(detail="success")


@router.post("/test", response_model=GenericResponse[BackupConnectivityResponse])
async def post_backup_test(
    data: BackupConnectivityRequest,
) -> GenericResponse[BackupConnectivityResponse]:
    ok, message, detail = await asyncio.to_thread(test_backup_connectivity, data)
    return GenericResponse(
        detail=BackupConnectivityResponse(
            ok=ok, source=data.source, message=message, detail=detail
        )
    )


@router.get("/list", response_model=GenericResponse[BackupRemoteListResponse])
async def get_backup_list(
    source: BackupSource = Query(...),
) -> GenericResponse[BackupRemoteListResponse]:
    items = await asyncio.to_thread(list_remote_backups, source)
    return GenericResponse(detail=BackupRemoteListResponse(source=source, items=items))


@router.post("/download")
async def download_project_backup(
    background_tasks: BackgroundTasks,
    project: NoneBotProjectManager = Depends(get_nonebot_project_manager),
):
    project_meta = project.read()
    filename = build_backup_filename(project_meta.project_name)
    archive_path = await asyncio.to_thread(
        create_backup_archive,
        project_meta.project_id,
        project_meta.project_name,
        Path(project_meta.project_dir),
        Config.backup_archive_password,
    )
    background_tasks.add_task(remove_temp_file, archive_path)
    return FileResponse(
        path=archive_path,
        filename=filename,
        media_type="application/zip",
    )


@router.post("/upload", response_model=GenericResponse[BackupArchiveResponse])
async def upload_project_backup(
    source: BackupSource = Query(...),
    project: NoneBotProjectManager = Depends(get_nonebot_project_manager),
) -> GenericResponse[BackupArchiveResponse]:
    project_meta = project.read()
    filename = build_backup_filename(project_meta.project_name)
    archive_path = await asyncio.to_thread(
        create_backup_archive,
        project_meta.project_id,
        project_meta.project_name,
        Path(project_meta.project_dir),
        Config.backup_archive_password,
    )
    try:
        key, size = await asyncio.to_thread(
            upload_backup_to_remote, source, archive_path, filename
        )
        await asyncio.to_thread(
            prune_remote_backups, source, project_meta.project_name, Config.backup_keep_count
        )
    finally:
        remove_temp_file(archive_path)

    return GenericResponse(
        detail=BackupArchiveResponse(
            source=source,
            key=key,
            name=filename,
            size=size,
            created_at="",
        )
    )


@router.post("/restore/remote", response_model=GenericResponse[BackupRestoreResponse])
async def restore_remote_backup(
    data: BackupRestoreRemoteRequest,
    project: NoneBotProjectManager = Depends(get_nonebot_project_manager),
) -> GenericResponse[BackupRestoreResponse]:
    fd, archive_name = tempfile.mkstemp(
        prefix="nonebot-webui-restore-", suffix=".zip"
    )
    os.close(fd)
    archive_path = Path(archive_name)

    try:
        await asyncio.to_thread(download_remote_backup, data.source, data.key, archive_path)
        restarted = await restore_project_from_archive(
            project, archive_path, password=data.password
        )
    finally:
        remove_temp_file(archive_path)

    return GenericResponse(
        detail=BackupRestoreResponse(
            restarted=restarted,
            message=(
                "Remote backup restored successfully. Instance was restarted automatically."
                if restarted
                else "Remote backup restored successfully."
            ),
        )
    )


@router.post("/restore/local", response_model=GenericResponse[BackupRestoreResponse])
async def restore_local_backup(
    request: Request,
    project: NoneBotProjectManager = Depends(get_nonebot_project_manager),
    x_backup_filename: str = Header(default="", alias="X-Backup-Filename"),
    x_backup_password: str = Header(default="", alias="X-Backup-Password"),
) -> GenericResponse[BackupRestoreResponse]:
    _ = x_backup_filename.strip() or "backup.zip"

    fd, archive_name = tempfile.mkstemp(
        prefix="nonebot-webui-restore-upload-", suffix=".zip"
    )
    os.close(fd)
    archive_path = Path(archive_name)

    try:
        with archive_path.open("wb") as target:
            async for chunk in request.stream():
                if chunk:
                    target.write(chunk)

        restarted = await restore_project_from_archive(
            project, archive_path, password=x_backup_password
        )
    finally:
        remove_temp_file(archive_path)

    return GenericResponse(
        detail=BackupRestoreResponse(
            restarted=restarted,
            message=(
                "Local backup restored successfully. Instance was restarted automatically."
                if restarted
                else "Local backup restored successfully."
            ),
        )
    )
