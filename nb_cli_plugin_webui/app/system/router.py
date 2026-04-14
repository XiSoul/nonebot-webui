import os
import time
from typing import Dict, List

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, status
from pydantic import SecretStr
from nb_cli_plugin_webui.app.config import (
    CONFIG_FILE_PATH,
    Config,
    DEFAULT_DOCKER_HOST,
    DEFAULT_DOCKER_PORT,
    DEFAULT_LOCAL_PORT,
    generate_secret_key,
)
from nb_cli_plugin_webui.app.schemas import GenericResponse
from nb_cli_plugin_webui.app.utils.container import (
    is_docker_runtime,
    ContainerRuntimeSettings,
    apply_container_runtime_config,
    benchmark_container_source_presets,
    test_container_runtime_connectivity,
)
from nb_cli_plugin_webui.app.utils.security import salt
from nb_cli_plugin_webui.app.utils.string_utils import check_string_complexity
from nb_cli_plugin_webui.app.auth.utils import (
    configure_random_login_token,
    get_login_token_expires_at,
    normalize_login_token_mode,
    normalize_random_token_expire_hours,
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
    SecuritySettingsResponse,
    SecuritySettingsUpdateRequest,
    SecuritySettingsUpdateResponse,
)

router = APIRouter(tags=["system"])


def _normalize_text(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def _is_socks_proxy_url(value: str) -> bool:
    normalized = _normalize_text(value).lower()
    return normalized.startswith(("socks4://", "socks4a://", "socks5://", "socks5h://"))


def _derive_proxy_url(http_proxy: str, https_proxy: str, all_proxy: str) -> str:
    normalized_http = _normalize_text(http_proxy)
    normalized_https = _normalize_text(https_proxy)
    normalized_all = _normalize_text(all_proxy)
    if normalized_http and normalized_https and normalized_http == normalized_https:
        return normalized_http
    return normalized_all or normalized_http or normalized_https


def _normalize_proxy_fields(
    proxy_url: str,
    http_proxy: str,
    https_proxy: str,
    all_proxy: str,
) -> Dict[str, str]:
    normalized_proxy_url = _normalize_text(proxy_url) or _derive_proxy_url(
        http_proxy, https_proxy, all_proxy
    )
    if normalized_proxy_url:
        return {
            "proxy_url": normalized_proxy_url,
            "http_proxy": normalized_proxy_url,
            "https_proxy": normalized_proxy_url,
            "all_proxy": normalized_proxy_url if _is_socks_proxy_url(normalized_proxy_url) else "",
        }

    return {
        "proxy_url": "",
        "http_proxy": _normalize_text(http_proxy),
        "https_proxy": _normalize_text(https_proxy),
        "all_proxy": _normalize_text(all_proxy),
    }


def _normalize_service_port(value: object) -> int:
    if isinstance(value, int):
        port = value
        text = str(value)
    else:
        text = _normalize_text(value)
        port = None

    if not text:
        text = DEFAULT_DOCKER_PORT if is_docker_runtime() else DEFAULT_LOCAL_PORT

    if port is None:
        try:
            port = int(text)
        except (TypeError, ValueError) as err:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Service port must be an integer.",
            ) from err

    if port < 1024 or port > 49151:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Service port must be between 1024 and 49151.",
        )

    return port


def _restart_process_after_response(delay_seconds: float = 1.0) -> None:
    time.sleep(delay_seconds)
    os._exit(0)


def _build_token_hint(token_mode: str, is_docker: bool) -> str:
    if token_mode == "random":
        if is_docker:
            return (
                "Random login tokens are written to Docker logs only. "
                "When the token expires, the system will automatically generate a new one and write it to Docker logs again."
            )
        return (
            "Random login tokens are written to service logs only. "
            "When the token expires, the system will automatically generate a new one and write it to the service logs again."
        )

    return (
        "Permanent login tokens do not expire automatically. "
        "Enter the current login token first before switching mode or updating the credential."
    )


