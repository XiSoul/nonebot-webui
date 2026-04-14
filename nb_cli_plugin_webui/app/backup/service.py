import asyncio
import hmac
import json
import os
import shutil
import tempfile
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path, PurePosixPath
from typing import Dict, List, Optional, Tuple
from urllib.parse import quote, urlparse
from xml.etree import ElementTree as ET

import httpx
from fastapi import HTTPException, status
try:
    import pyzipper
except ImportError:  # pragma: no cover - optional until image is rebuilt
    pyzipper = None

from nb_cli_plugin_webui import get_version
from nb_cli_plugin_webui.app.config import CONFIG_FILE_PATH, Config
from nb_cli_plugin_webui.app.handlers.process import ProcessManager
from nb_cli_plugin_webui.app.handlers.project import NoneBotProjectManager
from nb_cli_plugin_webui.app.logging import logger
from nb_cli_plugin_webui.app.process.service import run_nonebot_project
from nb_cli_plugin_webui.app.utils.global_log import (
    build_instance_log_folder_name,
    get_global_logs_root,
)
from nb_cli_plugin_webui.app.utils.scheduler import scheduler

from .schemas import (
    BackupConnectivityRequest,
    BackupRemoteItem,
    BackupSettingsUpdateRequest,
    BackupSource,
)

BACKUP_METADATA_NAME = ".nb-webui-backup.json"
BACKUP_LOG_ROOT = "__nb_webui_logs__"
BACKUP_JOB_ID = "scheduled-project-backup"
BACKUP_USER_AGENT = "NoneBot-WebUI-Backup/%s" % get_version()


def _http_request_without_env_proxy(
    method: str,
    url: str,
    **kwargs,
) -> httpx.Response:
    return httpx.request(method, url, trust_env=False, **kwargs)


def _normalize_text(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def _clean_posix_path(value: str, default: str = "") -> str:
    normalized = _normalize_text(value).replace("\\", "/")
    if not normalized:
        return default
    parts = [part for part in normalized.split("/") if part and part != "."]
    if not parts:
        return default
    return "/".join(parts)


def _clean_webdav_base_path(value: str) -> str:
    normalized = _clean_posix_path(value, default="")
    if not normalized:
        return "/"
    return "/" + normalized


def _archive_password_from_config() -> str:
    return _normalize_archive_password(getattr(Config, "backup_archive_password", ""))


def _extract_host(value: str) -> str:
    normalized = _normalize_text(value)
    if not normalized:
        return ""
    if "://" not in normalized:
        normalized = "https://" + normalized
    try:
        return (urlparse(normalized).hostname or "").lower()
    except Exception:
        return ""


def _is_cstcloud_host(value: str) -> bool:
    host = _extract_host(value)
    return bool(host and host.endswith("cstcloud.cn"))


def _archive_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")


def _iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _safe_archive_name(project_name: str) -> str:
    raw = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in project_name)
    return raw.strip("._") or "nonebot-project"


def _backup_name_prefix(project_name: str) -> str:
    return _safe_archive_name(project_name) + "-"


def build_backup_filename(project_name: str) -> str:
    return "%s-%s.zip" % (_safe_archive_name(project_name), _archive_timestamp())


def _normalize_keep_count(value: object) -> int:
    try:
        count = int(value)
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Backup keep count must be an integer.",
        ) from err
    if count < 1 or count > 200:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Backup keep count must be between 1 and 200.",
        )
    return count


def _normalize_archive_password(value: object) -> str:
    return _normalize_text(value)


def _normalize_project_id_list(value: object) -> List[str]:
    if not isinstance(value, list):
        return []

    result: List[str] = []
    seen = set()
    for item in value:
        normalized = _normalize_text(item)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    return result


def _normalize_interval_hours(value: object) -> int:
    try:
        hours = int(value)
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Backup interval must be an integer hour value.",
        ) from err
    if hours < 1 or hours > 720:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Backup interval must be between 1 and 720 hours.",
        )
    return hours


