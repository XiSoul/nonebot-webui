import sys
import os
import time
import shutil
import asyncio
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import httpx
from nb_cli_plugin_webui.app.config import CONFIG_FILE_PATH, Config
from nb_cli_plugin_webui.app.logging import logger as log

_DOCKER_ENV_FLAG = "WEBUI_BUILD"

_PROXY_ENV_KEYS = {
    "HTTP_PROXY": ("WEBUI_HTTP_PROXY",),
    "HTTPS_PROXY": ("WEBUI_HTTPS_PROXY",),
    "ALL_PROXY": ("WEBUI_ALL_PROXY",),
    "NO_PROXY": ("WEBUI_NO_PROXY",),
}

_DEBIAN_MIRROR_KEYS = (
    "WEBUI_DEBIAN_MIRROR",
    "WEBUI_APT_MIRROR",
    "WEBUI_LINUX_MIRROR",
    "DEBIAN_MIRROR",
    "APT_MIRROR",
    "LINUX_MIRROR",
)

_PIP_SOURCE_KEYS = {
    "PIP_INDEX_URL": ("WEBUI_PIP_INDEX_URL",),
    "PIP_EXTRA_INDEX_URL": ("WEBUI_PIP_EXTRA_INDEX_URL",),
    "PIP_TRUSTED_HOST": ("WEBUI_PIP_TRUSTED_HOST",),
}

_SOURCE_PRESET_KEYS = (
    "WEBUI_SOURCE_PRESET",
    "WEBUI_MIRROR_PRESET",
    "SOURCE_PRESET",
    "MIRROR_PRESET",
)

_AUTO_BEST_PRESET_KEYS = (
    "WEBUI_AUTO_BEST_PRESET",
    "WEBUI_AUTO_BENCHMARK_PRESET",
)

_AUTO_BEST_PRESET_FORCE_KEYS = (
    "WEBUI_AUTO_BEST_PRESET_FORCE",
    "WEBUI_AUTO_BENCHMARK_PRESET_FORCE",
)

_DEBIAN_SOURCE_FILES = (
    Path("/etc/apt/sources.list"),
    Path("/etc/apt/sources.list.d/debian.sources"),
    Path("/etc/apt/sources.list.d/debian.list"),
)
_DEBIAN_SOURCE_BACKUP_SUFFIX = ".webui.bak"

_SOURCE_PRESETS: List[Dict[str, str]] = [
    {
        "id": "official",
        "name": "Official",
        "debian_mirror": "",
        "pip_index_url": "https://pypi.org/simple",
        "pip_trusted_host": "pypi.org files.pythonhosted.org",
    },
    {
        "id": "tuna",
        "name": "Tsinghua TUNA",
        "debian_mirror": "https://mirrors.tuna.tsinghua.edu.cn",
        "pip_index_url": "https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple",
        "pip_trusted_host": "mirrors.tuna.tsinghua.edu.cn",
    },
    {
        "id": "ustc",
        "name": "USTC",
        "debian_mirror": "https://mirrors.ustc.edu.cn",
        "pip_index_url": "https://mirrors.ustc.edu.cn/pypi/web/simple",
        "pip_trusted_host": "mirrors.ustc.edu.cn",
    },
    {
        "id": "aliyun",
        "name": "Aliyun",
        "debian_mirror": "https://mirrors.aliyun.com",
        "pip_index_url": "https://mirrors.aliyun.com/pypi/simple",
        "pip_trusted_host": "mirrors.aliyun.com",
    },
    {
        "id": "huawei",
        "name": "Huawei",
        "debian_mirror": "https://repo.huaweicloud.com",
        "pip_index_url": "https://repo.huaweicloud.com/repository/pypi/simple",
        "pip_trusted_host": "repo.huaweicloud.com",
    },
]

_SOURCE_PRESET_ALIASES = {
    "default": "official",
    "offical": "official",
    "tsinghua": "tuna",
    "tuna-tsinghua": "tuna",
    "ali": "aliyun",
    "huaweicloud": "huawei",
}


