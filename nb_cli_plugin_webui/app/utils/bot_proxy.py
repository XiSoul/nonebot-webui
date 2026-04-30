import os
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple
from urllib.parse import quote, urlparse

from nb_cli_plugin_webui.app.config import Config


def _normalize_text(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def _normalize_apply_target(value: str) -> str:
    normalized = _normalize_text(value).lower()
    if normalized in {"http_https", "all_proxy", "http_only", "https_only"}:
        return normalized
    return "http_https"


def _parse_target_instances(value: object) -> set[str]:
    raw = _normalize_text(value)
    if not raw:
        return set()
    normalized = raw.replace("\n", ",")
    return {item.strip() for item in normalized.split(",") if item.strip()}


def _build_proxy_url(
    protocol: str,
    host: str,
    port: str,
    username: str = "",
    password: str = "",
) -> str:
    protocol = _normalize_text(protocol).lower()
    host = _normalize_text(host)
    port = _normalize_text(port)
    username = _normalize_text(username)
    password = _normalize_text(password)
    if not protocol or not host or not port:
        return ""
    if not port.isdigit():
        return ""

    auth = ""
    if username or password:
        auth = f"{quote(username, safe='')}:{quote(password, safe='')}@"
    return f"{protocol}://{auth}{host}:{port}"


@dataclass
class BotProxySettings:
    http_proxy: str = ""
    https_proxy: str = ""
    all_proxy: str = ""
    no_proxy: str = ""
    proxy_protocol: str = "http"
    proxy_host: str = ""
    proxy_port: str = ""
    proxy_username: str = ""
    proxy_password: str = ""
    proxy_apply_target: str = "http_https"

    @classmethod
    def from_config(cls) -> "BotProxySettings":
        return cls(
            http_proxy=_normalize_text(Config.bot_http_proxy),
            https_proxy=_normalize_text(Config.bot_https_proxy),
            all_proxy=_normalize_text(Config.bot_all_proxy),
            no_proxy=_normalize_text(Config.bot_no_proxy),
            proxy_protocol=_normalize_text(Config.bot_proxy_protocol) or "http",
            proxy_host=_normalize_text(Config.bot_proxy_host),
            proxy_port=_normalize_text(Config.bot_proxy_port),
            proxy_username=_normalize_text(Config.bot_proxy_username),
            proxy_password=_normalize_text(Config.bot_proxy_password),
            proxy_apply_target=_normalize_apply_target(Config.bot_proxy_apply_target),
        )

    def build_proxy_url(self) -> str:
        return _build_proxy_url(
            self.proxy_protocol,
            self.proxy_host,
            self.proxy_port,
            self.proxy_username,
            self.proxy_password,
        )

    def has_custom_settings(self) -> bool:
        return bool(
            _normalize_text(self.http_proxy)
            or _normalize_text(self.https_proxy)
            or _normalize_text(self.all_proxy)
            or _normalize_text(self.no_proxy)
            or _normalize_text(self.proxy_host)
            or _normalize_text(self.proxy_port)
        )

    def resolve_proxy_urls(self) -> Dict[str, str]:
        http_proxy = _normalize_text(self.http_proxy)
        https_proxy = _normalize_text(self.https_proxy)
        all_proxy = _normalize_text(self.all_proxy)
        no_proxy = _normalize_text(self.no_proxy)

        generated = self.build_proxy_url()
        if generated:
            apply_target = _normalize_apply_target(self.proxy_apply_target)
            if apply_target == "all_proxy":
                all_proxy = all_proxy or generated
            elif apply_target == "http_only":
                http_proxy = http_proxy or generated
            elif apply_target == "https_only":
                https_proxy = https_proxy or generated
            else:
                http_proxy = http_proxy or generated
                https_proxy = https_proxy or generated

        return {
            "HTTP_PROXY": http_proxy,
            "HTTPS_PROXY": https_proxy,
            "ALL_PROXY": all_proxy,
            "NO_PROXY": no_proxy,
        }


@dataclass
class ProjectBotProxySettings(BotProxySettings):
    use_global_proxy: bool = True

    @classmethod
    def from_project_meta(cls, project_meta: Any) -> "ProjectBotProxySettings":
        return cls(
            use_global_proxy=bool(getattr(project_meta, "bot_use_global_proxy", True)),
            http_proxy=_normalize_text(getattr(project_meta, "bot_http_proxy", "")),
            https_proxy=_normalize_text(getattr(project_meta, "bot_https_proxy", "")),
            all_proxy=_normalize_text(getattr(project_meta, "bot_all_proxy", "")),
            no_proxy=_normalize_text(getattr(project_meta, "bot_no_proxy", "")),
            proxy_protocol=_normalize_text(
                getattr(project_meta, "bot_proxy_protocol", "")
            )
            or "http",
            proxy_host=_normalize_text(getattr(project_meta, "bot_proxy_host", "")),
            proxy_port=_normalize_text(getattr(project_meta, "bot_proxy_port", "")),
            proxy_username=_normalize_text(
                getattr(project_meta, "bot_proxy_username", "")
            ),
            proxy_password=_normalize_text(
                getattr(project_meta, "bot_proxy_password", "")
            ),
            proxy_apply_target=_normalize_apply_target(
                getattr(project_meta, "bot_proxy_apply_target", "")
            ),
        )


def _apply_proxy_mapping_to_env(env: Dict[str, str], mapping: Dict[str, str]) -> Dict[str, str]:
    for key, value in mapping.items():
        lower_key = key.lower()
        if value:
            env[key] = value
            env[lower_key] = value
        else:
            env.pop(key, None)
            env.pop(lower_key, None)
    return env


def _get_container_proxy_mapping() -> Dict[str, str]:
    proxy_url = _normalize_text(getattr(Config, "container_proxy_url", ""))
    http_proxy = _normalize_text(getattr(Config, "container_http_proxy", ""))
    https_proxy = _normalize_text(getattr(Config, "container_https_proxy", ""))
    all_proxy = _normalize_text(getattr(Config, "container_all_proxy", ""))
    no_proxy = _normalize_text(getattr(Config, "container_no_proxy", ""))

    if proxy_url:
        parsed = urlparse(proxy_url)
        if parsed.scheme.startswith("socks"):
            all_proxy = all_proxy or proxy_url
        else:
            http_proxy = http_proxy or proxy_url
            https_proxy = https_proxy or proxy_url

    return {
        "HTTP_PROXY": http_proxy,
        "HTTPS_PROXY": https_proxy,
        "ALL_PROXY": all_proxy,
        "NO_PROXY": no_proxy,
    }


def _has_any_proxy(mapping: Dict[str, str]) -> bool:
    return any(_normalize_text(value) for value in mapping.values())


def get_bot_proxy_env(
    base_env: Optional[Dict[str, str]] = None, project_meta: Optional[Any] = None
) -> Dict[str, str]:
    env = dict(base_env if base_env is not None else os.environ)

    if project_meta is not None:
        project_settings = ProjectBotProxySettings.from_project_meta(project_meta)
        if not project_settings.use_global_proxy:
            return _apply_proxy_mapping_to_env(env, project_settings.resolve_proxy_urls())

    settings = BotProxySettings.from_config()
    target_instances = _parse_target_instances(getattr(Config, "bot_proxy_instances", ""))
    if project_meta is not None and target_instances:
        project_name = _normalize_text(getattr(project_meta, "project_name", ""))
        if project_name not in target_instances:
            return env

    if settings.has_custom_settings():
        return _apply_proxy_mapping_to_env(env, settings.resolve_proxy_urls())

    # Backward compatibility: if only container runtime proxy is configured,
    # reuse it for bot/plugin runtime when the project inherits the global proxy.
    container_mapping = _get_container_proxy_mapping()
    if _has_any_proxy(container_mapping):
        return _apply_proxy_mapping_to_env(env, container_mapping)

    return env


def _is_socks_proxy_url(value: str) -> bool:
    scheme = urlparse(_normalize_text(value)).scheme.lower()
    return scheme.startswith("socks")


def get_pip_proxy_env(
    base_env: Optional[Dict[str, str]] = None, project_meta: Optional[Any] = None
) -> Tuple[Dict[str, str], bool]:
    env = get_bot_proxy_env(base_env=base_env, project_meta=project_meta)
    socks_proxy_disabled = False

    for key in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY"):
        value = _normalize_text(env.get(key) or env.get(key.lower()) or "")
        if not _is_socks_proxy_url(value):
            continue

        env.pop(key, None)
        env.pop(key.lower(), None)
        socks_proxy_disabled = True

    return env, socks_proxy_disabled