def remove_temp_file(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except Exception:
        pass


def _write_archive_metadata(archive: zipfile.ZipFile, project_id: str, project_name: str) -> None:
    archive.writestr(
        BACKUP_METADATA_NAME,
        json.dumps(
            {
                "project_id": project_id,
                "project_name": project_name,
                "created_at": _iso_now(),
            },
            ensure_ascii=False,
            indent=2,
        ),
    )


def _resolve_backup_log_projects() -> List[Tuple[str, str]]:
    if not bool(getattr(Config, "backup_include_logs", False)):
        return []

    selected_ids = _normalize_project_id_list(
        getattr(Config, "backup_log_project_ids", [])
    )
    if not selected_ids:
        return []

    try:
        project_map = NoneBotProjectManager.get_project()
    except Exception:
        project_map = {}

    result: List[Tuple[str, str]] = []
    for project_id in selected_ids:
        project_meta = project_map.get(project_id)
        project_name = _normalize_text(
            getattr(project_meta, "project_name", "") if project_meta else ""
        )
        result.append((project_id, project_name))
    return result


def _iter_backup_log_sources() -> List[Tuple[Path, str]]:
    log_root = get_global_logs_root(create=False)
    if not log_root.exists():
        return []

    items: List[Tuple[Path, str]] = []
    for project_id, project_name in _resolve_backup_log_projects():
        if project_name:
            directory = log_root / "instances" / build_instance_log_folder_name(
                project_id, project_name
            )
            if directory.is_dir():
                items.append((directory, directory.name))
                continue

        pattern = "%s-*" % project_id
        matches = sorted((log_root / "instances").glob(pattern))
        for match in matches:
            if match.is_dir():
                items.append((match, match.name))
    return items


def _write_selected_logs_to_archive(archive: zipfile.ZipFile) -> None:
    for source_dir, folder_name in _iter_backup_log_sources():
        for file_path in sorted(source_dir.rglob("*")):
            if file_path.is_dir():
                continue
            archive.write(
                file_path,
                arcname=PurePosixPath(BACKUP_LOG_ROOT, "instances", folder_name, *file_path.relative_to(source_dir).parts).as_posix(),
            )


def _archive_requires_password(archive_path: Path) -> bool:
    with zipfile.ZipFile(archive_path, "r") as archive:
        return any(info.flag_bits & 0x1 for info in archive.infolist())


def _open_archive_for_reading(archive_path: Path, password: str = ""):
    normalized_password = _normalize_archive_password(password)
    requires_password = _archive_requires_password(archive_path)
    if requires_password and not normalized_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Backup archive requires password.",
        )

    if requires_password and pyzipper is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Encrypted backup support is unavailable. Please rebuild the image.",
        )

    archive_class = pyzipper.AESZipFile if pyzipper is not None else zipfile.ZipFile
    archive = archive_class(archive_path, "r")
    if normalized_password:
        archive.setpassword(normalized_password.encode("utf-8"))
    return archive


def _create_archive_writer(archive_path: Path, password: str = ""):
    normalized_password = _normalize_archive_password(password)
    if not normalized_password:
        return zipfile.ZipFile(
            archive_path, mode="w", compression=zipfile.ZIP_DEFLATED
        )

    if pyzipper is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Encrypted backup support is unavailable. Please rebuild the image.",
        )

    archive = pyzipper.AESZipFile(
        archive_path,
        mode="w",
        compression=zipfile.ZIP_DEFLATED,
        encryption=pyzipper.WZ_AES,
    )
    archive.setpassword(normalized_password.encode("utf-8"))
    archive.setencryption(pyzipper.WZ_AES, nbits=256)
    return archive


def create_backup_archive(
    project_id: str,
    project_name: str,
    project_dir: Path,
    password: str = "",
) -> Path:
    if not project_dir.is_dir():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project directory does not exist.",
        )

    fd, archive_name = tempfile.mkstemp(
        prefix="nonebot-webui-backup-%s-" % project_id,
        suffix=".zip",
    )
    os.close(fd)
    archive_path = Path(archive_name)

    try:
        with _create_archive_writer(archive_path, password=password) as archive:
            for file_path in sorted(project_dir.rglob("*")):
                if file_path.is_dir():
                    continue
                archive.write(
                    file_path,
                    arcname=file_path.relative_to(project_dir).as_posix(),
                )
            _write_selected_logs_to_archive(archive)
            _write_archive_metadata(archive, project_id, project_name)
    except Exception:
        remove_temp_file(archive_path)
        raise

    return archive_path


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _restore_member_mode(member: zipfile.ZipInfo, destination: Path) -> None:
    mode = (member.external_attr >> 16) & 0o7777
    if not mode:
        return

    try:
        destination.chmod(mode)
    except Exception:
        pass


