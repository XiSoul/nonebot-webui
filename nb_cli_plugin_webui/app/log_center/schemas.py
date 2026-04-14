from typing import List, Literal

from pydantic import BaseModel

from nb_cli_plugin_webui.app.config import LogLevels


LogKind = Literal["webui", "instance"]


class GlobalLogSettingsResponse(BaseModel):
    min_level: LogLevels = LogLevels.DEBUG
    retention_days: int = 7
    available_levels: List[str] = []


class GlobalLogSettingsUpdateRequest(BaseModel):
    min_level: LogLevels = LogLevels.DEBUG
    retention_days: int = 7


class GlobalLogCatalogResponse(BaseModel):
    kind: LogKind
    dates: List[str] = []


class GlobalLogEntry(BaseModel):
    timestamp: str = ""
    level: str = "INFO"
    source: str = ""
    message: str = ""
    detail: str = ""
    project_id: str = ""
    project_name: str = ""


class GlobalLogEntriesResponse(BaseModel):
    kind: LogKind
    date: str = ""
    total: int = 0
    items: List[GlobalLogEntry] = []


class GlobalLogEventRequest(BaseModel):
    level: LogLevels = LogLevels.INFO
    message: str
    detail: str = ""
    source: str = "frontend"
    project_id: str = ""
    project_name: str = ""

