import re
import ast
import json
from io import StringIO
from pathlib import Path
from typing import Any, Dict, List

from fastapi import BackgroundTasks, Body, Depends, APIRouter
from dotenv import dotenv_values
import tomlkit
from nb_cli.config.parser import CONFIG_FILE_ENCODING

from nb_cli_plugin_webui.app.logging import logger as log
from nb_cli_plugin_webui.app.models.types import ModuleType
from nb_cli_plugin_webui.app.models.base import NoneBotProjectMeta
from nb_cli_plugin_webui.app.utils.openapi import resolve_references
from nb_cli_plugin_webui.app.handlers import (
    NoneBotProjectManager,
    get_nonebot_loaded_config,
    get_nonebot_self_config_schema,
)

from .utils import config_child_parser
from ..dependencies import get_nonebot_project_manager
from ..service import (
    ensure_project_name_is_unique,
    ensure_project_port_is_unique,
    normalize_project_name,
    parse_project_port,
)
from ...process.service import restart_nonebot_project_if_running
from .exceptions import (
    EnvExists,
    EnvNotFound,
    ConfigNotFound,
    GetConfigError,
    ConfigParseError,
    BaseEnvCannotBeDeleted,
)
from .schemas import (
    ConfigType,
    GenericResponse,
    ConfigModuleType,
    ModuleConfigChild,
    ModuleConfigFather,
    ModuleConfigResponse,
    ModuleConfigUpdateRequest,
)

router = APIRouter()


async def _sync_project_and_restart_if_needed(
    project: NoneBotProjectManager,
    *,
    sync_project_toml: bool = False,
) -> None:
    try:
        if sync_project_toml:
            await project.sync_from_project_toml()
        await restart_nonebot_project_if_running(project)
    except Exception as err:
        project_id = getattr(project, "project_id", "unknown")
        log.exception(
            f"Background project config sync/restart failed for {project_id=}: {err}"
        )


@router.get("/env/list", response_model=GenericResponse[List[str]])
async def _get_project_env_list(
    project: NoneBotProjectManager = Depends(get_nonebot_project_manager),
) -> GenericResponse[List[str]]:
    """
    - 鑾峰彇 NoneBot 瀹炰緥涓殑鐜鏂囦欢鍒楄〃
    """
    project_meta = project.read()
    project_dir = Path(project_meta.project_dir)
    result = list()
    for i in project_dir.iterdir():
        if i.name.startswith(".env"):
            result.append(i.name)

    return GenericResponse(detail=result)


@router.post("/env/create", response_model=GenericResponse[str])
async def _create_project_env(
    env: str,
    project: NoneBotProjectManager = Depends(get_nonebot_project_manager),
) -> GenericResponse[str]:
    """
    - 鍒涘缓 NoneBot 瀹炰緥涓殑鐜鏂囦欢
    """
    project_meta = project.read()
    project_dir = Path(project_meta.project_dir)
    for i in project_dir.iterdir():
        if env == i.name:
            raise EnvExists()

    (project_dir / env).write_text(str(), encoding="utf-8")

    return GenericResponse(detail="success")


@router.delete("/env/delete", response_model=GenericResponse[str])
async def _delete_project_env(
    env: str, project: NoneBotProjectManager = Depends(get_nonebot_project_manager)
) -> GenericResponse[str]:
    """
    - 鍒犻櫎 NoneBot 瀹炰緥涓殑鐜鏂囦欢
    """
    if env == ".env":
        raise BaseEnvCannotBeDeleted()

    project_meta = project.read()
    project_dir = Path(project_meta.project_dir)
    for i in project_dir.iterdir():
        if env == i.name:
            i.unlink()
            return GenericResponse(detail="success")

    raise EnvNotFound()


@router.post("/env/use", response_model=GenericResponse[str])
async def _use_project_env(
    env: str, project: NoneBotProjectManager = Depends(get_nonebot_project_manager)
) -> GenericResponse[str]:
    """
    - 鍒囨崲 NoneBot 瀹炰緥鎵€搴旂敤鐨勭幆澧冩枃浠?
    """
    project_meta = project.read()
    project_dir = Path(project_meta.project_dir)
    for i in project_dir.iterdir():
        if env == i.name:
            env_name = str()
            _match = re.compile(r"(?<=\.env\.)[\w-]+")
            search = _match.search(env)
            if search:
                env_name = search.group()

            project.write_to_env(".env", "ENVIRONMENT", env_name)
            project_meta.use_env = env
            project.store(project_meta)

            return GenericResponse(detail="success")

    raise EnvNotFound()