def _extract_archive_safely(
    archive_path: Path,
    target_dir: Path,
    *,
    log_stage_dir: Optional[Path] = None,
    password: str = "",
) -> None:
    target_root = target_dir.resolve()
    log_stage_root = log_stage_dir.resolve() if log_stage_dir else None
    try:
        with _open_archive_for_reading(archive_path, password=password) as archive:
            for member in archive.infolist():
                member_name = member.filename.replace("\\", "/")
                if (
                    not member_name
                    or member_name.endswith("/")
                    or member_name == BACKUP_METADATA_NAME
                ):
                    continue

                destination_root = target_root
                relative_name = member_name
                log_prefix = BACKUP_LOG_ROOT + "/"
                if member_name.startswith(log_prefix):
                    if log_stage_root is None:
                        continue
                    destination_root = log_stage_root
                    relative_name = member_name[len(log_prefix) :]
                    if not relative_name:
                        continue

                destination = (destination_root / relative_name).resolve()
                try:
                    destination.relative_to(destination_root)
                except ValueError as err:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Backup archive contains unsafe file paths.",
                    ) from err

                _ensure_parent(destination)
                with archive.open(member, "r") as source, destination.open("wb") as output:
                    shutil.copyfileobj(source, output)
                _restore_member_mode(member, destination)
    except RuntimeError as err:
        message = str(err).lower()
        if "password" in message or "decrypt" in message:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Backup password is invalid.",
            ) from err
        raise


def _merge_directory_tree(source_dir: Path, target_dir: Path) -> None:
    if not source_dir.exists():
        return

    target_dir.mkdir(parents=True, exist_ok=True)
    source_instances_dir = source_dir / "instances"
    if source_instances_dir.is_dir():
        target_instances_dir = target_dir / "instances"
        target_instances_dir.mkdir(parents=True, exist_ok=True)
        for instance_dir in sorted(source_instances_dir.iterdir()):
            if not instance_dir.is_dir():
                continue
            destination_dir = target_instances_dir / instance_dir.name
            if destination_dir.exists():
                shutil.rmtree(destination_dir, ignore_errors=True)
            shutil.copytree(instance_dir, destination_dir)

    for source_path in sorted(source_dir.rglob("*")):
        if source_instances_dir in source_path.parents or source_path == source_instances_dir:
            continue
        relative_path = source_path.relative_to(source_dir)
        destination = target_dir / relative_path
        if source_path.is_dir():
            destination.mkdir(parents=True, exist_ok=True)
            continue

        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, destination)


async def restore_project_from_archive(project, archive_path: Path, password: str = "") -> bool:
    project_meta = project.read()
    project_dir = Path(project_meta.project_dir)
    parent_dir = project_dir.parent
    parent_dir.mkdir(parents=True, exist_ok=True)

    process = ProcessManager.get_process(project_meta.project_id)
    was_running = bool(process and process.process_is_running)
    if was_running and process:
        await process.stop()

    try:
        ProcessManager.remove_process(project_meta.project_id)
    except Exception:
        pass

    staged_dir = Path(
        tempfile.mkdtemp(prefix=".backup-restore-new-", dir=str(parent_dir))
    )
    staged_log_dir = Path(tempfile.mkdtemp(prefix=".backup-restore-logs-"))
    old_dir = parent_dir / (
        ".backup-restore-old-%s-%s"
        % (project_meta.project_id, _archive_timestamp())
    )
    old_dir_exists = False

    try:
        _extract_archive_safely(
            archive_path,
            staged_dir,
            log_stage_dir=staged_log_dir,
            password=password,
        )
        if not any(staged_dir.iterdir()):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Backup archive is empty.",
            )

        if project_dir.exists():
            shutil.move(str(project_dir), str(old_dir))
            old_dir_exists = True

        shutil.move(str(staged_dir), str(project_dir))
        staged_dir = Path()

        _merge_directory_tree(staged_log_dir, get_global_logs_root())

        if old_dir_exists:
            shutil.rmtree(old_dir, ignore_errors=True)
    except Exception:
        if staged_dir and staged_dir.exists():
            shutil.rmtree(staged_dir, ignore_errors=True)
        if staged_log_dir.exists():
            shutil.rmtree(staged_log_dir, ignore_errors=True)

        if not project_dir.exists() and old_dir_exists and old_dir.exists():
            shutil.move(str(old_dir), str(project_dir))
        raise
    finally:
        if staged_log_dir.exists():
            shutil.rmtree(staged_log_dir, ignore_errors=True)

    if was_running:
        await run_nonebot_project(project)
    return was_running


@dataclass
class WebDavSettings:
    url: str
    username: str
    password: str
    base_path: str

    @classmethod
    def from_config(cls) -> "WebDavSettings":
        return cls(
            url=_normalize_text(Config.backup_webdav_url),
            username=_normalize_text(Config.backup_webdav_username),
            password=_normalize_text(Config.backup_webdav_password),
            base_path=_clean_webdav_base_path(Config.backup_webdav_base_path),
        )

    def is_configured(self) -> bool:
        return bool(self.url and self.username and self.password)