@dataclass
class ContainerRuntimeSettings:
    http_proxy: str = ""
    https_proxy: str = ""
    all_proxy: str = ""
    no_proxy: str = ""
    debian_mirror: str = ""
    pip_index_url: str = ""
    pip_extra_index_url: str = ""
    pip_trusted_host: str = ""

    @classmethod
    def from_config(cls) -> "ContainerRuntimeSettings":
        return cls(
            http_proxy=_normalize_text(Config.container_http_proxy),
            https_proxy=_normalize_text(Config.container_https_proxy),
            all_proxy=_normalize_text(Config.container_all_proxy),
            no_proxy=_normalize_text(Config.container_no_proxy),
            debian_mirror=_normalize_text(Config.container_debian_mirror),
            pip_index_url=_normalize_text(Config.container_pip_index_url),
            pip_extra_index_url=_normalize_text(Config.container_pip_extra_index_url),
            pip_trusted_host=_normalize_text(Config.container_pip_trusted_host),
        )


def is_docker_runtime() -> bool:
    return _DOCKER_ENV_FLAG in os.environ


def get_container_source_presets() -> List[Dict[str, str]]:
    return [dict(item) for item in _SOURCE_PRESETS]


def apply_container_runtime_config(force: bool = False) -> None:
    if not force and not is_docker_runtime():
        return

    settings = get_effective_container_settings()
    proxy_values = _apply_proxy_env(settings)
    _apply_apt_proxy(proxy_values)
    _apply_debian_mirror(settings.debian_mirror)
    _apply_pip_source(settings)


def get_effective_container_settings() -> ContainerRuntimeSettings:
    config_settings = ContainerRuntimeSettings.from_config()
    preset_settings = _resolve_source_preset_settings()
    preset_enabled = bool(preset_settings)

    explicit_pip_extra_index_url = _pick_env(
        (
            *_PIP_SOURCE_KEYS["PIP_EXTRA_INDEX_URL"],
            "PIP_EXTRA_INDEX_URL",
            "pip_extra_index_url",
        )
    )

    return ContainerRuntimeSettings(
        http_proxy=_pick_env(
            (*_PROXY_ENV_KEYS["HTTP_PROXY"], "HTTP_PROXY", "http_proxy")
        )
        or config_settings.http_proxy,
        https_proxy=_pick_env(
            (*_PROXY_ENV_KEYS["HTTPS_PROXY"], "HTTPS_PROXY", "https_proxy")
        )
        or config_settings.https_proxy,
        all_proxy=_pick_env((*_PROXY_ENV_KEYS["ALL_PROXY"], "ALL_PROXY", "all_proxy"))
        or config_settings.all_proxy,
        no_proxy=_pick_env((*_PROXY_ENV_KEYS["NO_PROXY"], "NO_PROXY", "no_proxy"))
        or config_settings.no_proxy,
        debian_mirror=_pick_env(_DEBIAN_MIRROR_KEYS)
        or _normalize_text(preset_settings.get("debian_mirror", ""))
        or config_settings.debian_mirror,
        pip_index_url=_pick_env(
            (*_PIP_SOURCE_KEYS["PIP_INDEX_URL"], "PIP_INDEX_URL", "pip_index_url")
        )
        or _normalize_text(preset_settings.get("pip_index_url", ""))
        or config_settings.pip_index_url,
        pip_extra_index_url=explicit_pip_extra_index_url
        or ("" if preset_enabled else config_settings.pip_extra_index_url),
        pip_trusted_host=_pick_env(
            (
                *_PIP_SOURCE_KEYS["PIP_TRUSTED_HOST"],
                "PIP_TRUSTED_HOST",
                "pip_trusted_host",
            )
        )
        or _normalize_text(preset_settings.get("pip_trusted_host", ""))
        or config_settings.pip_trusted_host,
    )


def _normalize_text(value: Optional[str]) -> str:
    return value.strip() if isinstance(value, str) else ""


def _pick_env(keys: Iterable[str]) -> Optional[str]:
    for key in keys:
        value = os.getenv(key)
        if value:
            return value.strip()
    return None


