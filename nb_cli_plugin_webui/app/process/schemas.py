from typing import List

from pydantic import BaseModel


class TerminalSessionInfo(BaseModel):
    session_id: str
    title: str
    created_at: float
    is_active: bool
    is_running: bool
    log_key: str


class TerminalSessionListResponse(BaseModel):
    sessions: List[TerminalSessionInfo]
    active_session_id: str