@dataclass
class S3Settings:
    endpoint: str
    region: str
    bucket: str
    access_key: str
    secret_key: str
    prefix: str
    force_path_style: bool

    @classmethod
    def from_config(cls) -> "S3Settings":
        return cls(
            endpoint=_normalize_text(Config.backup_s3_endpoint),
            region=_normalize_text(Config.backup_s3_region) or "us-east-1",
            bucket=_normalize_text(Config.backup_s3_bucket),
            access_key=_normalize_text(Config.backup_s3_access_key),
            secret_key=_normalize_text(Config.backup_s3_secret_key),
            prefix=_clean_posix_path(Config.backup_s3_prefix, default=""),
            force_path_style=bool(Config.backup_s3_force_path_style),
        )

    def is_configured(self) -> bool:
        return bool(
            self.endpoint
            and self.region
            and self.bucket
            and self.access_key
            and self.secret_key
        )


def _resolve_webdav_user_agent(settings: "WebDavSettings") -> str:
    if _is_cstcloud_host(settings.url):
        return "Zotero/8.0"
    return BACKUP_USER_AGENT


def _resolve_s3_user_agent(settings: "S3Settings") -> str:
    if _is_cstcloud_host(settings.endpoint):
        return "S3Drive"
    return BACKUP_USER_AGENT


def get_backup_settings_response() -> Dict[str, object]:
    webdav = WebDavSettings.from_config()
    s3 = S3Settings.from_config()
    return {
        "webdav_url": webdav.url,
        "webdav_username": webdav.username,
        "webdav_password": webdav.password,
        "webdav_base_path": webdav.base_path,
        "webdav_configured": webdav.is_configured(),
        "s3_endpoint": s3.endpoint,
        "s3_region": s3.region,
        "s3_bucket": s3.bucket,
        "s3_access_key": s3.access_key,
        "s3_secret_key": s3.secret_key,
        "s3_prefix": s3.prefix,
        "s3_force_path_style": s3.force_path_style,
        "s3_configured": s3.is_configured(),
        "archive_password": _archive_password_from_config(),
        "archive_password_configured": bool(_archive_password_from_config()),
        "auto_backup_enabled": bool(Config.backup_auto_enabled),
        "auto_backup_interval_hours": _normalize_interval_hours(
            getattr(Config, "backup_auto_interval_hours", 24)
        ),
        "keep_count": _normalize_keep_count(getattr(Config, "backup_keep_count", 10)),
        "include_logs": bool(getattr(Config, "backup_include_logs", False)),
        "log_project_ids": _normalize_project_id_list(
            getattr(Config, "backup_log_project_ids", [])
        ),
    }


def update_backup_settings(data: BackupSettingsUpdateRequest) -> None:
    Config.backup_webdav_url = _normalize_text(data.webdav_url)
    Config.backup_webdav_username = _normalize_text(data.webdav_username)
    Config.backup_webdav_password = _normalize_text(data.webdav_password)
    Config.backup_webdav_base_path = _clean_webdav_base_path(data.webdav_base_path)

    Config.backup_s3_endpoint = _normalize_text(data.s3_endpoint)
    Config.backup_s3_region = _normalize_text(data.s3_region) or "us-east-1"
    Config.backup_s3_bucket = _normalize_text(data.s3_bucket)
    Config.backup_s3_access_key = _normalize_text(data.s3_access_key)
    Config.backup_s3_secret_key = _normalize_text(data.s3_secret_key)
    Config.backup_s3_prefix = _clean_posix_path(data.s3_prefix, default="")
    Config.backup_s3_force_path_style = bool(data.s3_force_path_style)
    Config.backup_archive_password = _normalize_archive_password(data.archive_password)
    Config.backup_auto_enabled = bool(data.auto_backup_enabled)
    Config.backup_auto_interval_hours = _normalize_interval_hours(
        data.auto_backup_interval_hours
    )
    Config.backup_keep_count = _normalize_keep_count(data.keep_count)
    Config.backup_include_logs = bool(data.include_logs)
    Config.backup_log_project_ids = _normalize_project_id_list(data.log_project_ids)
    Config.store(CONFIG_FILE_PATH)


def _ensure_webdav_configured(settings: WebDavSettings) -> None:
    if settings.is_configured():
        return
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="WebDAV backup storage is not configured.",
    )


def _quote_path(path: str) -> str:
    parts = [part for part in path.split("/") if part]
    if not parts:
        return "/"
    return "/" + "/".join(quote(part, safe="") for part in parts)


