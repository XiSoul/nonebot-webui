import os
from pathlib import Path, PurePosixPath
from typing import Any, Dict, List

import tomlkit
from nb_cli.config.parser import CONFIG_FILE, CONFIG_FILE_ENCODING

from nb_cli_plugin_webui.app.config import Config
from nb_cli_plugin_webui.app.utils.container import is_docker_runtime

from .schemas import ProjectTomlDetail


def _normalize_string_list(items: Any) -> List[str]:
    if not isinstance(items, list):
        return []

    result: List[str] = []
    seen = set()
    for item in items:
        value = str(item).strip()
        if not value or value in seen:
            continue
        seen.add(value)
        result.append(value.replace("\\", "/"))
    return result


def _normalize_adapters(items: Any) -> List[Dict[str, str]]:
    if not isinstance(items, list):
        return []

    adapters: List[Dict[str, str]] = []
    for item in items:
        if isinstance(item, dict):
            adapter = {str(k): str(v) for k, v in item.items() if v is not None}
            if adapter:
                adapters.append(adapter)
            continue

        module_name = str(item).strip()
        if not module_name:
            continue
        adapters.append(
            {
                "module_name": module_name,
                "name": module_name,
                "project_link": module_name,
            }
        )
    return adapters


def _discover_plugin_dirs(working_dir: Path, project_name: str) -> List[str]:
    candidates = [
        "src/plugins",
        "plugins",
        f"{working_dir.name}/plugins",
    ]
    if project_name:
        candidates.append(f"{project_name}/plugins")

    result: List[str] = []
    seen = set()
    for candidate in candidates:
        normalized = candidate.strip().replace("\\", "/")
        if not normalized or normalized in seen:
            continue
        if (working_dir / normalized).is_dir():
            seen.add(normalized)
            result.append(normalized)
    return result


def _safe_resolve(path: Path) -> Path:
    try:
        return path.expanduser().resolve()
    except Exception:
        return path.expanduser().absolute()


def _known_project_roots() -> List[Path]:
    roots: List[Path] = []
    seen = set()
    for raw_root in (str(getattr(Config, "base_dir", "") or "").strip(), "/external-projects"):
        if not raw_root:
            continue
        path = _safe_resolve(Path(raw_root))
        normalized = str(path).replace("\\", "/").casefold()
        if normalized in seen:
            continue
        seen.add(normalized)
        roots.append(path)
    return roots


def _append_unique_path(paths: List[Path], seen: set, path: Path) -> None:
    normalized = str(_safe_resolve(path)).replace("\\", "/").casefold()
    if normalized in seen:
        return
    seen.add(normalized)
    paths.append(path)


def _is_absolute_like(value: str) -> bool:
    return value.startswith("/") or value.startswith("\\") or bool(
        len(value) >= 2 and value[1] == ":"
    )


def _append_relative_project_candidates(
    candidates: List[Path], seen: set, normalized_input: str
) -> None:
    cleaned = normalized_input.strip()
    while cleaned.startswith("./"):
        cleaned = cleaned[2:]
    if not cleaned:
        return

    relative_parts = [part for part in PurePosixPath(cleaned).parts if part not in {"."}]
    if not relative_parts:
        return
    if any(part == ".." for part in relative_parts):
        return

    relative_path = Path(*relative_parts)
    first_part = relative_parts[0]

    for root in _known_project_roots():
        _append_unique_path(candidates, seen, root / relative_path)
        if relative_path.name == CONFIG_FILE:
            _append_unique_path(candidates, seen, (root / relative_path).parent)
        if first_part == root.name:
            _append_unique_path(candidates, seen, root.parent / relative_path)
            if relative_path.name == CONFIG_FILE:
                _append_unique_path(
                    candidates, seen, (root.parent / relative_path).parent
                )


def resolve_nonebot_project_dir(project_dir: str) -> Path:
    raw_value = str(project_dir or "").strip()
    if not raw_value:
        return Path(raw_value)

    normalized_input = raw_value.replace("\\", "/")
    is_absolute_input = _is_absolute_like(normalized_input)
    provided_path = Path(os.path.expanduser(normalized_input))
    provided_name = PurePosixPath(normalized_input).name

    candidates: List[Path] = []
    seen = set()

    if is_absolute_input:
        _append_unique_path(candidates, seen, provided_path)
        if provided_path.name == CONFIG_FILE:
            _append_unique_path(candidates, seen, provided_path.parent)

        current = provided_path
        while True:
            if current.parent == current:
                break
            current = current.parent
            _append_unique_path(candidates, seen, current)
    else:
        _append_relative_project_candidates(candidates, seen, normalized_input)
    if is_absolute_input and is_docker_runtime():
        for root in _known_project_roots():
            if provided_name:
                _append_unique_path(candidates, seen, root / provided_name)

    for candidate in candidates:
        resolved_candidate = _safe_resolve(candidate)
        config_path = resolved_candidate / CONFIG_FILE
        if resolved_candidate.is_dir() and config_path.is_file():
            return resolved_candidate

        if not resolved_candidate.is_dir():
            continue

        try:
            child_dirs = [
                child
                for child in resolved_candidate.iterdir()
                if child.is_dir() and (child / CONFIG_FILE).is_file()
            ]
        except OSError:
            continue
        if len(child_dirs) == 1:
            return _safe_resolve(child_dirs[0])

    raise FileNotFoundError(CONFIG_FILE)


def get_nonebot_info_from_toml(working_dir: Path) -> ProjectTomlDetail:
    path = working_dir / CONFIG_FILE
    if not path.is_file():
        raise FileNotFoundError
    data = tomlkit.loads(path.read_text(encoding=CONFIG_FILE_ENCODING))

    project_name = data.get("project", dict()).get("name", str())
    tool_detail = data.get("tool", dict())

    nonebot_info = tool_detail.get("nonebot", dict())
    adapters = _normalize_adapters(nonebot_info.get("adapters", list()))
    plugins = _normalize_string_list(nonebot_info.get("plugins", list()))
    plugin_dirs = _normalize_string_list(nonebot_info.get("plugin_dirs", list()))
    discovered_plugin_dirs = _discover_plugin_dirs(working_dir, project_name)
    builtin_plugins = _normalize_string_list(
        nonebot_info.get("builtin_plugins", list())
    )

    return ProjectTomlDetail(
        project_name=project_name,
        resolved_project_dir=str(_safe_resolve(working_dir)).replace("\\", "/"),
        adapters=adapters,
        plugins=plugins,
        plugin_dirs=plugin_dirs,
        discovered_plugin_dirs=discovered_plugin_dirs,
        builtin_plugins=builtin_plugins,
    )
