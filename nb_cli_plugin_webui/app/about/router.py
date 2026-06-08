import os
import re
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version as package_version
from typing import Optional, Tuple

import httpx
from fastapi import APIRouter

from nb_cli_plugin_webui import get_version
from nb_cli_plugin_webui.app.schemas import GenericResponse

from .schemas import VersionInfoResponse, VersionLatestInfo

router = APIRouter(tags=["about"])

PACKAGE_DISTRIBUTIONS = ("nb-cli-plugin-webui-xisoul", "nb_cli_plugin_webui")
REPOSITORY_OWNER = "XiSoul"
REPOSITORY_NAME = "nonebot-webui"
REPOSITORY_URL = f"https://github.com/{REPOSITORY_OWNER}/{REPOSITORY_NAME}"
DEFAULT_BRANCH = "master"
GITHUB_API_BASE = "https://api.github.com"
_REVISION_FILE = "/usr/local/share/nb-cli-plugin-webui/revision"


def _read_text_file(path: str) -> Optional[str]:
    try:
        if os.path.isfile(path):
            value = open(path, "r", encoding="utf-8").read().strip()
            if value:
                return value
    except Exception:
        return None
    return None


def _get_package_name() -> str:
    for distribution in PACKAGE_DISTRIBUTIONS:
        try:
            package_version(distribution)
            return distribution
        except PackageNotFoundError:
            continue
    return PACKAGE_DISTRIBUTIONS[0]


def _get_commit() -> Optional[str]:
    candidates = [
        os.getenv("WEBUI_VCS_REF"),
        os.getenv("VCS_REF"),
        _read_text_file(_REVISION_FILE),
    ]
    for candidate in candidates:
        value = str(candidate or "").strip()
        if value and value.lower() != "unknown":
            return value
    return None


def _normalize_version(raw_version: Optional[str]) -> Optional[str]:
    if not raw_version:
        return None
    version = raw_version.strip()
    if version.startswith("v"):
        version = version[1:]
    return version.split("+", 1)[0] or None


def _version_tuple(raw_version: Optional[str]) -> Optional[Tuple[int, ...]]:
    normalized = _normalize_version(raw_version)
    if not normalized:
        return None
    match = re.match(r"^(\d+(?:\.\d+)*)", normalized)
    if not match:
        return None
    return tuple(int(part) for part in match.group(1).split("."))


def _compare_versions(current: Optional[str], latest: Optional[str]) -> Optional[int]:
    current_tuple = _version_tuple(current)
    latest_tuple = _version_tuple(latest)
    if current_tuple is None or latest_tuple is None:
        return None
    max_len = max(len(current_tuple), len(latest_tuple))
    current_tuple = current_tuple + (0,) * (max_len - len(current_tuple))
    latest_tuple = latest_tuple + (0,) * (max_len - len(latest_tuple))
    if current_tuple < latest_tuple:
        return -1
    if current_tuple > latest_tuple:
        return 1
    return 0


async def _fetch_latest_info() -> VersionLatestInfo:
    timeout = httpx.Timeout(8.0, connect=5.0)
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "nonebot-webui-version-check",
    }
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        release_response = await client.get(
            f"{GITHUB_API_BASE}/repos/{REPOSITORY_OWNER}/{REPOSITORY_NAME}/releases/latest",
            headers=headers,
        )
        latest_version: Optional[str] = None
        latest_tag: Optional[str] = None
        latest_url: Optional[str] = None
        if release_response.status_code == 200:
            release_payload = release_response.json()
            latest_tag = str(release_payload.get("tag_name") or "").strip() or None
            latest_version = _normalize_version(latest_tag)
            latest_url = str(release_payload.get("html_url") or "").strip() or None
        elif release_response.status_code not in (404, 403):
            release_response.raise_for_status()

        commit_response = await client.get(
            f"{GITHUB_API_BASE}/repos/{REPOSITORY_OWNER}/{REPOSITORY_NAME}/commits/{DEFAULT_BRANCH}",
            headers=headers,
        )
        commit_response.raise_for_status()
        commit_payload = commit_response.json()
        latest_commit = str(commit_payload.get("sha") or "").strip() or None
        commit_url = str(commit_payload.get("html_url") or "").strip() or None

    return VersionLatestInfo(
        version=latest_version,
        tag=latest_tag,
        commit=latest_commit,
        commit_short=latest_commit[:7] if latest_commit else None,
        html_url=latest_url or commit_url,
        checked_at=datetime.now(timezone.utc).isoformat(),
    )


@router.get("/version", response_model=GenericResponse[VersionInfoResponse])
async def get_about_version() -> GenericResponse[VersionInfoResponse]:
    current_version = get_version()
    current_commit = _get_commit()
    response = VersionInfoResponse(
        package_name=_get_package_name(),
        version=current_version,
        commit=current_commit,
        commit_short=current_commit[:7] if current_commit else None,
        build_time=os.getenv("WEBUI_BUILD_TIME") or os.getenv("BUILD_DATE"),
        repository=REPOSITORY_URL,
        branch=DEFAULT_BRANCH,
        status="ok",
    )

    try:
        latest = await _fetch_latest_info()
        response.latest = latest
        version_compare = _compare_versions(current_version, latest.version)
        if version_compare is not None:
            response.update_available = version_compare < 0
        elif current_commit and latest.commit:
            response.update_available = current_commit != latest.commit
        else:
            response.update_available = None
    except Exception as err:
        response.status = "error"
        response.error = str(err)

    return GenericResponse(detail=response)