def _webdav_url(settings: WebDavSettings, relative_path: str = "") -> str:
    base_url = settings.url.rstrip("/")
    full_path = settings.base_path
    normalized_relative = _clean_posix_path(relative_path, default="")
    if normalized_relative:
        full_path = "%s/%s" % (full_path.rstrip("/"), normalized_relative)
    return "%s%s" % (base_url, _quote_path(full_path))


def _webdav_request(
    method: str,
    settings: WebDavSettings,
    relative_path: str = "",
    headers: Optional[Dict[str, str]] = None,
    content: bytes = b"",
) -> httpx.Response:
    request_headers = {"User-Agent": _resolve_webdav_user_agent(settings)}
    if headers:
        request_headers.update(headers)
    return _http_request_without_env_proxy(
        method,
        _webdav_url(settings, relative_path),
        auth=(settings.username, settings.password),
        headers=request_headers,
        content=content,
        timeout=120.0,
    )


def ensure_webdav_base_path(settings: WebDavSettings) -> None:
    _ensure_webdav_configured(settings)
    parts = [part for part in settings.base_path.split("/") if part]
    current = "/"
    for part in parts:
        current = "%s/%s" % (current.rstrip("/"), part)
        response = _webdav_request("MKCOL", settings, current)
        if response.status_code not in {200, 201, 301, 405}:
            response_text = (
                response.text.strip().replace("\n", " ")[:300]
                or response.reason_phrase
                or "-"
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to prepare WebDAV path: %s %s (path=%s)"
                % (response.status_code, response_text, current),
            )


def upload_backup_to_webdav(archive_path: Path, remote_name: str) -> Tuple[str, int]:
    settings = WebDavSettings.from_config()
    ensure_webdav_base_path(settings)

    response = _webdav_request(
        "PUT",
        settings,
        remote_name,
        content=archive_path.read_bytes(),
    )
    if response.status_code not in {200, 201, 204}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="WebDAV upload failed.",
        )
    return remote_name, archive_path.stat().st_size


def list_webdav_backups() -> List[BackupRemoteItem]:
    settings = WebDavSettings.from_config()
    if not settings.is_configured():
        return []

    response = _webdav_request(
        "PROPFIND",
        settings,
        headers={"Depth": "1", "Content-Type": "application/xml"},
        content=(
            b'<?xml version="1.0" encoding="utf-8"?>'
            b"<propfind xmlns=\"DAV:\">"
            b"<prop><displayname/><getcontentlength/><getlastmodified/><resourcetype/></prop>"
            b"</propfind>"
        ),
    )
    if response.status_code not in {200, 207}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="WebDAV list failed.",
        )

    namespace = {"d": "DAV:"}
    root = ET.fromstring(response.content)
    root_path = urlparse(_webdav_url(settings)).path.rstrip("/")
    items: List[BackupRemoteItem] = []
    for node in root.findall("d:response", namespace):
        href = node.findtext("d:href", default="", namespaces=namespace)
        parsed_path = urlparse(href).path.rstrip("/")
        if not parsed_path or parsed_path == root_path:
            continue

        resource_type = node.find("d:propstat/d:prop/d:resourcetype", namespace)
        if resource_type is not None and resource_type.find("d:collection", namespace) is not None:
            continue

        if parsed_path.startswith(root_path):
            key = parsed_path[len(root_path) :].lstrip("/")
        else:
            key = parsed_path.lstrip("/")
        if not key:
            continue

        size_text = node.findtext(
            "d:propstat/d:prop/d:getcontentlength",
            default="0",
            namespaces=namespace,
        )
        try:
            size_value = int(size_text)
        except Exception:
            size_value = 0

        items.append(
            BackupRemoteItem(
                source="webdav",
                key=key,
                name=node.findtext(
                    "d:propstat/d:prop/d:displayname",
                    default=PurePosixPath(key).name,
                    namespaces=namespace,
                ),
                size=size_value,
                last_modified=node.findtext(
                    "d:propstat/d:prop/d:getlastmodified",
                    default="",
                    namespaces=namespace,
                ),
            )
        )

    items.sort(key=lambda item: item.last_modified or item.name, reverse=True)
    return items


def download_backup_from_webdav(remote_key: str, target_path: Path) -> None:
    settings = WebDavSettings.from_config()
    _ensure_webdav_configured(settings)

    response = _webdav_request("GET", settings, remote_key)
    if response.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="WebDAV backup download failed.",
        )
    target_path.write_bytes(response.content)


def delete_backup_from_webdav(remote_key: str) -> None:
    settings = WebDavSettings.from_config()
    _ensure_webdav_configured(settings)

    response = _webdav_request("DELETE", settings, remote_key)
    if response.status_code not in {200, 202, 204}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="WebDAV backup delete failed.",
        )