def _normalize_preset_id(value: str) -> str:
    normalized = _normalize_text(value).lower().replace(" ", "-").replace("_", "-")
    return _SOURCE_PRESET_ALIASES.get(normalized, normalized)


def _env_flag_enabled(keys: Iterable[str], default: bool = False) -> bool:
    truthy_values = {"1", "true", "yes", "on", "enable", "enabled"}
    falsy_values = {"0", "false", "no", "off", "disable", "disabled"}

    raw = _pick_env(keys)
    if raw is None:
        return default

    normalized = _normalize_text(raw).lower()
    if normalized in truthy_values:
        return True
    if normalized in falsy_values:
        return False
    return default


def _resolve_source_preset_settings() -> Dict[str, str]:
    raw_preset_id = _pick_env(_SOURCE_PRESET_KEYS)
    if not raw_preset_id:
        return {}

    preset_id = _normalize_preset_id(raw_preset_id)
    for preset in _SOURCE_PRESETS:
        if preset["id"] == preset_id:
            log.info(f"Container source preset enabled by env: {preset['id']}")
            return preset

    available = ", ".join(item["id"] for item in _SOURCE_PRESETS)
    log.warning(
        f"Unknown source preset {raw_preset_id!r}, available presets: {available}"
    )
    return {}


def _set_env(name: str, value: str) -> None:
    os.environ[name] = value
    os.environ[name.lower()] = value


def _unset_env(name: str) -> None:
    os.environ.pop(name, None)
    os.environ.pop(name.lower(), None)


def _apply_proxy_env(settings: ContainerRuntimeSettings) -> Dict[str, str]:
    result: Dict[str, str] = {}
    mapping = {
        "HTTP_PROXY": settings.http_proxy,
        "HTTPS_PROXY": settings.https_proxy,
        "ALL_PROXY": settings.all_proxy,
        "NO_PROXY": settings.no_proxy,
    }
    for env_name, value in mapping.items():
        value = _normalize_text(value)
        if value:
            _set_env(env_name, value)
            result[env_name] = value
        else:
            _unset_env(env_name)

    if result:
        enabled_proxy_names = [
            name for name in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY") if name in result
        ]
        log.info("Container proxy enabled: " + ", ".join(enabled_proxy_names))
    return result


def _apply_apt_proxy(proxy_values: Dict[str, str]) -> None:
    apt_proxy_file = Path("/etc/apt/apt.conf.d/99webui-proxy")
    lines = []
    if http_proxy := proxy_values.get("HTTP_PROXY"):
        lines.append(f'Acquire::http::Proxy "{http_proxy}";')
    if https_proxy := proxy_values.get("HTTPS_PROXY"):
        lines.append(f'Acquire::https::Proxy "{https_proxy}";')

    if not lines:
        if not apt_proxy_file.exists():
            return
        try:
            apt_proxy_file.unlink()
            log.info("Removed apt proxy config.")
        except OSError as err:
            log.warning(f"Failed to remove apt proxy config: {err}")
        return

    try:
        apt_proxy_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
        log.info(f"Updated apt proxy config: {apt_proxy_file}")
    except OSError as err:
        log.warning(f"Failed to write apt proxy config: {err}")


def _apply_debian_mirror(mirror: str) -> None:
    mirror = _normalize_text(mirror)
    if not mirror:
        _restore_debian_sources_from_backup()
        return

    mirror = mirror.rstrip("/")
    replacement_rules = {
        "http://deb.debian.org/debian": f"{mirror}/debian",
        "https://deb.debian.org/debian": f"{mirror}/debian",
        "http://security.debian.org/debian-security": f"{mirror}/debian-security",
        "https://security.debian.org/debian-security": f"{mirror}/debian-security",
        "http://ftp.debian.org/debian": f"{mirror}/debian",
        "https://ftp.debian.org/debian": f"{mirror}/debian",
    }

    updated_files = []
    for source_file in _DEBIAN_SOURCE_FILES:
        if not source_file.exists():
            continue

        try:
            content = source_file.read_text(encoding="utf-8")
        except OSError as err:
            log.warning(f"Failed to read apt source file {source_file}: {err}")
            continue

        new_content = content
        for old, new in replacement_rules.items():
            new_content = new_content.replace(old, new)

        if new_content == content:
            continue

        try:
            _ensure_debian_source_backup(source_file, content)
            source_file.write_text(new_content, encoding="utf-8")
            updated_files.append(str(source_file))
        except OSError as err:
            log.warning(f"Failed to write apt source file {source_file}: {err}")

    if updated_files:
        log.info("Updated Debian mirror for files: " + ", ".join(updated_files))
    else:
        log.info("Debian mirror variable is set, but no matching apt sources were updated.")


