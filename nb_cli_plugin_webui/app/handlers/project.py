import json
from pathlib import Path
import re
from typing import Any, Dict, List

import tomlkit
from nb_cli.config import ConfigManager
from dotenv import set_key, dotenv_values
from tomlkit.toml_document import TOMLDocument
from pydantic import BaseModel, ValidationError
from nb_cli.exceptions import ProjectNotFoundError
from nb_cli.config import SimpleInfo as CliSimpleInfo
from nb_cli.config.parser import CONFIG_FILE_ENCODING

from nb_cli_plugin_webui.app.handlers import get_pkg_version
from nb_cli_plugin_webui.app.utils.storage import get_data_file
from nb_cli_plugin_webui.app.utils.openapi import resolve_references
from nb_cli_plugin_webui.app.models.base import Plugin, ModuleInfo, NoneBotProjectMeta
from .nonebot import (
    get_nonebot_loaded_plugins,
    get_nonebot_plugin_metadata,
    get_nonebot_plugin_config_schema,
)

PROJECT_DATA_FILE = "project.json"
PROJECT_DATA_PATH = get_data_file(PROJECT_DATA_FILE)
PROJECT_DATA_ENCODING = "utf-8"


class NoneBotProjectList(BaseModel):
    __root__: Dict[str, NoneBotProjectMeta]