def test_webdav_connection(settings: WebDavSettings) -> Tuple[bool, str, str]:
    ensure_webdav_base_path(settings)
    response = _webdav_request("PROPFIND", settings, headers={"Depth": "0"})
    if response.status_code >= 400:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="WebDAV connection test failed: %s %s"
            % (response.status_code, response.text[:300] or response.reason_phrase),
        )
    detail = "status=%s user-agent=%s server=%s" % (
        response.status_code,
        _resolve_webdav_user_agent(settings),
        response.headers.get("server", "-"),
    )
    return True, "WebDAV 连接成功。", detail


def _hash_bytes(value: bytes) -> str:
    return sha256(value).hexdigest()


def _hash_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _hmac_sha256(key: bytes, value: str) -> bytes:
    return hmac.new(key, value.encode("utf-8"), sha256).digest()


def _aws_signature(
    secret_key: str,
    date_stamp: str,
    region: str,
    service: str,
    string_to_sign: str,
) -> str:
    key_date = _hmac_sha256(("AWS4" + secret_key).encode("utf-8"), date_stamp)
    key_region = _hmac_sha256(key_date, region)
    key_service = _hmac_sha256(key_region, service)
    key_signing = _hmac_sha256(key_service, "aws4_request")
    return hmac.new(
        key_signing, string_to_sign.encode("utf-8"), sha256
    ).hexdigest()


def _encode_query(params: Dict[str, str]) -> str:
    parts = []
    for key, value in sorted(params.items()):
        parts.append(
            "%s=%s" % (quote(key, safe="-_.~"), quote(value, safe="-_.~"))
        )
    return "&".join(parts)