def _get_debian_source_backup_path(source_file: Path) -> Path:
    return Path(f"{source_file}{_DEBIAN_SOURCE_BACKUP_SUFFIX}")


def _ensure_debian_source_backup(source_file: Path, content: str) -> None:
    backup_file = _get_debian_source_backup_path(source_file)
    if backup_file.exists():
        return
    backup_file.write_text(content, encoding="utf-8")


def _restore_debian_sources_from_backup() -> None:
    restored_files: List[str] = []
    for source_file in _DEBIAN_SOURCE_FILES:
        backup_file = _get_debian_source_backup_path(source_file)
        if not backup_file.exists():
            continue

        try:
            source_file.write_text(backup_file.read_text(encoding="utf-8"), encoding="utf-8")
            restored_files.append(str(source_file))
        except OSError as err:
            log.warning(
                f"Failed to restore apt source file {source_file} from backup {backup_file}: {err}"
            )

    if restored_files:
        log.info("Restored Debian source files from backup: " + ", ".join(restored_files))


def _apply_pip_source(settings: ContainerRuntimeSettings) -> None:
    pip_values = {
        "PIP_INDEX_URL": _normalize_text(settings.pip_index_url),
        "PIP_EXTRA_INDEX_URL": _normalize_text(settings.pip_extra_index_url),
        "PIP_TRUSTED_HOST": _normalize_text(settings.pip_trusted_host),
    }

    for key, value in pip_values.items():
        if value:
            _set_env(key, value)
        else:
            _unset_env(key)

    pip_config_file = Path("/etc/pip.conf")
    lines = ["[global]"]
    if index_url := pip_values.get("PIP_INDEX_URL"):
        lines.append(f"index-url = {index_url}")
    if extra_index := pip_values.get("PIP_EXTRA_INDEX_URL"):
        lines.append(f"extra-index-url = {extra_index}")
    if trusted_host := pip_values.get("PIP_TRUSTED_HOST"):
        lines.append(f"trusted-host = {trusted_host}")

    if len(lines) == 1:
        if not pip_config_file.exists():
            return
        try:
            pip_config_file.unlink()
            log.info("Removed pip source config.")
        except OSError as err:
            log.warning(f"Failed to remove pip source config: {err}")
        return

    try:
        pip_config_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
        log.info(f"Updated pip source config: {pip_config_file}")
    except OSError as err:
        log.warning(f"Failed to write pip source config: {err}")


def _build_proxy_mapping(settings: ContainerRuntimeSettings) -> Optional[Dict[str, str]]:
    http_proxy = _normalize_text(settings.http_proxy)
    https_proxy = _normalize_text(settings.https_proxy)
    all_proxy = _normalize_text(settings.all_proxy)

    proxies: Dict[str, str] = {}
    if http_proxy:
        proxies["http://"] = http_proxy
    if https_proxy:
        proxies["https://"] = https_proxy
    if all_proxy:
        proxies.setdefault("http://", all_proxy)
        proxies.setdefault("https://", all_proxy)

    return proxies if proxies else None


def _build_connectivity_targets(
    settings: ContainerRuntimeSettings,
) -> List[Tuple[str, str]]:
    targets: List[Tuple[str, str]] = []
    debian_mirror = _normalize_text(settings.debian_mirror).rstrip("/")
    pip_index_url = _normalize_text(settings.pip_index_url)

    if debian_mirror:
        targets.append(
            (
                "debian_mirror",
                f"{debian_mirror}/debian/dists/stable/Release",
            )
        )
    if pip_index_url:
        targets.append(("pip_index", pip_index_url))

    return targets


