from typing import Dict, List

from fastapi import APIRouter, HTTPException, Query, status

from nb_cli_plugin_webui.app.config import CONFIG_FILE_PATH, Config
from nb_cli_plugin_webui.app.schemas import GenericResponse
from nb_cli_plugin_webui.app.utils.container import (
    is_docker_runtime,
    ContainerRuntimeSettings,
    apply_container_runtime_config,
    benchmark_container_source_presets,
    test_container_runtime_connectivity,
)

from .schemas import (
    ContainerRuntimeConnectivityRequest,
    ContainerRuntimeConnectivityResponse,
    ContainerRuntimePresetBenchmarkRequest,
    ContainerRuntimePresetBenchmarkResponse,
    ContainerRuntimeProfileApplyRequest,
    ContainerRuntimeProfileItem,
    ContainerRuntimeProfileListResponse,
    ContainerRuntimeProfileSaveRequest,
    ContainerRuntimeSettingsUpdate,
    ContainerRuntimeSettingsResponse,
)

router = APIRouter(tags=["system"])


def _normalize_text(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def _settings_to_map(settings: ContainerRuntimeSettings) -> Dict[str, str]:
    return {
        "http_proxy": settings.http_proxy,
        "https_proxy": settings.https_proxy,
        "all_proxy": settings.all_proxy,
        "no_proxy": settings.no_proxy,
        "debian_mirror": settings.debian_mirror,
        "pip_index_url": settings.pip_index_url,
        "pip_extra_index_url": settings.pip_extra_index_url,
        "pip_trusted_host": settings.pip_trusted_host,
    }


def _to_settings(data: ContainerRuntimeSettingsUpdate) -> ContainerRuntimeSettings:
    return ContainerRuntimeSettings(
        http_proxy=_normalize_text(data.http_proxy),
        https_proxy=_normalize_text(data.https_proxy),
        all_proxy=_normalize_text(data.all_proxy),
        no_proxy=_normalize_text(data.no_proxy),
        debian_mirror=_normalize_text(data.debian_mirror),
        pip_index_url=_normalize_text(data.pip_index_url),
        pip_extra_index_url=_normalize_text(data.pip_extra_index_url),
        pip_trusted_host=_normalize_text(data.pip_trusted_host),
    )


def _read_runtime_profiles() -> List[Dict[str, str]]:
    raw_profiles = Config.container_runtime_profiles
    if not isinstance(raw_profiles, list):
        return []

    profiles: List[Dict[str, str]] = []
    profile_index: Dict[str, int] = {}
    for item in raw_profiles:
        if not isinstance(item, dict):
            continue

        name = _normalize_text(item.get("name", ""))
        if not name:
            continue

        settings = ContainerRuntimeSettings(
            http_proxy=_normalize_text(item.get("http_proxy", "")),
            https_proxy=_normalize_text(item.get("https_proxy", "")),
            all_proxy=_normalize_text(item.get("all_proxy", "")),
            no_proxy=_normalize_text(item.get("no_proxy", "")),
            debian_mirror=_normalize_text(item.get("debian_mirror", "")),
            pip_index_url=_normalize_text(item.get("pip_index_url", "")),
            pip_extra_index_url=_normalize_text(item.get("pip_extra_index_url", "")),
            pip_trusted_host=_normalize_text(item.get("pip_trusted_host", "")),
        )
        profile_data = {"name": name, **_settings_to_map(settings)}

        existed_index = profile_index.get(name)
        if existed_index is None:
            profile_index[name] = len(profiles)
            profiles.append(profile_data)
        else:
            profiles[existed_index] = profile_data

    return profiles


def _store_runtime_profiles(profiles: List[Dict[str, str]]) -> None:
    Config.container_runtime_profiles = profiles
    Config.store(CONFIG_FILE_PATH)


def _profile_to_settings(profile: Dict[str, str]) -> ContainerRuntimeSettings:
    return ContainerRuntimeSettings(
        http_proxy=profile.get("http_proxy", ""),
        https_proxy=profile.get("https_proxy", ""),
        all_proxy=profile.get("all_proxy", ""),
        no_proxy=profile.get("no_proxy", ""),
        debian_mirror=profile.get("debian_mirror", ""),
        pip_index_url=profile.get("pip_index_url", ""),
        pip_extra_index_url=profile.get("pip_extra_index_url", ""),
        pip_trusted_host=profile.get("pip_trusted_host", ""),
    )


def _apply_runtime_settings_to_config(settings: ContainerRuntimeSettings) -> None:
    Config.container_http_proxy = settings.http_proxy
    Config.container_https_proxy = settings.https_proxy
    Config.container_all_proxy = settings.all_proxy
    Config.container_no_proxy = settings.no_proxy
    Config.container_debian_mirror = settings.debian_mirror
    Config.container_pip_index_url = settings.pip_index_url
    Config.container_pip_extra_index_url = settings.pip_extra_index_url
    Config.container_pip_trusted_host = settings.pip_trusted_host


@router.get(
    "/container/runtime",
    response_model=GenericResponse[ContainerRuntimeSettingsResponse],
)
async def get_container_runtime_settings() -> GenericResponse[ContainerRuntimeSettingsResponse]:
    settings = ContainerRuntimeSettings.from_config()
    return GenericResponse(
        detail=ContainerRuntimeSettingsResponse(
            is_docker=is_docker_runtime(),
            http_proxy=settings.http_proxy,
            https_proxy=settings.https_proxy,
            all_proxy=settings.all_proxy,
            no_proxy=settings.no_proxy,
            debian_mirror=settings.debian_mirror,
            pip_index_url=settings.pip_index_url,
            pip_extra_index_url=settings.pip_extra_index_url,
            pip_trusted_host=settings.pip_trusted_host,
        )
    )


@router.put("/container/runtime", response_model=GenericResponse[str])
async def update_container_runtime_settings(
    data: ContainerRuntimeSettingsUpdate,
) -> GenericResponse[str]:
    settings = _to_settings(data)
    _apply_runtime_settings_to_config(settings)

    Config.store(CONFIG_FILE_PATH)

    if is_docker_runtime():
        apply_container_runtime_config(force=True)

    return GenericResponse(detail="success")


@router.post(
    "/container/runtime/test",
    response_model=GenericResponse[ContainerRuntimeConnectivityResponse],
)
async def test_runtime_settings_connectivity(
    data: ContainerRuntimeConnectivityRequest,
) -> GenericResponse[ContainerRuntimeConnectivityResponse]:
    result = await test_container_runtime_connectivity(
        _to_settings(data), mode=_normalize_text(data.mode) or "quick"
    )
    return GenericResponse(detail=ContainerRuntimeConnectivityResponse(**result))


@router.post(
    "/container/runtime/preset/benchmark",
    response_model=GenericResponse[ContainerRuntimePresetBenchmarkResponse],
)
async def benchmark_runtime_presets(
    data: ContainerRuntimePresetBenchmarkRequest,
) -> GenericResponse[ContainerRuntimePresetBenchmarkResponse]:
    proxy_settings = ContainerRuntimeSettings(
        http_proxy=_normalize_text(data.http_proxy),
        https_proxy=_normalize_text(data.https_proxy),
        all_proxy=_normalize_text(data.all_proxy),
        no_proxy=_normalize_text(data.no_proxy),
    )
    result = await benchmark_container_source_presets(proxy_settings)
    return GenericResponse(detail=ContainerRuntimePresetBenchmarkResponse(results=result))


@router.get(
    "/container/runtime/profile/list",
    response_model=GenericResponse[ContainerRuntimeProfileListResponse],
)
async def list_runtime_profiles() -> GenericResponse[ContainerRuntimeProfileListResponse]:
    profiles = [ContainerRuntimeProfileItem(**item) for item in _read_runtime_profiles()]
    return GenericResponse(detail=ContainerRuntimeProfileListResponse(profiles=profiles))


@router.post("/container/runtime/profile/save", response_model=GenericResponse[str])
async def save_runtime_profile(
    data: ContainerRuntimeProfileSaveRequest,
) -> GenericResponse[str]:
    name = _normalize_text(data.name)
    if not name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Profile name cannot be empty.",
        )

    profile_data = {"name": name, **_settings_to_map(_to_settings(data))}
    profiles = _read_runtime_profiles()
    profile_index = next(
        (index for index, item in enumerate(profiles) if item["name"] == name),
        None,
    )
    if profile_index is None:
        profiles.append(profile_data)
    else:
        profiles[profile_index] = profile_data

    _store_runtime_profiles(profiles)
    return GenericResponse(detail="success")


@router.post("/container/runtime/profile/apply", response_model=GenericResponse[str])
async def apply_runtime_profile(
    data: ContainerRuntimeProfileApplyRequest,
) -> GenericResponse[str]:
    name = _normalize_text(data.name)
    if not name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Profile name cannot be empty.",
        )

    profile = next((item for item in _read_runtime_profiles() if item["name"] == name), None)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found.",
        )

    _apply_runtime_settings_to_config(_profile_to_settings(profile))
    Config.store(CONFIG_FILE_PATH)

    if is_docker_runtime():
        apply_container_runtime_config(force=True)

    return GenericResponse(detail="success")


@router.delete("/container/runtime/profile/delete", response_model=GenericResponse[str])
async def delete_runtime_profile(name: str = Query("")) -> GenericResponse[str]:
    normalized_name = _normalize_text(name)
    if not normalized_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Profile name cannot be empty.",
        )

    profiles = _read_runtime_profiles()
    new_profiles = [item for item in profiles if item["name"] != normalized_name]
    if len(new_profiles) == len(profiles):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found.",
        )

    _store_runtime_profiles(new_profiles)
    return GenericResponse(detail="success")