class S3Client:
    def __init__(self, settings: S3Settings) -> None:
        if not settings.is_configured():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="S3 backup storage is not configured.",
            )

        endpoint = settings.endpoint
        if "://" not in endpoint:
            endpoint = "https://" + endpoint
        self.settings = settings
        self.parsed_endpoint = urlparse(endpoint)
        if not self.parsed_endpoint.scheme or not self.parsed_endpoint.netloc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="S3 endpoint is invalid.",
            )

    def _target(self, key: str) -> Tuple[str, str]:
        normalized_key = _clean_posix_path(key, default="")
        endpoint_parts = [
            part for part in self.parsed_endpoint.path.split("/") if part
        ]
        path_style = self.settings.force_path_style or self.parsed_endpoint.hostname in {
            "127.0.0.1",
            "localhost",
        }

        if path_style:
            host = self.parsed_endpoint.netloc
            path_parts = endpoint_parts + [self.settings.bucket]
        else:
            host = "%s.%s" % (self.settings.bucket, self.parsed_endpoint.netloc)
            path_parts = endpoint_parts

        if normalized_key:
            path_parts.extend(normalized_key.split("/"))

        canonical_uri = "/" + "/".join(
            quote(part, safe="-_.~") for part in path_parts
        )
        url = "%s://%s%s" % (self.parsed_endpoint.scheme, host, canonical_uri)
        return url, canonical_uri

    def _request(
        self,
        method: str,
        key: str = "",
        params: Optional[Dict[str, str]] = None,
        content: bytes = b"",
        payload_hash: Optional[str] = None,
    ) -> httpx.Response:
        params = params or {}
        payload_hash = payload_hash or _hash_bytes(content)
        now = datetime.now(timezone.utc)
        amz_date = now.strftime("%Y%m%dT%H%M%SZ")
        date_stamp = now.strftime("%Y%m%d")
        url, canonical_uri = self._target(key)
        query_string = _encode_query(params)
        host = urlparse(url).netloc

        canonical_headers = (
            "host:%s\nx-amz-content-sha256:%s\nx-amz-date:%s\n"
            % (host, payload_hash, amz_date)
        )
        signed_headers = "host;x-amz-content-sha256;x-amz-date"
        canonical_request = "\n".join(
            [
                method,
                canonical_uri,
                query_string,
                canonical_headers,
                signed_headers,
                payload_hash,
            ]
        )
        credential_scope = "%s/%s/s3/aws4_request" % (
            date_stamp,
            self.settings.region,
        )
        string_to_sign = "\n".join(
            [
                "AWS4-HMAC-SHA256",
                amz_date,
                credential_scope,
                sha256(canonical_request.encode("utf-8")).hexdigest(),
            ]
        )
        signature = _aws_signature(
            self.settings.secret_key,
            date_stamp,
            self.settings.region,
            "s3",
            string_to_sign,
        )
        authorization = (
            "AWS4-HMAC-SHA256 "
            "Credential=%s/%s, SignedHeaders=%s, Signature=%s"
            % (
                self.settings.access_key,
                credential_scope,
                signed_headers,
                signature,
            )
        )

        return _http_request_without_env_proxy(
            method,
            url,
            params=params,
            content=content,
            headers={
                "User-Agent": _resolve_s3_user_agent(self.settings),
                "Authorization": authorization,
                "x-amz-date": amz_date,
                "x-amz-content-sha256": payload_hash,
                "x-amz-user-agent": _resolve_s3_user_agent(self.settings),
            },
            timeout=120.0,
        )

    def upload(self, archive_path: Path, key: str) -> Tuple[str, int]:
        payload_hash = _hash_file(archive_path)
        response = self._request(
            "PUT",
            key=key,
            content=archive_path.read_bytes(),
            payload_hash=payload_hash,
        )
        if response.status_code not in {200, 201}:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="S3 upload failed.",
            )
        return key, archive_path.stat().st_size

    def list(self) -> List[BackupRemoteItem]:
        params = {"list-type": "2"}
        if self.settings.prefix:
            params["prefix"] = self.settings.prefix.rstrip("/") + "/"

        response = self._request(
            "GET",
            params=params,
            content=b"",
            payload_hash=_hash_bytes(b""),
        )
        if response.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="S3 list failed.",
            )

        root = ET.fromstring(response.content)
        items: List[BackupRemoteItem] = []
        for node in root.findall(".//{*}Contents"):
            key = node.findtext("{*}Key", default="")
            if not key or key.endswith("/"):
                continue

            size_text = node.findtext("{*}Size", default="0")
            try:
                size_value = int(size_text)
            except Exception:
                size_value = 0

            items.append(
                BackupRemoteItem(
                    source="s3",
                    key=key,
                    name=PurePosixPath(key).name,
                    size=size_value,
                    last_modified=node.findtext("{*}LastModified", default=""),
                )
            )

        items.sort(key=lambda item: item.last_modified or item.name, reverse=True)
        return items

    def download(self, key: str, target_path: Path) -> None:
        response = self._request(
            "GET",
            key=key,
            content=b"",
            payload_hash=_hash_bytes(b""),
        )
        if response.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="S3 backup download failed.",
            )
        target_path.write_bytes(response.content)

    def delete(self, key: str) -> None:
        response = self._request(
            "DELETE",
            key=key,
            content=b"",
            payload_hash=_hash_bytes(b""),
        )
        if response.status_code not in {200, 202, 204}:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="S3 backup delete failed.",
            )

    def test_connection(self) -> Tuple[bool, str, str]:
        params = {"list-type": "2", "max-keys": "1"}
        if self.settings.prefix:
            params["prefix"] = self.settings.prefix.rstrip("/") + "/"
        response = self._request(
            "GET",
            params=params,
            content=b"",
            payload_hash=_hash_bytes(b""),
        )
        if response.status_code != 200:
            response_text = (
                response.text.strip().replace("\n", " ")[:300]
                or response.reason_phrase
                or response.headers.get("www-authenticate", "")
                or "-"
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="S3 connection test failed: %s %s (endpoint=%s bucket=%s region=%s path-style=%s)"
                % (
                    response.status_code,
                    response_text,
                    self.settings.endpoint,
                    self.settings.bucket,
                    self.settings.region,
                    str(self.settings.force_path_style).lower(),
                ),
            )
        detail = "status=%s user-agent=%s endpoint=%s bucket=%s path-style=%s" % (
            response.status_code,
            _resolve_s3_user_agent(self.settings),
            self.settings.endpoint,
            self.settings.bucket,
            str(self.settings.force_path_style).lower(),
        )
        return True, "S3 连接成功。", detail


def _webdav_settings_from_request(data: BackupConnectivityRequest) -> WebDavSettings:
    return WebDavSettings(
        url=_normalize_text(data.webdav_url),
        username=_normalize_text(data.webdav_username),
        password=_normalize_text(data.webdav_password),
        base_path=_clean_webdav_base_path(data.webdav_base_path),
    )


def _s3_settings_from_request(data: BackupConnectivityRequest) -> S3Settings:
    return S3Settings(
        endpoint=_normalize_text(data.s3_endpoint),
        region=_normalize_text(data.s3_region) or "us-east-1",
        bucket=_normalize_text(data.s3_bucket),
        access_key=_normalize_text(data.s3_access_key),
        secret_key=_normalize_text(data.s3_secret_key),
        prefix=_clean_posix_path(data.s3_prefix, default=""),
        force_path_style=bool(data.s3_force_path_style),
    )


