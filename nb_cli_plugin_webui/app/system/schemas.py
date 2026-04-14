from typing import List

from pydantic import BaseModel


class ContainerRuntimeSettingsResponse(BaseModel):
    is_docker: bool
    proxy_url: str = ""
    http_proxy: str = ""
    https_proxy: str = ""
    all_proxy: str = ""
    no_proxy: str = ""
    debian_mirror: str = ""
    pip_index_url: str = ""
    pip_extra_index_url: str = ""
    pip_trusted_host: str = ""
    github_proxy_base_url: str = ""
    bot_http_proxy: str = ""
    bot_https_proxy: str = ""
    bot_all_proxy: str = ""
    bot_no_proxy: str = ""
    bot_proxy_protocol: str = "http"
    bot_proxy_host: str = ""
    bot_proxy_port: str = ""
    bot_proxy_username: str = ""
    bot_proxy_password: str = ""
    bot_proxy_apply_target: str = "http_https"
    bot_proxy_instances: str = ""


class ContainerRuntimeSettingsUpdate(BaseModel):
    proxy_url: str = ""
    http_proxy: str = ""
    https_proxy: str = ""
    all_proxy: str = ""
    no_proxy: str = ""
    debian_mirror: str = ""
    pip_index_url: str = ""
    pip_extra_index_url: str = ""
    pip_trusted_host: str = ""
    github_proxy_base_url: str = ""
    bot_http_proxy: str = ""
    bot_https_proxy: str = ""
    bot_all_proxy: str = ""
    bot_no_proxy: str = ""
    bot_proxy_protocol: str = "http"
    bot_proxy_host: str = ""
    bot_proxy_port: str = ""
    bot_proxy_username: str = ""
    bot_proxy_password: str = ""
    bot_proxy_apply_target: str = "http_https"
    bot_proxy_instances: str = ""


class ContainerRuntimeConnectivityRequest(ContainerRuntimeSettingsUpdate):
    mode: str = "quick"


class ContainerRuntimeConnectivityItem(BaseModel):
    name: str
    target: str
    ok: bool
    skipped: bool = False
    status_code: int = 0
    elapsed_ms: int = 0
    error: str = ""


class ContainerRuntimeConnectivityResponse(BaseModel):
    ok: bool
    results: List[ContainerRuntimeConnectivityItem]


class ContainerRuntimePresetBenchmarkRequest(BaseModel):
    proxy_url: str = ""
    http_proxy: str = ""
    https_proxy: str = ""
    all_proxy: str = ""
    no_proxy: str = ""


class ContainerRuntimePresetBenchmarkItem(BaseModel):
    preset_id: str
    preset_name: str
    ok: bool
    score_ms: int = 0
    debian_elapsed_ms: int = 0
    pip_elapsed_ms: int = 0
    error: str = ""


class ContainerRuntimePresetBenchmarkResponse(BaseModel):
    results: List[ContainerRuntimePresetBenchmarkItem]


class ContainerRuntimeProfileItem(ContainerRuntimeSettingsUpdate):
    name: str


class ContainerRuntimeProfileListResponse(BaseModel):
    profiles: List[ContainerRuntimeProfileItem]


class ContainerRuntimeProfileSaveRequest(ContainerRuntimeSettingsUpdate):
    name: str


class ContainerRuntimeProfileApplyRequest(BaseModel):
    name: str


class SecuritySettingsResponse(BaseModel):
    is_docker: bool
    service_host: str = ""
    service_port: int = 18080
    token_hint: str = ""
    token_mode: str = "permanent"
    random_token_expire_hours: int = 24
    token_expires_at: int = 0


class SecuritySettingsUpdateRequest(BaseModel):
    current_token: str = ""
    new_token: str = ""
    service_port: int = 18080
    token_mode: str = "permanent"
    random_token_expire_hours: int = 24


class SecuritySettingsUpdateResponse(BaseModel):
    token_changed: bool = False
    reauth_required: bool = False
    port_changed: bool = False
    restart_scheduled: bool = False
    service_port: int = 18080
    message: str = ""
    token_mode: str = "permanent"
    random_token_expire_hours: int = 24
    token_expires_at: int = 0