def _settings_to_map(settings: ContainerRuntimeSettings) -> Dict[str, str]:
    proxy_fields = _normalize_proxy_fields(
        settings.proxy_url,
        settings.http_proxy,
        settings.https_proxy,
        settings.all_proxy,
    )
    return {
        "proxy_url": proxy_fields["proxy_url"],
        "http_proxy": proxy_fields["http_proxy"],
        "https_proxy": proxy_fields["https_proxy"],
        "all_proxy": proxy_fields["all_proxy"],
        "no_proxy": settings.no_proxy,
        "debian_mirror": settings.debian_mirror,
        "pip_index_url": settings.pip_index_url,
        "pip_extra_index_url": settings.pip_extra_index_url,
        "pip_trusted_host": settings.pip_trusted_host,
        "github_proxy_base_url": _normalize_text(Config.github_proxy_base_url),
        "bot_http_proxy": _normalize_text(Config.bot_http_proxy),
        "bot_https_proxy": _normalize_text(Config.bot_https_proxy),
        "bot_all_proxy": _normalize_text(Config.bot_all_proxy),
        "bot_no_proxy": _normalize_text(Config.bot_no_proxy),
        "bot_proxy_protocol": _normalize_text(Config.bot_proxy_protocol) or "http",
        "bot_proxy_host": _normalize_text(Config.bot_proxy_host),
        "bot_proxy_port": _normalize_text(Config.bot_proxy_port),
        "bot_proxy_username": _normalize_text(Config.bot_proxy_username),
        "bot_proxy_password": _normalize_text(Config.bot_proxy_password),
        "bot_proxy_apply_target": _normalize_text(Config.bot_proxy_apply_target)
        or "http_https",
        "bot_proxy_instances": _normalize_text(Config.bot_proxy_instances),
    }