def build_remote_backup_key(source: BackupSource, filename: str) -> str:
    if source == "webdav":
        return filename

    settings = S3Settings.from_config()
    if settings.prefix:
        return settings.prefix.rstrip("/") + "/" + filename
    return filename


def _delete_remote_backup(source: BackupSource, key: str) -> None:
    if source == "webdav":
        delete_backup_from_webdav(key)
        return
    S3Client(S3Settings.from_config()).delete(key)


def prune_remote_backups(source: BackupSource, project_name: str, keep_count: int) -> None:
    keep_count = _normalize_keep_count(keep_count)
    items = list_remote_backups(source)
    prefix = _backup_name_prefix(project_name)
    project_items = [item for item in items if item.name.startswith(prefix)]
    if len(project_items) <= keep_count:
        return

    for item in project_items[keep_count:]:
        try:
            _delete_remote_backup(source, item.key)
        except Exception as err:
            logger.warning(f"Failed to prune backup {item.key} from {source}: {err}")


def upload_backup_to_remote(
    source: BackupSource,
    archive_path: Path,
    filename: str,
) -> Tuple[str, int]:
    if source == "webdav":
        return upload_backup_to_webdav(archive_path, filename)
    return S3Client(S3Settings.from_config()).upload(
        archive_path,
        build_remote_backup_key(source, filename),
    )


def list_remote_backups(source: BackupSource) -> List[BackupRemoteItem]:
    if source == "webdav":
        return list_webdav_backups()
    settings = S3Settings.from_config()
    if not settings.is_configured():
        return []
    return S3Client(settings).list()


def download_remote_backup(source: BackupSource, key: str, target_path: Path) -> None:
    if source == "webdav":
        download_backup_from_webdav(key, target_path)
        return
    S3Client(S3Settings.from_config()).download(key, target_path)


def test_backup_connectivity(data: BackupConnectivityRequest) -> Tuple[bool, str, str]:
    if data.source == "webdav":
        return test_webdav_connection(_webdav_settings_from_request(data))
    return S3Client(_s3_settings_from_request(data)).test_connection()


def get_active_backup_sources() -> List[BackupSource]:
    sources: List[BackupSource] = []
    if WebDavSettings.from_config().is_configured():
        sources.append("webdav")
    if S3Settings.from_config().is_configured():
        sources.append("s3")
    return sources


async def run_scheduled_backup_once() -> None:
    sources = get_active_backup_sources()
    if not sources:
        logger.info("Scheduled backup skipped because no remote storage is configured.")
        return

    keep_count = _normalize_keep_count(getattr(Config, "backup_keep_count", 10))
    try:
        project_map = NoneBotProjectManager.get_project()
    except Exception as err:
        logger.warning(f"Scheduled backup skipped because project list is unavailable: {err}")
        return

    for project_id, project_meta in project_map.items():
        project_dir = Path(project_meta.project_dir)
        if not project_dir.is_dir():
            logger.warning(
                f"Scheduled backup skipped for {project_meta.project_name}: project directory not found."
            )
            continue

        filename = build_backup_filename(project_meta.project_name)
        try:
            archive_path = await asyncio.to_thread(
                create_backup_archive,
                project_id,
                project_meta.project_name,
                project_dir,
                _archive_password_from_config(),
            )
        except Exception as err:
            logger.exception(err)
            logger.warning(
                f"Scheduled backup failed while archiving {project_meta.project_name}: {err}"
            )
            continue

        try:
            for source in sources:
                try:
                    await asyncio.to_thread(
                        upload_backup_to_remote, source, archive_path, filename
                    )
                    await asyncio.to_thread(
                        prune_remote_backups, source, project_meta.project_name, keep_count
                    )
                    logger.info(
                        f"Scheduled backup uploaded for {project_meta.project_name} to {source}."
                    )
                except Exception as err:
                    logger.exception(err)
                    logger.warning(
                        f"Scheduled backup failed for {project_meta.project_name} to {source}: {err}"
                    )
        finally:
            remove_temp_file(archive_path)


def configure_backup_scheduler() -> None:
    try:
        scheduler.remove_job(BACKUP_JOB_ID)
    except Exception:
        pass

    if not bool(getattr(Config, "backup_auto_enabled", False)):
        return

    interval_hours = _normalize_interval_hours(
        getattr(Config, "backup_auto_interval_hours", 24)
    )
    scheduler.add_job(
        run_scheduled_backup_once,
        "interval",
        hours=interval_hours,
        id=BACKUP_JOB_ID,
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        next_run_time=datetime.now(timezone.utc),
    )
