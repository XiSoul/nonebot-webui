from typing import List, Literal

from pydantic import BaseModel


BackupSource = Literal["webdav", "s3"]


class BackupSettingsResponse(BaseModel):
    webdav_url: str = ""
    webdav_username: str = ""
    webdav_password: str = ""
    webdav_base_path: str = "/"
    webdav_configured: bool = False

    s3_endpoint: str = ""
    s3_region: str = "us-east-1"
    s3_bucket: str = ""
    s3_access_key: str = ""
    s3_secret_key: str = ""
    s3_prefix: str = ""
    s3_force_path_style: bool = True
    s3_configured: bool = False
    archive_password: str = ""
    archive_password_configured: bool = False
    auto_backup_enabled: bool = False
    auto_backup_interval_hours: int = 24
    keep_count: int = 10
    include_logs: bool = False
    log_project_ids: List[str] = []


class BackupSettingsUpdateRequest(BaseModel):
    webdav_url: str = ""
    webdav_username: str = ""
    webdav_password: str = ""
    webdav_base_path: str = "/"

    s3_endpoint: str = ""
    s3_region: str = "us-east-1"
    s3_bucket: str = ""
    s3_access_key: str = ""
    s3_secret_key: str = ""
    s3_prefix: str = ""
    s3_force_path_style: bool = True
    archive_password: str = ""
    auto_backup_enabled: bool = False
    auto_backup_interval_hours: int = 24
    keep_count: int = 10
    include_logs: bool = False
    log_project_ids: List[str] = []


class BackupConnectivityRequest(BackupSettingsUpdateRequest):
    source: BackupSource


class BackupConnectivityResponse(BaseModel):
    ok: bool = False
    source: BackupSource
    message: str = ""
    detail: str = ""


class BackupRemoteItem(BaseModel):
    source: BackupSource
    key: str
    name: str
    size: int = 0
    last_modified: str = ""


class BackupRemoteListResponse(BaseModel):
    source: BackupSource
    items: List[BackupRemoteItem]


class BackupArchiveResponse(BaseModel):
    source: str
    key: str = ""
    name: str
    size: int = 0
    created_at: str = ""


class BackupRestoreRemoteRequest(BaseModel):
    source: BackupSource
    key: str
    password: str = ""


class BackupRestoreResponse(BaseModel):
    restarted: bool = False
    message: str = ""