def _to_settings(data: ContainerRuntimeSettingsUpdate) -> ContainerRuntimeSettings:
    proxy_fields = _normalize_proxy_fields(
        _normalize_text(data.proxy_url),
        _normalize_text(data.http_proxy),
        _normalize_text(data.https_proxy),
        _normalize_text(data.all_proxy),
    )
    return ContainerRuntimeSettings(
        proxy_url=proxy_fields["proxy_url"],
        http_proxy=proxy_fields["http_proxy"],
        https_proxy=proxy_fields["https_proxy"],
        all_proxy=proxy_fields["all_proxy"],
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
            proxy_url=_normalize_text(item.get("proxy_url", "")),
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
        profile_data.update(
            {
                "github_proxy_base_url": _normalize_text(
                    item.get("github_proxy_base_url", "")
                ),
                "bot_http_proxy": _normalize_text(item.get("bot_http_proxy", "")),
                "bot_https_proxy": _normalize_text(item.get("bot_https_proxy", "")),
                "bot_all_proxy": _normalize_text(item.get("bot_all_proxy", "")),
                "bot_no_proxy": _normalize_text(item.get("bot_no_proxy", "")),
                "bot_proxy_protocol": _normalize_text(
                    item.get("bot_proxy_protocol", "")
                )
                or "http",
                "bot_proxy_host": _normalize_text(item.get("bot_proxy_host", "")),
                "bot_proxy_port": _normalize_text(item.get("bot_proxy_port", "")),
                "bot_proxy_username": _normalize_text(
                    item.get("bot_proxy_username", "")
                ),
                "bot_proxy_password": _normalize_text(
                    item.get("bot_proxy_password", "")
                ),
                "bot_proxy_apply_target": _normalize_text(
                    item.get("bot_proxy_apply_target", "")
                )
                or "http_https",
                "bot_proxy_instances": _normalize_text(
                    item.get("bot_proxy_instances", "")
                ),
            }
        )

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
        proxy_url=profile.get("proxy_url", ""),
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
    proxy_fields = _normalize_proxy_fields(
        settings.proxy_url,
        settings.http_proxy,
        settings.https_proxy,
        settings.all_proxy,
    )
    Config.container_proxy_url = proxy_fields["proxy_url"]
    Config.container_http_proxy = proxy_fields["http_proxy"]
    Config.container_https_proxy = proxy_fields["https_proxy"]
    Config.container_all_proxy = proxy_fields["all_proxy"]
    Config.container_no_proxy = settings.no_proxy
    Config.container_debian_mirror = settings.debian_mirror
    Config.container_pip_index_url = settings.pip_index_url
    Config.container_pip_extra_index_url = settings.pip_extra_index_url
    Config.container_pip_trusted_host = settings.pip_trusted_host


def _apply_bot_proxy_settings_to_config(data: ContainerRuntimeSettingsUpdate) -> None:
    Config.bot_http_proxy = _normalize_text(data.bot_http_proxy)
    Config.bot_https_proxy = _normalize_text(data.bot_https_proxy)
    Config.bot_all_proxy = _normalize_text(data.bot_all_proxy)
    Config.bot_no_proxy = _normalize_text(data.bot_no_proxy)
    Config.bot_proxy_protocol = _normalize_text(data.bot_proxy_protocol) or "http"
    Config.bot_proxy_host = _normalize_text(data.bot_proxy_host)
    Config.bot_proxy_port = _normalize_text(data.bot_proxy_port)
    Config.bot_proxy_username = _normalize_text(data.bot_proxy_username)
    Config.bot_proxy_password = _normalize_text(data.bot_proxy_password)
    Config.bot_proxy_apply_target = (
        _normalize_text(data.bot_proxy_apply_target) or "http_https"
    )
    Config.bot_proxy_instances = _normalize_text(data.bot_proxy_instances)


@router.get("/security", response_model=GenericResponse[SecuritySettingsResponse])
async def get_security_settings() -> GenericResponse[SecuritySettingsResponse]:
    token_mode = normalize_login_token_mode(
        getattr(Config, "login_token_mode", "permanent")
    )
    random_token_expire_hours = normalize_random_token_expire_hours(
        getattr(Config, "login_token_random_expire_hours", 24)
    )
    is_docker = is_docker_runtime()
    return GenericResponse(
        detail=SecuritySettingsResponse(
            is_docker=is_docker,
            service_host=_normalize_text(Config.host)
            or (DEFAULT_DOCKER_HOST if is_docker else ""),
            service_port=_normalize_service_port(Config.port),
            token_hint=_build_token_hint(token_mode, is_docker),
            token_mode=token_mode,
            random_token_expire_hours=random_token_expire_hours,
            token_expires_at=get_login_token_expires_at() if token_mode == "random" else 0,
        )
    )


@router.put("/security", response_model=GenericResponse[SecuritySettingsUpdateResponse])
async def update_security_settings(
    data: SecuritySettingsUpdateRequest,
    background_tasks: BackgroundTasks,
) -> GenericResponse[SecuritySettingsUpdateResponse]:
    next_port = _normalize_service_port(data.service_port)
    current_token = _normalize_text(data.current_token)
    new_token = _normalize_text(data.new_token)
    next_token_mode = normalize_login_token_mode(data.token_mode)
    next_random_token_expire_hours = normalize_random_token_expire_hours(
        data.random_token_expire_hours
    )
    current_token_mode = normalize_login_token_mode(
        getattr(Config, "login_token_mode", "permanent")
    )
    current_random_token_expire_hours = normalize_random_token_expire_hours(
        getattr(Config, "login_token_random_expire_hours", 24)
    )

    token_changed = False
    token_settings_changed = bool(new_token)
    if next_token_mode != current_token_mode:
        token_settings_changed = True
    if (
        next_token_mode == "random"
        and next_random_token_expire_hours != current_random_token_expire_hours
    ):
        token_settings_changed = True

    if token_settings_changed:
        if not current_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current login token is required before updating login token settings.",
            )

        if not salt.verify_token(
            Config.salt.get_secret_value() + current_token,
            Config.hashed_token.get_secret_value(),
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Current login token is incorrect.",
            )

    if next_token_mode == "permanent":
        Config.login_token_mode = "permanent"
        Config.login_token_expires_at = 0
        Config.login_token_random_expire_hours = next_random_token_expire_hours

        if new_token:
            try:
                check_string_complexity(new_token)
            except Exception as err:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=str(err),
                ) from err

            Config.set_permanent_login_token(new_token)
            Config.secret_key = SecretStr(generate_secret_key())
            token_changed = True
        elif current_token_mode == "random":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Please enter a new permanent login token before switching from random mode.",
            )
    else:
        Config.login_token_mode = "random"
        Config.login_token_random_expire_hours = next_random_token_expire_hours

        if token_settings_changed or current_token_mode != "random":
            configure_random_login_token(
                expire_hours=next_random_token_expire_hours,
                reason="updated in security settings",
                persist=False,
            )
            token_changed = True

    current_port = _normalize_service_port(Config.port)
    port_changed = current_port != next_port
    Config.port = str(next_port)
    if is_docker_runtime():
        Config.host = DEFAULT_DOCKER_HOST

    Config.store(CONFIG_FILE_PATH)

    restart_scheduled = False
    message = "Security settings saved."
    if port_changed and is_docker_runtime():
        restart_scheduled = True
        message = (
            "Security settings saved. Docker service will restart shortly to apply the new port."
        )
        background_tasks.add_task(_restart_process_after_response)
    elif port_changed:
        message = "Security settings saved. Please restart the service to apply the new port."
    elif token_changed and next_token_mode == "random":
        message = (
            "Random login token has been regenerated and written to Docker/service logs. Please sign in again with the new token."
        )
    elif token_changed:
        message = "Login token updated. Please sign in again with the new token."

    return GenericResponse(
        detail=SecuritySettingsUpdateResponse(
            token_changed=token_changed,
            reauth_required=token_changed,
            port_changed=port_changed,
            restart_scheduled=restart_scheduled,
            service_port=next_port,
            message=message,
            token_mode=next_token_mode,
            random_token_expire_hours=next_random_token_expire_hours,
            token_expires_at=get_login_token_expires_at()
            if next_token_mode == "random"
            else 0,
        )
    )