@router.get("/meta/detail", response_model=ModuleConfigResponse)
async def _get_project_meta_config(
    project: NoneBotProjectManager = Depends(get_nonebot_project_manager),
) -> ModuleConfigResponse:
    """
    - 鑾峰彇 NoneBot 瀹炰緥鍦?.toml 涓殑閰嶇疆淇℃伅
    """
    project_meta = project.read()
    config_props = NoneBotProjectMeta.schema()["properties"]
    cache_list: List[ModuleConfigChild] = list()
    for prop in config_props:
        if prop not in project.meta_modifiable_keys:
            continue

        config_props[prop]["configured"] = getattr(project_meta, prop)
        detail = config_child_parser(prop, config_props[prop])
        cache_list.append(detail)

    result = ModuleConfigFather(
        title="Project Config",
        description="",
        name="project-meta",
        module_type=ConfigType.TOML,
        properties=cache_list,
    )

    return ModuleConfigResponse(detail=[result])


@router.get("/nonebot/detail", response_model=ModuleConfigResponse)
async def _get_project_nonebot_config(
    project: NoneBotProjectManager = Depends(get_nonebot_project_manager),
) -> ModuleConfigResponse:
    """
    - 鑾峰彇 NoneBot 瀹炰緥閰嶇疆淇℃伅
    """
    project_meta = project.read()

    try:
        config = await get_nonebot_loaded_config(
            Path(project_meta.project_dir), project.config_manager.python_path
        )
        config_schema = await get_nonebot_self_config_schema(
            Path(project_meta.project_dir), project.config_manager.python_path
        )
    except Exception as err:
        log.error(f"Get nonebot config failed: {err}")
        raise GetConfigError()

    if not isinstance(config, dict):
        config = {}
    if not isinstance(config_schema, dict):
        config_schema = {}
    config_schema.setdefault("properties", {})

    config_schema = resolve_references(config_schema)
    for i in config:
        if config_schema["properties"].get(i) is None or config.get(i) is None:
            continue

        config_schema["properties"][i]["configured"] = config[i]

    config_props = config_schema["properties"]
    cache_list: List[ModuleConfigChild] = list()
    for prop in config_props:
        detail = config_child_parser(prop, config_props[prop])
        cache_list.append(detail)

    result = ModuleConfigFather(
        title="NoneBot Config",
        description=config.get("description", str()),
        name="nonebot-config",
        module_type=ConfigType.PROJECT,
        properties=cache_list,
    )

    return ModuleConfigResponse(detail=[result])


@router.get("/nonebot/plugin/detail", response_model=ModuleConfigResponse)
async def _get_project_nonebot_plugin_config(
    project: NoneBotProjectManager = Depends(get_nonebot_project_manager),
) -> ModuleConfigResponse:
    """
    - 鑾峰彇 NoneBot 瀹炰緥涓墍鏈?NoneBot 鎻掍欢璁剧疆淇℃伅
    """
    project_meta = project.read()

    try:
        config = await get_nonebot_loaded_config(
            Path(project_meta.project_dir), project.config_manager.python_path
        )
    except Exception as err:
        log.error(f"Get nonebot config failed: {err}")
        raise GetConfigError()

    if not isinstance(config, dict):
        config = {}

    plugin_list = project_meta.plugins
    result: List[ModuleConfigFather] = list()
    for plugin in plugin_list:
        plugin_config = plugin.config
        if not plugin_config:
            continue

        cache_list: List[ModuleConfigChild] = list()
        for i in config:
            if plugin_config.get("properties") is None or plugin_config.get(i) is None:
                continue

            plugin_config["properties"][i]["configured"] = config[i]

        props = plugin_config.get("properties")
        if props is None:
            continue

        for prop in props:
            if _plugin_config := config.get(prop):
                props[prop]["configured"] = _plugin_config

            detail = config_child_parser(prop, props[prop])
            cache_list.append(detail)

        plugin_desc = str() if plugin.desc == "unknown" else plugin.desc

        plugin_detail = ModuleConfigFather(
            title=plugin.module_name,
            description=plugin_desc,
            name=plugin.module_name,
            module_type=ModuleType.PLUGIN,
            properties=cache_list,
        )
        result.append(plugin_detail)

    return ModuleConfigResponse(detail=result)