def _build_runtime_env(settings: ContainerRuntimeSettings) -> Dict[str, str]:
    env = os.environ.copy()
    mapping = {
        "HTTP_PROXY": settings.http_proxy,
        "HTTPS_PROXY": settings.https_proxy,
        "ALL_PROXY": settings.all_proxy,
        "NO_PROXY": settings.no_proxy,
    }
    for key, value in mapping.items():
        value = _normalize_text(value)
        if value:
            env[key] = value
            env[key.lower()] = value
        else:
            env.pop(key, None)
            env.pop(key.lower(), None)
    return env


def _make_result(
    name: str,
    target: str,
    ok: bool,
    status_code: int = 0,
    elapsed_ms: int = 0,
    error: str = "",
    skipped: bool = False,
) -> Dict[str, Any]:
    return {
        "name": name,
        "target": target,
        "ok": bool(ok),
        "skipped": bool(skipped),
        "status_code": int(status_code),
        "elapsed_ms": int(elapsed_ms),
        "error": error,
    }


async def _http_probe(
    client: httpx.AsyncClient,
    *,
    name: str,
    target: str,
    timeout_error: str = "request timeout",
) -> Dict[str, Any]:
    start = time.perf_counter()
    try:
        response = await client.get(target)
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        return _make_result(
            name=name,
            target=target,
            ok=response.status_code < 400,
            status_code=int(response.status_code),
            elapsed_ms=elapsed_ms,
        )
    except Exception as err:
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        err_msg = timeout_error if isinstance(err, asyncio.TimeoutError) else str(err)
        return _make_result(
            name=name,
            target=target,
            ok=False,
            elapsed_ms=elapsed_ms,
            error=err_msg,
        )


async def _run_deep_apt_update(settings: ContainerRuntimeSettings) -> Dict[str, Any]:
    if not sys.platform.startswith("linux"):
        return _make_result(
            name="apt_update",
            target="apt-get update",
            ok=True,
            skipped=True,
            error="non-linux platform",
        )

    if hasattr(os, "geteuid") and os.geteuid() != 0:
        return _make_result(
            name="apt_update",
            target="apt-get update",
            ok=True,
            skipped=True,
            error="requires root privileges",
        )

    mirror = _normalize_text(settings.debian_mirror).rstrip("/")
    if not mirror:
        return _make_result(
            name="apt_update",
            target="apt-get update",
            ok=True,
            skipped=True,
            error="debian mirror is empty",
        )

    apt_get = shutil.which("apt-get")
    if not apt_get:
        return _make_result(
            name="apt_update",
            target="apt-get update",
            ok=True,
            skipped=True,
            error="apt-get not available",
        )

    source_content = "\n".join(
        [
            f"deb {mirror}/debian stable main contrib non-free non-free-firmware",
            f"deb {mirror}/debian stable-updates main contrib non-free non-free-firmware",
            f"deb {mirror}/debian-security stable-security main contrib non-free non-free-firmware",
            "",
        ]
    )

    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", suffix=".list", delete=False
    ) as source_file:
        source_file.write(source_content)
        source_list_path = source_file.name

    cmd = [
        apt_get,
        "-o",
        f"Dir::Etc::sourcelist={source_list_path}",
        "-o",
        "Dir::Etc::sourceparts=-",
        "-o",
        "Acquire::Retries=0",
        "-o",
        "Acquire::Languages=none",
        "-o",
        "APT::Get::List-Cleanup=0",
        "update",
    ]

    if settings.http_proxy:
        cmd.extend(["-o", f'Acquire::http::Proxy={settings.http_proxy}'])
    if settings.https_proxy:
        cmd.extend(["-o", f'Acquire::https::Proxy={settings.https_proxy}'])

    start = time.perf_counter()
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            env=_build_runtime_env(settings),
        )
        output, _ = await asyncio.wait_for(proc.communicate(), timeout=45.0)
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        ok = proc.returncode == 0
        error = "" if ok else output.decode("utf-8", errors="ignore")[-300:]
        return _make_result(
            name="apt_update",
            target=cmd[-1],
            ok=ok,
            status_code=proc.returncode or 0,
            elapsed_ms=elapsed_ms,
            error=error.strip(),
        )
    except Exception as err:
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        return _make_result(
            name="apt_update",
            target="apt-get update",
            ok=False,
            elapsed_ms=elapsed_ms,
            error=str(err),
        )
    finally:
        try:
            os.remove(source_list_path)
        except OSError:
            pass


