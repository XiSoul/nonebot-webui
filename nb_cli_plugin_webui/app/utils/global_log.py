import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from nb_cli_plugin_webui.app.config import Config, LogLevels

from .storage import get_data_dir

LogKind = Literal["webui", "instance"]

LOG_CLEANUP_JOB_ID = "global-log-cleanup"
DATE_FORMAT = "%Y-%m-%d"
ANSI_ESCAPE_RE = re.compile(r"\x1B\[[0-?]*[ -/]*[@-~]")
CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0B-\x1F\x7F]")
PLACEHOLDER_ERROR_RE = re.compile(r"\b(undefined|null)\b", re.IGNORECASE)


def _normalize_text(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def _strip_ansi(value: str) -> str:
    return ANSI_ESCAPE_RE.sub("", value)


def _strip_control_chars(value: str) -> str:
    return CONTROL_CHAR_RE.sub("", value.replace("\r", ""))


def _normalize_placeholder_text(value: str) -> str:
    text = value.strip()
    if not text:
        return ""
    if PLACEHOLDER_ERROR_RE.fullmatch(text):
        return ""
    return PLACEHOLDER_ERROR_RE.sub("未知错误", text)


def _clean_log_text(value: object) -> str:
    normalized = _normalize_text(value)
    if not normalized:
        return ""
    normalized = _strip_ansi(normalized)
    normalized = _strip_control_chars(normalized)
    normalized = _normalize_placeholder_text(normalized)
    return normalized.strip()


def _normalize_level(value: object) -> str:
    if isinstance(value, LogLevels):
        return value.value
    normalized = _normalize_text(value).upper() or LogLevels.INFO.value
    valid = {level.value for level in LogLevels}
    return normalized if normalized in valid else LogLevels.INFO.value


def _level_priority(level: object) -> int:
    mapping = {
        LogLevels.DEBUG.value: 10,
        LogLevels.INFO.value: 20,
        LogLevels.WARNING.value: 30,
        LogLevels.ERROR.value: 40,
        LogLevels.CRITICAL.value: 50,
    }
    return mapping.get(_normalize_level(level), 20)


def _normalize_retention_days(value: object) -> int:
    try:
        days = int(value)
    except Exception:
        return 7
    return min(180, max(1, days))


def _sanitize_file_part(value: str, default: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9._-]+", "-", _normalize_text(value)).strip("-._")
    return cleaned or default


def _root_dir() -> Path:
    path = get_data_dir() / "global_logs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_global_logs_root(*, create: bool = True) -> Path:
    path = get_data_dir() / "global_logs"
    if create:
        path.mkdir(parents=True, exist_ok=True)
    return path


def build_instance_log_folder_name(project_id: str, project_name: str = "") -> str:
    return "%s-%s" % (
        _sanitize_file_part(project_id, "unknown"),
        _sanitize_file_part(project_name, "project"),
    )


def _webui_dir() -> Path:
    path = _root_dir() / "webui"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _instance_dir(project_id: str, project_name: str = "") -> Path:
    folder_name = build_instance_log_folder_name(project_id, project_name)
    path = _root_dir() / "instances" / folder_name
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_instance_log_directory(
    project_id: str, project_name: str = "", *, create: bool = True
) -> Path:
    path = get_global_logs_root(create=create) / "instances" / build_instance_log_folder_name(
        project_id, project_name
    )
    if create:
        path.mkdir(parents=True, exist_ok=True)
    return path


def _daily_log_path(kind: LogKind, *, project_id: str = "", project_name: str = "") -> Path:
    filename = datetime.now().strftime(DATE_FORMAT) + ".jsonl"
    if kind == "webui":
        return _webui_dir() / filename
    return _instance_dir(project_id, project_name) / filename


def _write_json_line(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def get_log_settings_response() -> Dict[str, object]:
    return {
        "min_level": _normalize_level(getattr(Config, "global_log_min_level", LogLevels.DEBUG)),
        "retention_days": _normalize_retention_days(
            getattr(Config, "global_log_retention_days", 7)
        ),
        "available_levels": [level.value for level in LogLevels],
    }


def infer_log_level(message: str, fallback: str = LogLevels.INFO.value) -> str:
    normalized = message.lower()
    if "traceback" in normalized or "exception" in normalized or "fatal" in normalized:
        return LogLevels.ERROR.value
    if "error" in normalized or "failed" in normalized:
        return LogLevels.ERROR.value
    if "warning" in normalized or "warn" in normalized:
        return LogLevels.WARNING.value
    if "debug" in normalized:
        return LogLevels.DEBUG.value
    return _normalize_level(fallback)


def append_log_entry(
    kind: LogKind,
    *,
    level: object,
    source: str,
    message: str,
    detail: str = "",
    project_id: str = "",
    project_name: str = "",
) -> None:
    payload = {
        "timestamp": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "kind": kind,
        "level": _normalize_level(level),
        "source": _clean_log_text(source) or kind,
        "message": _clean_log_text(message),
        "detail": _clean_log_text(detail),
        "project_id": _normalize_text(project_id),
        "project_name": _normalize_text(project_name),
    }
    if not payload["message"]:
        return

    path = _daily_log_path(
        kind, project_id=payload["project_id"], project_name=payload["project_name"]
    )
    _write_json_line(path, payload)


def append_webui_loguru_record(message: Any) -> None:
    record = message.record
    append_log_entry(
        "webui",
        level=record["level"].name,
        source="%s:%s:%s"
        % (record["module"], record["name"], record["line"]),
        message=str(record["message"]),
        detail=str(record["exception"] or ""),
    )


def append_ui_event(
    *,
    level: object,
    message: str,
    detail: str = "",
    source: str = "frontend",
    project_id: str = "",
    project_name: str = "",
) -> None:
    append_log_entry(
        "webui",
        level=level,
        source=source,
        message=message,
        detail=detail,
        project_id=project_id,
        project_name=project_name,
    )


def append_instance_log(
    *,
    project_id: str,
    project_name: str,
    message: str,
    detail: str = "",
    source: str = "instance",
    level: Optional[object] = None,
) -> None:
    append_log_entry(
        "instance",
        level=level or infer_log_level(message),
        source=source,
        message=message,
        detail=detail,
        project_id=project_id,
        project_name=project_name,
    )


def list_log_dates(kind: LogKind, project_id: str = "", project_name: str = "") -> List[str]:
    if kind == "webui":
        target_dir = _webui_dir()
    else:
        if not project_id:
            return []
        target_dir = _instance_dir(project_id, project_name)
    items = []
    for file_path in sorted(target_dir.glob("*.jsonl"), reverse=True):
        items.append(file_path.stem)
    return items


def read_log_entries(
    kind: LogKind,
    *,
    date: str,
    level: object = LogLevels.DEBUG,
    project_id: str = "",
    project_name: str = "",
    search: str = "",
) -> List[Dict[str, str]]:
    if kind == "webui":
        file_path = _webui_dir() / ("%s.jsonl" % date)
    else:
        if not project_id:
            return []
        file_path = _instance_dir(project_id, project_name) / ("%s.jsonl" % date)

    if not file_path.is_file():
        return []

    minimum_level = _level_priority(level)
    keyword = _normalize_text(search).lower()
    items: List[Dict[str, str]] = []
    with file_path.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            raw_line = raw_line.strip()
            if not raw_line:
                continue
            try:
                payload = json.loads(raw_line)
            except json.JSONDecodeError:
                continue

            if _level_priority(payload.get("level")) < minimum_level:
                continue

            message = _clean_log_text(payload.get("message", ""))
            detail = _clean_log_text(payload.get("detail", ""))
            source = _clean_log_text(payload.get("source", ""))
            if keyword and keyword not in " ".join([message, detail, source]).lower():
                continue

            items.append(
                {
                    "timestamp": str(payload.get("timestamp", "")),
                    "level": _normalize_level(payload.get("level")),
                    "source": source,
                    "message": message,
                    "detail": detail,
                    "project_id": str(payload.get("project_id", "")),
                    "project_name": str(payload.get("project_name", "")),
                }
            )

    items.sort(key=lambda item: item["timestamp"], reverse=True)
    return items


def cleanup_old_logs() -> None:
    retention_days = _normalize_retention_days(
        getattr(Config, "global_log_retention_days", 7)
    )
    cutoff = datetime.now().date() - timedelta(days=retention_days)
    root_dir = _root_dir()
    for file_path in root_dir.rglob("*.jsonl"):
        try:
            log_date = datetime.strptime(file_path.stem, DATE_FORMAT).date()
        except ValueError:
            continue
        if log_date < cutoff:
            file_path.unlink(missing_ok=True)

    for dir_path in sorted(root_dir.rglob("*"), reverse=True):
        if dir_path.is_dir():
            try:
                next(dir_path.iterdir())
            except StopIteration:
                dir_path.rmdir()
