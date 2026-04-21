import re
import json
import ast
from pathlib import Path
from typing import Any, Dict, List, Optional

from nb_cli.handlers import get_default_python

from nb_cli_plugin_webui.app.utils.process import run_python_script

from . import templates


def _findall(pattern, string) -> str:
    matches = re.findall(pattern, string)
    return matches[0] if matches else str()


def _loads_json_or_literal(content: str, default: Any):
    raw = (content or "").strip()
    if not raw:
        return default

    for parser in (json.loads, ast.literal_eval):
        try:
            return parser(raw)
        except Exception:
            continue
    return default


async def get_nonebot_loaded_plugins(
    config_file: Path, python_path: Optional[str] = None
) -> List[str]:
    if python_path is None:
        python_path = await get_default_python()

    cwd = config_file.parent
    t = templates.get_template("scripts/nonebot/get_nonebot_loaded_plugins.py.jinja")
    raw_content = await run_python_script(
        python_path, await t.render_async(toml_path=config_file), cwd
    )

    plugins = _findall(r"nonebot_plugins:\s*(.*)", raw_content).split(",")
    return [plugin.strip() for plugin in plugins if plugin.strip()]


async def get_nonebot_loaded_config(
    cwd: Optional[Path] = None, python_path: Optional[str] = None
):
    if python_path is None:
        python_path = await get_default_python()

    t = templates.get_template("scripts/nonebot/get_nonebot_loaded_config.py.jinja")
    raw_content = await run_python_script(python_path, await t.render_async(), cwd)

    config = _loads_json_or_literal(
        _findall(r"nonebot_loaded_config:\s*(.*)", raw_content), default={}
    )
    return config if isinstance(config, dict) else {}


async def get_nonebot_self_config_schema(
    cwd: Optional[Path] = None, python_path: Optional[str] = None
):
    if python_path is None:
        python_path = await get_default_python()

    t = templates.get_template(
        "scripts/nonebot/get_nonebot_self_config_schema.py.jinja"
    )
    raw_content = await run_python_script(python_path, await t.render_async(), cwd)

    schema = _loads_json_or_literal(
        _findall(r"nonebot_self_config_schema:\s*(.*)", raw_content), default={}
    )
    return schema if isinstance(schema, dict) else {}


async def get_nonebot_plugin_config_schema(
    plugin: str, cwd: Optional[Path] = None, python_path: Optional[str] = None
):
    if python_path is None:
        python_path = await get_default_python()

    t = templates.get_template(
        "scripts/nonebot/get_nonebot_plugin_config_schema.py.jinja"
    )
    raw_content = await run_python_script(
        python_path, await t.render_async(plugin=plugin), cwd
    )

    schema = _loads_json_or_literal(
        _findall(r"nonebot_plugin_config_schema:\s*(.*)", raw_content), default={}
    )
    return schema if isinstance(schema, dict) else {}


async def get_nonebot_plugin_metadata(
    plugin: str, cwd: Optional[Path] = None, python_path: Optional[str] = None
) -> Dict[str, Any]:
    if python_path is None:
        python_path = await get_default_python()

    t = templates.get_template("scripts/nonebot/get_nonebot_plugin_metadata.py.jinja")
    raw_content = await run_python_script(
        python_path, await t.render_async(plugin=plugin), cwd
    )
    metadata = _loads_json_or_literal(
        _findall(r"nonebot_plugin_metadata:\s*(.*)", raw_content),
        default={},
    )

    if not isinstance(metadata, dict):
        metadata = {}

    metadata.setdefault("module_name", plugin)
    metadata.setdefault("name", plugin)
    metadata.setdefault("config", {})
    return metadata