async def _run_deep_pip_download(settings: ContainerRuntimeSettings) -> Dict[str, Any]:
    pip_index_url = _normalize_text(settings.pip_index_url)
    if not pip_index_url:
        return _make_result(
            name="pip_download",
            target="pip download",
            ok=True,
            skipped=True,
            error="pip index url is empty",
        )

    tmp_dir = tempfile.mkdtemp(prefix="webui-pip-test-")
    cmd = [
        sys.executable,
        "-m",
        "pip",
        "--disable-pip-version-check",
        "download",
        "--no-deps",
        "--no-cache-dir",
        "--dest",
        tmp_dir,
        "-i",
        pip_index_url,
    ]
    trusted_host = _normalize_text(settings.pip_trusted_host)
    if trusted_host:
        for host in trusted_host.split():
            cmd.extend(["--trusted-host", host])
    cmd.append("pip")

    start = time.perf_counter()
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            env=_build_runtime_env(settings),
        )
        output, _ = await asyncio.wait_for(proc.communicate(), timeout=45.0)
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        ok = proc.returncode == 0
        error = "" if ok else output.decode("utf-8", errors="ignore")[-300:]
        return _make_result(
            name="pip_download",
            target="pip download pip",
            ok=ok,
            status_code=proc.returncode or 0,
            elapsed_ms=elapsed_ms,
            error=error.strip(),
        )
    except Exception as err:
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        return _make_result(
            name="pip_download",
            target="pip download pip",
            ok=False,
            elapsed_ms=elapsed_ms,
            error=str(err),
        )
    finally:
        try:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        except Exception:
            pass


async def test_container_runtime_connectivity(
    settings: ContainerRuntimeSettings,
    *,
    mode: str = "quick",
) -> Dict[str, Any]:
    targets = _build_connectivity_targets(settings)
    results: List[Dict[str, Any]] = []

    proxies = _build_proxy_mapping(settings)
    timeout = httpx.Timeout(10.0, connect=6.0)

    if targets:
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=timeout,
            proxies=proxies,
        ) as client:
            for name, target in targets:
                results.append(await _http_probe(client, name=name, target=target))

    if _normalize_text(mode).lower() == "deep":
        results.append(await _run_deep_apt_update(settings))
        results.append(await _run_deep_pip_download(settings))

    final_ok = all(item["ok"] or item.get("skipped") for item in results)
    return {"ok": final_ok, "results": results}


async def benchmark_container_source_presets(
    proxy_settings: ContainerRuntimeSettings,
) -> List[Dict[str, Any]]:
    benchmark_results: List[Dict[str, Any]] = []

    for preset in _SOURCE_PRESETS:
        settings = ContainerRuntimeSettings(
            http_proxy=proxy_settings.http_proxy,
            https_proxy=proxy_settings.https_proxy,
            all_proxy=proxy_settings.all_proxy,
            no_proxy=proxy_settings.no_proxy,
            debian_mirror=preset.get("debian_mirror", ""),
            pip_index_url=preset.get("pip_index_url", ""),
            pip_trusted_host=preset.get("pip_trusted_host", ""),
        )

        test_result = await test_container_runtime_connectivity(settings, mode="quick")
        result_map = {item["name"]: item for item in test_result["results"]}
        debian_item = result_map.get("debian_mirror")
        pip_item = result_map.get("pip_index")

        debian_elapsed_ms = int(debian_item["elapsed_ms"]) if debian_item else 0
        pip_elapsed_ms = int(pip_item["elapsed_ms"]) if pip_item else 0
        ok = bool(test_result["ok"])

        score_ms = debian_elapsed_ms + pip_elapsed_ms
        if not ok:
            score_ms += 100000

        errors = []
        if debian_item and debian_item.get("error"):
            errors.append(f"debian: {debian_item['error']}")
        if pip_item and pip_item.get("error"):
            errors.append(f"pip: {pip_item['error']}")

        benchmark_results.append(
            {
                "preset_id": preset["id"],
                "preset_name": preset["name"],
                "ok": ok,
                "score_ms": score_ms,
                "debian_elapsed_ms": debian_elapsed_ms,
                "pip_elapsed_ms": pip_elapsed_ms,
                "error": "; ".join(errors),
            }
        )

    benchmark_results.sort(
        key=lambda item: (0 if item["ok"] else 1, item["score_ms"])
    )
    return benchmark_results