@router.post("/update", response_model=GenericResponse[str])
async def _update_project_config(
    module_type: ConfigModuleType,
    data: ModuleConfigUpdateRequest,
    background_tasks: BackgroundTasks,
    project: NoneBotProjectManager = Depends(get_nonebot_project_manager),
) -> GenericResponse[str]:
    """
    - 鏍规嵁妯″潡绫诲瀷鍙婄幆澧冩洿鏂伴厤缃俊鎭?
    - 璇存槑:
        * `module_type` 浠呬綔 WebUI 鏇存柊鑷韩瀛樺偍鐨勫疄渚嬩俊鎭紝涓嶄細褰卞搷瀹炰緥鏈綋
    """
    project_meta = project.read()
    target_config = data.k.split(":")[-1]

    if module_type == ConfigType.TOML:
        if data.conf_type == "boolean":
            setattr(data, "v", bool(data.v))
        elif target_config == "project_name":
            next_project_name = normalize_project_name(str(data.v))
            ensure_project_name_is_unique(
                next_project_name, exclude_project_id=project_meta.project_id
            )
            data.v = next_project_name

        project.modify_meta(target_config, data.v)

        toml_data = project.get_toml_data()
        table: Dict[str, Any] = toml_data.setdefault("tool", {}).setdefault(
            "nonebot", {}
        )
        table[data.k] = data.v
        project.write_toml_data(toml_data)
        background_tasks.add_task(_sync_project_and_restart_if_needed, project)

        return GenericResponse(detail="success")

    def modify_config():
        if target_config == "PORT":
            port = parse_project_port(data.v)
            if not port:
                raise ConfigParseError()
            ensure_project_port_is_unique(port, exclude_project_id=project_meta.project_id)

        data.v = str(data.v)
        if data.conf_type in {"object", "array", "boolean"}:
            try:
                data.v = ast.literal_eval(data.v)
            except Exception:
                raise ConfigParseError()
            v = json.dumps(data.v)
        else:
            v = data.v
        project.write_to_env(data.env, target_config, v)

        if module_type == ModuleType.PLUGIN:
            plugins = project_meta.plugins
            for plugin in plugins:
                config_detail = plugin.config
                props = config_detail.get("properties")
                if props is None:
                    continue
                for prop in props:
                    if target_config != prop:
                        continue
                    conf = props[prop].get("configured")
                    if conf is None:
                        raise ConfigNotFound()
                    plugin.config["properties"][prop]["configured"] = data.v
                    plugin.config["properties"][prop]["latest_change"] = data.env
                    project_meta.plugins = plugins
                    project.store(project_meta)

    project_dir = Path(project_meta.project_dir)
    for f in project_dir.iterdir():
        if data.env == f.name:
            modify_config()
            background_tasks.add_task(_sync_project_and_restart_if_needed, project)
            return GenericResponse(detail="success")

    raise EnvNotFound()


@router.get("/dotenv", response_model=GenericResponse[str])
async def get_dotenv_file(
    env: str,
    project: NoneBotProjectManager = Depends(get_nonebot_project_manager),
) -> GenericResponse[str]:
    """
    - 鑾峰彇鐜鏂囦欢鍐呭
    """
    project_meta = project.read()
    project_dir = Path(project_meta.project_dir)
    env_file = project_dir / env
    if not env_file.exists():
        raise EnvNotFound()

    return GenericResponse(detail=env_file.read_text(encoding="utf-8"))


@router.put("/dotenv", response_model=GenericResponse[str])
async def update_dotenv_file(
    background_tasks: BackgroundTasks,
    env: str = "",
    data: str = "",
    payload: Dict[str, str] = Body(default={}),
    project: NoneBotProjectManager = Depends(get_nonebot_project_manager),
) -> GenericResponse[str]:
    """
    - 鏇存柊鐜鏂囦欢鍐呭
    """
    env = env or payload.get("env", "")
    data = data or payload.get("data", "") or payload.get("detail", "")
    if not env:
        raise EnvNotFound()

    project_meta = project.read()
    project_dir = Path(project_meta.project_dir)
    env_file = project_dir / env
    if not env_file.exists():
        raise EnvNotFound()

    parsed_env = dotenv_values(stream=StringIO(data))
    port = parse_project_port(parsed_env.get("PORT"))
    if port:
        ensure_project_port_is_unique(port, exclude_project_id=project_meta.project_id)

    env_file.write_text(data, encoding="utf-8")
    background_tasks.add_task(_sync_project_and_restart_if_needed, project)

    return GenericResponse(detail="success")


@router.get("/pyproject", response_model=GenericResponse[str])
async def get_pyproject_file(
    project: NoneBotProjectManager = Depends(get_nonebot_project_manager),
) -> GenericResponse[str]:
    project.read()
    pyproject_file = project.config_manager.config_file
    if not pyproject_file.exists():
        raise ConfigNotFound()

    return GenericResponse(
        detail=pyproject_file.read_text(encoding=CONFIG_FILE_ENCODING)
    )


@router.put("/pyproject", response_model=GenericResponse[str])
async def update_pyproject_file(
    background_tasks: BackgroundTasks,
    data: str = "",
    payload: Dict[str, str] = Body(default={}),
    project: NoneBotProjectManager = Depends(get_nonebot_project_manager),
) -> GenericResponse[str]:
    data = data or payload.get("data", "") or payload.get("detail", "")
    if not data:
        raise ConfigParseError()
    project_meta = project.read()
    pyproject_file = project.config_manager.config_file
    if not pyproject_file.exists():
        raise ConfigNotFound()

    try:
        toml_data = tomlkit.parse(data)
    except Exception:
        raise ConfigParseError()

    next_project_name = str(toml_data.get("project", {}).get("name", "")).strip()
    if next_project_name:
        ensure_project_name_is_unique(
            next_project_name, exclude_project_id=project_meta.project_id
        )

    pyproject_file.write_text(data, encoding=CONFIG_FILE_ENCODING)
    background_tasks.add_task(
        _sync_project_and_restart_if_needed,
        project,
        sync_project_toml=True,
    )

    return GenericResponse(detail="success")



