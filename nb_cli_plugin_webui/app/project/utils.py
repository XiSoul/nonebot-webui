from pathlib import Path
from typing import Any, Dict, List

import tomlkit
from nb_cli.config.parser import CONFIG_FILE, CONFIG_FILE_ENCODING

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
    builtin_plugins = _normalize_string_list(
        nonebot_info.get("builtin_plugins", list())
    )

    if not plugin_dirs:
        plugin_dirs = _discover_plugin_dirs(working_dir, project_name)

    return ProjectTomlDetail(
        project_name=project_name,
        adapters=adapters,
        plugins=plugins,
        plugin_dirs=plugin_dirs,
        builtin_plugins=builtin_plugins,
    )