def _has_explicit_source_env() -> bool:
    mirror_env_keys = (
        *_DEBIAN_MIRROR_KEYS,
        *_PIP_SOURCE_KEYS["PIP_INDEX_URL"],
        *_PIP_SOURCE_KEYS["PIP_EXTRA_INDEX_URL"],
        *_PIP_SOURCE_KEYS["PIP_TRUSTED_HOST"],
        "PIP_INDEX_URL",
        "pip_index_url",
        "PIP_EXTRA_INDEX_URL",
        "pip_extra_index_url",
        "PIP_TRUSTED_HOST",
        "pip_trusted_host",
    )
    if _pick_env(_SOURCE_PRESET_KEYS):
        return True
    return bool(_pick_env(mirror_env_keys))


def _has_saved_source_config() -> bool:
    return bool(
        _normalize_text(Config.container_debian_mirror)
        or _normalize_text(Config.container_pip_index_url)
        or _normalize_text(Config.container_pip_extra_index_url)
        or _normalize_text(Config.container_pip_trusted_host)
    )


def _apply_source_preset_to_config(preset_id: str) -> bool:
    for preset in _SOURCE_PRESETS:
        if preset["id"] != preset_id:
            continue

        Config.container_debian_mirror = _normalize_text(preset.get("debian_mirror", ""))
        Config.container_pip_index_url = _normalize_text(preset.get("pip_index_url", ""))
        Config.container_pip_extra_index_url = ""
        Config.container_pip_trusted_host = _normalize_text(
            preset.get("pip_trusted_host", "")
        )
        return True
    return False


async def maybe_auto_select_best_source_preset() -> None:
    if not _env_flag_enabled(_AUTO_BEST_PRESET_KEYS):
        return

    force_mode = _env_flag_enabled(_AUTO_BEST_PRESET_FORCE_KEYS)
    if not force_mode and _has_explicit_source_env():
        log.info(
            "Skip auto best preset: explicit source env values are already provided."
        )
        return

    if not force_mode and _has_saved_source_config():
        log.info("Skip auto best preset: saved source config already exists.")
        return

    effective = get_effective_container_settings()
    proxy_settings = ContainerRuntimeSettings(
        http_proxy=effective.http_proxy,
        https_proxy=effective.https_proxy,
        all_proxy=effective.all_proxy,
        no_proxy=effective.no_proxy,
    )

    log.info("Auto best preset benchmark started.")
    benchmark_results = await benchmark_container_source_presets(proxy_settings)
    best = next((item for item in benchmark_results if item["ok"]), None)
    if not best:
        log.warning("Auto best preset failed: no available preset passed benchmark.")
        return

    preset_id = _normalize_text(best.get("preset_id", ""))
    if not preset_id:
        log.warning("Auto best preset failed: invalid benchmark result.")
        return

    if not _apply_source_preset_to_config(preset_id):
        log.warning(f"Auto best preset failed: unknown preset id {preset_id!r}.")
        return

    Config.store(CONFIG_FILE_PATH)
    log.info(
        "Auto best preset selected: %s (score=%sms)."
        % (best.get("preset_name", preset_id), best.get("score_ms", 0))
    )
