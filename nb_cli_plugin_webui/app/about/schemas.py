from typing import Optional

from pydantic import BaseModel


class VersionLatestInfo(BaseModel):
    version: Optional[str] = None
    tag: Optional[str] = None
    commit: Optional[str] = None
    commit_short: Optional[str] = None
    html_url: Optional[str] = None
    checked_at: Optional[str] = None


class VersionInfoResponse(BaseModel):
    package_name: str
    version: str
    commit: Optional[str] = None
    commit_short: Optional[str] = None
    build_time: Optional[str] = None
    repository: str
    branch: str
    latest: Optional[VersionLatestInfo] = None
    update_available: Optional[bool] = None
    status: str
    error: Optional[str] = None