class NoneBotProjectManager:
    meta_modifiable_keys = {
        "project_name",
        "mirror_url",
        "plugin_dirs",
        "use_run_script",
        "run_script_name",
        "bot_use_global_proxy",
        "bot_http_proxy",
        "bot_https_proxy",
        "bot_all_proxy",
        "bot_no_proxy",
        "bot_proxy_protocol",
        "bot_proxy_host",
        "bot_proxy_port",
        "bot_proxy_username",
        "bot_proxy_password",
        "bot_proxy_apply_target",
    }

    def __init__(self, *, project_id: str) -> None:
        self.project_id = project_id

        # TODO: 需考虑的错误处理
        try:
            self.read()
        except Exception:
            self.config_manager = ConfigManager(use_venv=True)

    @classmethod
    def _normalize_project_payload(cls, payload: Any) -> Dict[str, Any]:
        if payload is None:
            return {}

        if isinstance(payload, dict):
            data = payload
            while (
                isinstance(data, dict)
                and set(data.keys()) == {"__root__"}
                and isinstance(data.get("__root__"), dict)
            ):
                data = data["__root__"]
            return data

        raise ValueError("project data must be a JSON object")

    @classmethod
    def _load(cls) -> NoneBotProjectList:
        try:
            raw_text = PROJECT_DATA_PATH.read_text(encoding=PROJECT_DATA_ENCODING).strip()
        except FileNotFoundError as err:
            raise err

        if not raw_text:
            return NoneBotProjectList(__root__={})

        try:
            raw_payload = json.loads(raw_text)
        except json.JSONDecodeError as err:
            raise ValueError(f"invalid project data JSON: {err.msg}") from err

        normalized_payload = cls._normalize_project_payload(raw_payload)
        project_list = NoneBotProjectList(__root__=normalized_payload)

        if raw_payload != normalized_payload:
            PROJECT_DATA_PATH.write_text(
                project_list.json(), encoding=PROJECT_DATA_ENCODING
            )

        return project_list

    @classmethod
    def get_project(cls) -> Dict[str, NoneBotProjectMeta]:
        return cls._load().__root__

    def store(self, data: NoneBotProjectMeta) -> None:
        if not PROJECT_DATA_PATH.exists():
            file = NoneBotProjectList(__root__={self.project_id: data})
        else:
            file = self._load()
            file.__root__[self.project_id] = data

        PROJECT_DATA_PATH.write_text(file.json(), encoding="utf-8")

    def read(self) -> NoneBotProjectMeta:
        try:
            load = self._load()
            data = load.__root__
        except FileNotFoundError:
            raise FileNotFoundError(f"{PROJECT_DATA_FILE} Not found")
        info = data.get(self.project_id)
        if info is None:
            raise ProjectNotFoundError
        self.config_manager = ConfigManager(
            working_dir=Path(info.project_dir), use_venv=True
        )
        self._refresh_discovered_plugin_dirs(info)

        return info

    @staticmethod
    def _refresh_discovered_plugin_dirs(info: NoneBotProjectMeta) -> None:
        from nb_cli_plugin_webui.app.project.utils import get_nonebot_info_from_toml

        project_dir = Path(info.project_dir)
        if not project_dir.is_dir():
            info.discovered_plugin_dirs = []
            return

        try:
            detail = get_nonebot_info_from_toml(project_dir)
        except Exception:
            return

        info.discovered_plugin_dirs = detail.discovered_plugin_dirs

    def get_toml_data(self) -> TOMLDocument:
        return tomlkit.parse(
            self.config_manager.config_file.read_text(encoding=CONFIG_FILE_ENCODING)
        )

    def write_toml_data(self, data: TOMLDocument) -> None:
        self.config_manager.config_file.write_text(
            tomlkit.dumps(data), encoding=CONFIG_FILE_ENCODING
        )

    async def sync_from_project_toml(self) -> None:
        from nb_cli_plugin_webui.app.project.utils import get_nonebot_info_from_toml

        data = self.read()
        project_detail = get_nonebot_info_from_toml(Path(data.project_dir))

        if project_detail.project_name:
            data.project_name = project_detail.project_name

        current_adapters = {adapter.module_name: adapter for adapter in data.adapters}
        adapters: List[ModuleInfo] = []
        for adapter in project_detail.adapters:
            module_name = adapter.get("module_name", "unknown")
            if module_name in current_adapters:
                adapters.append(current_adapters[module_name].copy(update=adapter))
                continue
            adapters.append(ModuleInfo.parse_obj(adapter))

        data.adapters = adapters
        current_plugins = {plugin.module_name: plugin for plugin in data.plugins}
        data.plugins = [
            current_plugins.get(plugin_name, self._build_placeholder_plugin(plugin_name))
            for plugin_name in project_detail.plugins
        ]
        data.plugin_dirs = project_detail.plugin_dirs
        data.discovered_plugin_dirs = project_detail.discovered_plugin_dirs
        data.builtin_plugins = project_detail.builtin_plugins
        data.use_env = self._resolve_use_env(Path(data.project_dir))
        data.drivers = self._resolve_driver_metadata(
            self._get_configured_driver_names(data.use_env)
        )
        self.store(data)
        await self.update_plugin_config()

    async def add_project(
        self,
        *,
        project_name: str,
        project_dir: Path,
        mirror_url: str,
        adapters: List[ModuleInfo] = list(),
        drivers: List[ModuleInfo] = list(),
        plugins: List[Plugin] = list(),
        plugin_dirs: List[str] = list(),
        discovered_plugin_dirs: List[str] = list(),
        builtin_plugins: List[str] = list(),
        use_env: str = ".env",
    ) -> None:
        self.store(
            NoneBotProjectMeta(
                project_id=self.project_id,
                project_name=project_name,
                project_dir=str(project_dir.absolute()),
                mirror_url=mirror_url,
                adapters=adapters,
                drivers=drivers,
                plugins=plugins,
                plugin_dirs=plugin_dirs,
                discovered_plugin_dirs=discovered_plugin_dirs,
                builtin_plugins=builtin_plugins,
                use_env=use_env,
            )
        )
        await self.update_plugin_config()

    def remove_project(self) -> None:
        data = self._load()
        data.__root__.pop(self.project_id)
        PROJECT_DATA_PATH.write_text(data.json(), encoding="utf-8")

    def modify_meta(self, k: str, v: Any) -> None:
        data = self.read()
        if k in self.meta_modifiable_keys:
            setattr(data, k, v)
            self.store(data)

    @staticmethod
    def _normalize_driver_name(driver_name: str) -> str:
        name = (driver_name or "").strip()
        if not name:
            return ""

        if name.startswith("nonebot2[") and name.endswith("]"):
            name = name[len("nonebot2[") : -1]
        if name.startswith("nonebot.drivers."):
            name = name[len("nonebot.drivers.") :]
        if name.startswith("~"):
            name = name[1:]
        return name.strip()

    def _build_driver_expr(self, names: List[str]) -> str:
        normalized = [self._normalize_driver_name(name) for name in names]
        normalized = [name for name in normalized if name]
        if not normalized:
            return ""

        dedup: List[str] = list(dict.fromkeys(normalized))
        server_candidates = ["fastapi", "quart", "aiohttp", "sanic", "tornado"]
        mixin_candidates = ["httpx", "websockets"]

        base = next((name for name in dedup if name in server_candidates), dedup[0])
        mixins = [name for name in dedup if name != base and name in mixin_candidates]
        remain = [name for name in dedup if name != base and name not in mixins]
        ordered = [base, *mixins, *remain]
        return "+".join(f"~{name}" for name in ordered)

    @classmethod
    def _resolve_driver_metadata(cls, driver_names: List[str]) -> List[ModuleInfo]:
        from nb_cli_plugin_webui.app.models.types import ModuleType
        from nb_cli_plugin_webui.app.store.dependencies import get_store_items

        store_driver_data = get_store_items(ModuleType.DRIVER, is_search=False)
        store_driver_map: Dict[str, ModuleInfo] = {}
        for driver in store_driver_data:
            normalized_name = cls._normalize_driver_name(driver.module_name)
            if normalized_name and normalized_name not in store_driver_map:
                store_driver_map[normalized_name] = driver

        result: List[ModuleInfo] = []
        seen = set()
        for driver_name in driver_names:
            normalized_name = cls._normalize_driver_name(driver_name)
            if not normalized_name or normalized_name in seen:
                continue

            seen.add(normalized_name)
            driver = store_driver_map.get(normalized_name)
            if driver is not None:
                result.append(ModuleInfo.parse_obj(driver.dict()))
                continue

            result.append(
                ModuleInfo(
                    module_name=f"~{normalized_name}",
                    name=normalized_name,
                    project_link=f"nonebot2[{normalized_name}]",
                )
            )

        return result

    @staticmethod
    def _build_placeholder_plugin(plugin_name: str) -> Plugin:
        return Plugin(
            module_name=plugin_name,
            name=plugin_name,
            project_link=plugin_name,
            config={},
        )

    @staticmethod
    def _normalize_distribution_name(value: str) -> str:
        return re.sub(r"[-_.]+", "-", (value or "").strip()).strip("-").lower()

    @classmethod
    def _build_plugin_store_lookup(cls) -> Dict[str, Plugin]:
        from nb_cli_plugin_webui.app.models.types import ModuleType
        from nb_cli_plugin_webui.app.store.dependencies import get_store_items

        lookup: Dict[str, Plugin] = {}
        for plugin in get_store_items(ModuleType.PLUGIN, is_search=False):
            candidates = {
                (plugin.module_name or "").strip(),
                (plugin.module_name or "").split(".", 1)[0].strip(),
                cls._normalize_distribution_name(plugin.project_link),
                cls._normalize_distribution_name(plugin.module_name),
                cls._normalize_distribution_name(plugin.name),
            }
            for candidate in candidates:
                if candidate and candidate not in lookup:
                    lookup[candidate] = Plugin.parse_obj(plugin.dict())
        return lookup

    @classmethod
    def _lookup_plugin_store_metadata(
        cls, plugin: Plugin, lookup: Dict[str, Plugin]
    ) -> Plugin | None:
        candidates = [
            (plugin.module_name or "").strip(),
            (plugin.module_name or "").split(".", 1)[0].strip(),
            cls._normalize_distribution_name(plugin.project_link),
            cls._normalize_distribution_name(plugin.module_name),
            cls._normalize_distribution_name(plugin.name),
        ]
        for candidate in candidates:
            if candidate and candidate in lookup:
                return lookup[candidate]
        return None

    @classmethod
    def _merge_plugin_store_metadata(
        cls, plugin: Plugin, store_plugin: Plugin | None
    ) -> Plugin:
        if store_plugin is None:
            return plugin

        merged = plugin.dict()
        fallback_fields = (
            "project_link",
            "name",
            "desc",
            "author",
            "homepage",
            "usage",
            "tags",
            "is_official",
        )
        for field in fallback_fields:
            current_value = merged.get(field)
            if current_value not in ("", "unknown", None, [], {}):
                continue
            fallback_value = getattr(store_plugin, field, None)
            if fallback_value in ("", "unknown", None, [], {}):
                continue
            merged[field] = fallback_value

        if not merged.get("extra"):
            merged["extra"] = store_plugin.extra

        return Plugin.parse_obj(merged)

    @staticmethod
    def _resolve_use_env(project_dir: Path) -> str:
        base_env = project_dir / ".env"
        if not base_env.is_file():
            return ".env"

        env_name = str(dotenv_values(base_env).get("ENVIRONMENT", "")).strip()
        if not env_name:
            return ".env"

        env_file_name = f".env.{env_name}"
        if (project_dir / env_file_name).is_file():
            return env_file_name
        return ".env"

    def _get_configured_driver_names(self, env_name: str) -> List[str]:
        data = self.read()
        env_path = Path(data.project_dir) / env_name
        if not env_path.is_file():
            return []

        raw_drivers = str(dotenv_values(env_path).get("DRIVER") or "").strip()
        if not raw_drivers:
            return []

        return [driver_name for driver_name in raw_drivers.split("+") if driver_name]

    def add_adapter(self, adapter: ModuleInfo) -> None:
        self.config_manager.add_adapter(
            CliSimpleInfo(name=adapter.name, module_name=adapter.module_name)
        )
        data = self.read()
        data.adapters.append(adapter)
        self.store(data)

    def remove_adapter(self, adapter: ModuleInfo) -> None:
        self.config_manager.remove_adapter(
            CliSimpleInfo(name=adapter.name, module_name=adapter.module_name)
        )
        data = self.read()
        for adapter in data.adapters:
            if adapter.module_name == adapter.module_name:
                data.adapters.remove(adapter)
                break
        self.store(data)

    async def update_plugin_config(self) -> None:
        data = self.read()
        config_file = self.config_manager.config_file
        existing_plugins = {plugin.module_name: plugin for plugin in data.plugins}
        plugin_store_lookup = self._build_plugin_store_lookup()

        try:
            plugins = await get_nonebot_loaded_plugins(
                config_file, self.config_manager.python_path
            )
        except Exception:
            return
        plugin_names = list(dict.fromkeys([*plugins, *existing_plugins.keys()]))
        cwd = config_file.parent

        data.plugins = list()
        for plugin in plugin_names:
            try:
                plugin_metadata = await get_nonebot_plugin_metadata(
                    plugin, cwd, self.config_manager.python_path
                )
            except Exception:
                current_plugin = existing_plugins.get(plugin)
                plugin_metadata = (
                    current_plugin.dict()
                    if current_plugin is not None
                    else self._build_placeholder_plugin(plugin).dict()
                )
            try:
                plugin_config_schema = await get_nonebot_plugin_config_schema(
                    plugin, cwd, self.config_manager.python_path
                )
                plugin_config = resolve_references(plugin_config_schema)
            except Exception:
                plugin_config = plugin_metadata.get("config", {})

            plugin_metadata["config"] = plugin_config
            try:
                pkg_version = await get_pkg_version(plugin, self.config_manager.python_path)
                plugin_metadata["version"] = pkg_version
            except Exception:
                plugin_metadata["version"] = plugin_metadata.get("version", "unknown")

            metadata = Plugin.parse_obj(plugin_metadata)
            if metadata.module_name == "unknown":
                metadata.module_name = plugin
            metadata = self._merge_plugin_store_metadata(
                metadata,
                self._lookup_plugin_store_metadata(metadata, plugin_store_lookup),
            )

            data.plugins.append(metadata)

        self.store(data)

    async def add_plugin(self, plugin: Plugin) -> None:
        self.config_manager.add_plugin(plugin.module_name)

        await self.update_plugin_config()

    def remove_plugin(self, plugin: Plugin) -> None:
        self.config_manager.remove_plugin(plugin.module_name)

        data = self.read()
        cache_list = data.plugins[:]
        for i in cache_list:
            if i.module_name == plugin.module_name:
                data.plugins.remove(i)
        self.store(data)

    def add_builtin_plugin(self, plugin: str) -> None:
        self.config_manager.add_builtin_plugin(plugin)

        data = self.read()
        data.builtin_plugins.append(plugin)
        self.store(data)

    def remove_builtin_plugin(self, plugin: str) -> None:
        self.config_manager.remove_builtin_plugin(plugin)

        data = self.read()
        data.builtin_plugins.remove(plugin)
        self.store(data)

    def add_driver(self, env: str, driver: ModuleInfo) -> None:
        data = self.read()

        env_path = Path(data.project_dir) / env
        env_data = dotenv_values(env_path)
        raw_drivers = env_data.get("DRIVER")
        names: List[str] = []
        if raw_drivers:
            names.extend(raw_drivers.split("+"))
        names.append(driver.module_name)
        set_key(env_path, "DRIVER", self._build_driver_expr(names))

        data.drivers.append(driver)
        self.store(data)

    def remove_driver(self, env: str, driver: ModuleInfo) -> None:
        data = self.read()

        env_path = Path(data.project_dir) / env
        env_data = dotenv_values(env_path)
        raw_drivers = env_data.get("DRIVER")
        if not raw_drivers:
            set_key(env_path, "DRIVER", str())
        else:
            current = [self._normalize_driver_name(item) for item in raw_drivers.split("+")]
            target = self._normalize_driver_name(driver.module_name)
            current = [item for item in current if item and item != target]
            set_key(env_path, "DRIVER", self._build_driver_expr(current))

        for i in data.drivers:
            if i.module_name == driver.module_name:
                data.drivers.remove(i)
                break
        self.store(data)

    def write_to_env(self, env: str, k: str, v: Any) -> None:
        data = self.read()
        env_path = Path(data.project_dir) / env
        if not env_path.is_file():
            env_path.write_text(str(), encoding="utf-8")
        key = str(k).strip()
        value = "" if v is None else str(v)

        content = env_path.read_text(encoding="utf-8")
        lines = content.splitlines()
        key_pattern = re.compile(rf"^\s*{re.escape(key)}\s*=", re.IGNORECASE)
        filtered_lines = [line for line in lines if not key_pattern.match(line)]
        filtered_lines.append(f"{key}={value}")
        env_path.write_text("\n".join(filtered_lines) + "\n", encoding="utf-8")