@router.get(
    "/container/runtime",
    response_model=GenericResponse[ContainerRuntimeSettingsResponse],
)
async def get_container_runtime_settings() -> GenericResponse[ContainerRuntimeSettingsResponse]:
    settings = ContainerRuntimeSettings.from_config()
    proxy_fields = _normalize_proxy_fields(
        settings.proxy_url,
        settings.http_proxy,
        settings.https_proxy,
        settings.all_proxy,
    )
    return GenericResponse(
        detail=ContainerRuntimeSettingsResponse(
            is_docker=is_docker_runtime(),
            proxy_url=proxy_fields["proxy_url"],
            http_proxy=proxy_fields["http_proxy"],
            https_proxy=proxy_fields["https_proxy"],
            all_proxy=proxy_fields["all_proxy"],
            no_proxy=settings.no_proxy,
            debian_mirror=settings.debian_mirror,
            pip_index_url=settings.pip_index_url,
            pip_extra_index_url=settings.pip_extra_index_url,
            pip_trusted_host=settings.pip_trusted_host,
            github_proxy_base_url=_normalize_text(Config.github_proxy_base_url),
            bot_http_proxy=_normalize_text(Config.bot_http_proxy),
            bot_https_proxy=_normalize_text(Config.bot_https_proxy),
            bot_all_proxy=_normalize_text(Config.bot_all_proxy),
            bot_no_proxy=_normalize_text(Config.bot_no_proxy),
            bot_proxy_protocol=_normalize_text(Config.bot_proxy_protocol) or "http",
            bot_proxy_host=_normalize_text(Config.bot_proxy_host),
            bot_proxy_port=_normalize_text(Config.bot_proxy_port),
            bot_proxy_username=_normalize_text(Config.bot_proxy_username),
            bot_proxy_password=_normalize_text(Config.bot_proxy_password),
            bot_proxy_apply_target=_normalize_text(Config.bot_proxy_apply_target)
            or "http_https",
            bot_proxy_instances=_normalize_text(Config.bot_proxy_instances),
        )
    )


@router.put("/container/runtime", response_model=GenericResponse[str])
async def update_container_runtime_settings(
    data: ContainerRuntimeSettingsUpdate,
) -> GenericResponse[str]:
    settings = _to_settings(data)
    _apply_runtime_settings_to_config(settings)
    Config.github_proxy_base_url = _normalize_text(data.github_proxy_base_url)
    _apply_bot_proxy_settings_to_config(data)

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
    proxy_fields = _normalize_proxy_fields(
        _normalize_text(data.proxy_url),
        _normalize_text(data.http_proxy),
        _normalize_text(data.https_proxy),
        _normalize_text(data.all_proxy),
    )
    proxy_settings = ContainerRuntimeSettings(
        proxy_url=proxy_fields["proxy_url"],
        http_proxy=proxy_fields["http_proxy"],
        https_proxy=proxy_fields["https_proxy"],
        all_proxy=proxy_fields["all_proxy"],
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
    profile_data.update(
        {
            "github_proxy_base_url": _normalize_text(data.github_proxy_base_url),
            "bot_http_proxy": _normalize_text(data.bot_http_proxy),
            "bot_https_proxy": _normalize_text(data.bot_https_proxy),
            "bot_all_proxy": _normalize_text(data.bot_all_proxy),
            "bot_no_proxy": _normalize_text(data.bot_no_proxy),
            "bot_proxy_protocol": _normalize_text(data.bot_proxy_protocol) or "http",
            "bot_proxy_host": _normalize_text(data.bot_proxy_host),
            "bot_proxy_port": _normalize_text(data.bot_proxy_port),
            "bot_proxy_username": _normalize_text(data.bot_proxy_username),
            "bot_proxy_password": _normalize_text(data.bot_proxy_password),
            "bot_proxy_apply_target": _normalize_text(data.bot_proxy_apply_target)
            or "http_https",
            "bot_proxy_instances": _normalize_text(data.bot_proxy_instances),
        }
    )
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
    Config.github_proxy_base_url = _normalize_text(profile.get("github_proxy_base_url", ""))
    Config.bot_http_proxy = _normalize_text(profile.get("bot_http_proxy", ""))
    Config.bot_https_proxy = _normalize_text(profile.get("bot_https_proxy", ""))
    Config.bot_all_proxy = _normalize_text(profile.get("bot_all_proxy", ""))
    Config.bot_no_proxy = _normalize_text(profile.get("bot_no_proxy", ""))
    Config.bot_proxy_protocol = _normalize_text(profile.get("bot_proxy_protocol", "")) or "http"
    Config.bot_proxy_host = _normalize_text(profile.get("bot_proxy_host", ""))
    Config.bot_proxy_port = _normalize_text(profile.get("bot_proxy_port", ""))
    Config.bot_proxy_username = _normalize_text(profile.get("bot_proxy_username", ""))
    Config.bot_proxy_password = _normalize_text(profile.get("bot_proxy_password", ""))
    Config.bot_proxy_apply_target = (
        _normalize_text(profile.get("bot_proxy_apply_target", "")) or "http_https"
    )
    Config.bot_proxy_instances = _normalize_text(profile.get("bot_proxy_instances", ""))
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
