from typing import List

from pydantic import BaseModel


class ContainerRuntimeSettingsResponse(BaseModel):
    is_docker: bool
    http_proxy: str = ""
    https_proxy: str = ""
    all_proxy: str = ""
    no_proxy: str = ""
    debian_mirror: str = ""
    pip_index_url: str = ""
    pip_extra_index_url: str = ""
    pip_trusted_host: str = ""


class ContainerRuntimeSettingsUpdate(BaseModel):
    http_proxy: str = ""
    https_proxy: str = ""
    all_proxy: str = ""
    no_proxy: str = ""
    debian_mirror: str = ""
    pip_index_url: str = ""
    pip_extra_index_url: str = ""
    pip_trusted_host: str = ""


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
