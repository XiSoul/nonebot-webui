import os
import sys
import socket
import asyncio
import shlex
import json
import time
from typing import Dict, List, Optional, Tuple
from pathlib import Path

from dotenv import dotenv_values
from nb_cli.config import SimpleInfo as CliSimpleInfo
from nb_cli.handlers import get_default_python, generate_run_script

from nb_cli_plugin_webui.app.config import Config
from nb_cli_plugin_webui.app.project import service as project_service
from nb_cli_plugin_webui.app.handlers.process import (
    Processor,
    CustomLog,
    LogStorage,
    ProcessManager,
    LogStorageFather,
    ProcessAlreadyRunning,
    ProcessNotRunning,
)
from nb_cli_plugin_webui.app.utils.bot_proxy import get_bot_proxy_env, get_pip_proxy_env

from .exceptions import DriverNotFound, AdapterNotFound


SHELL_COMMAND_DONE_MARKER = "__NB_WEBUI_CMD_DONE__:"
HTMLRENDER_DEPENDENCY_MARKERS = (
    "nonebot-plugin-htmlrender",
    "nonebot_plugin_htmlrender",
)
HTMLRENDER_PROJECT_FILES = (
    "pyproject.toml",
    "requirements.txt",
    "requirements-dev.txt",
    "requirements-prod.txt",
    "poetry.lock",
    "uv.lock",
    "Pipfile",
    "Pipfile.lock",
)
HTMLRENDER_PLAYWRIGHT_TIMEOUT_SECONDS = 20 * 60
PLAYWRIGHT_DOWNLOAD_CONNECTION_TIMEOUT = "300000"
HTMLRENDER_INSTALL_TASKS: Dict[str, asyncio.Task] = dict()
PROCESS_START_STABILITY_SECONDS = 2.0
PROJECT_READY_TIMEOUT_SECONDS = 90.0
PROJECT_SHELL_LOG_SUFFIX = ":shell"
PLAYWRIGHT_DIRLOCK_STALE_SECONDS = 5 * 60


class ProjectShellSessionManager:
    sessions: Dict[str, Processor] = dict()

    @classmethod
    def get_session(cls, project_id: str) -> Optional[Processor]:
        session = cls.sessions.get(project_id)
        if session is None:
            return None
        if session.refresh_runtime_state():
            return session
        cls.sessions.pop(project_id, None)
        return None

    @classmethod
    def set_session(cls, project_id: str, session: Processor) -> None:
        cls.sessions[project_id] = session

    @classmethod
    async def stop_session(cls, project_id: str) -> bool:
        session = cls.sessions.pop(project_id, None)
        if session is None:
            return False

        try:
            await session.stop()
        except Exception:
            pass
        return True


def get_project_runtime_log_key(project_id: str) -> str:
    return project_id


def get_project_shell_log_key(project_id: str) -> str:
    return f"{project_id}{PROJECT_SHELL_LOG_SUFFIX}"


def _is_port_available(port: int) -> bool:
    if port <= 0:
        return False
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("0.0.0.0", port))
            return True
        except OSError:
            return False


def _pick_available_port(project_id: str) -> int:
    base = 20000 + (sum(ord(ch) for ch in project_id) % 20000)
    reserved_ports = set(
        project_service.get_project_port_usage(exclude_project_id=project_id).keys()
    )
    for offset in range(0, 20000):
        candidate = base + offset
        if candidate > 65535:
            candidate = 1024 + (candidate - 65536)
        if candidate not in reserved_ports and _is_port_available(candidate):
            return candidate
    return 0


def _load_project_env_data(project_meta, project_dir: Path) -> dict:
    env_filename = str(getattr(project_meta, "use_env", "") or "").strip()
    if not env_filename:
        return {}

    env_file = project_dir / env_filename
    if not env_file.exists():
        return {}

    return dotenv_values(env_file)


def _resolve_runtime_path(project_dir: Path, raw_value: str) -> str:
    resolved = Path(os.path.expanduser(raw_value))
    if not resolved.is_absolute():
        resolved = project_dir / resolved
    return str(resolved.absolute())


def _project_mentions_htmlrender(project_meta, project_dir: Path) -> bool:
    project_plugins = getattr(project_meta, "plugins", None) or []
    for plugin in project_plugins:
        plugin_module = str(getattr(plugin, "module_name", "") or "").lower()
        plugin_link = str(getattr(plugin, "project_link", "") or "").lower()
        plugin_name = str(getattr(plugin, "name", "") or "").lower()
        if any(
            marker in value
            for marker in HTMLRENDER_DEPENDENCY_MARKERS
            for value in (plugin_module, plugin_link, plugin_name)
        ):
            return True

    for file_name in HTMLRENDER_PROJECT_FILES:
        candidate = project_dir / file_name
        if not candidate.is_file():
            continue
        try:
            content = candidate.read_text(encoding="utf-8").lower()
        except UnicodeDecodeError:
            content = candidate.read_text(encoding="utf-8", errors="ignore").lower()
        except Exception:
            continue

        if any(marker in content for marker in HTMLRENDER_DEPENDENCY_MARKERS):
            return True

    return False


def _default_nonebot2_data_dir(env: dict) -> Path:
    if sys.platform == "win32":
        local_app_data = str(env.get("LOCALAPPDATA") or "").strip()
        if local_app_data:
            return Path(local_app_data) / "nonebot2"
        home_dir = Path(str(env.get("USERPROFILE") or Path.home()))
        return home_dir / "AppData" / "Local" / "nonebot2"

    home_dir = Path(str(env.get("HOME") or Path.home()))
    if sys.platform == "darwin":
        return home_dir / "Library" / "Application Support" / "nonebot2"

    data_home = str(env.get("XDG_DATA_HOME") or "").strip()
    if data_home:
        return Path(data_home) / "nonebot2"
    return home_dir / ".local" / "share" / "nonebot2"


def _clear_stale_htmlrender_dirlock(env: dict, log_storage: Optional[LogStorage] = None) -> None:
    lock_path = (
        _default_nonebot2_data_dir(env)
        / "nonebot_plugin_htmlrender"
        / "__dirlock"
    )
    if not lock_path.exists():
        return

    try:
        age_seconds = max(0.0, time.time() - lock_path.stat().st_mtime)
    except OSError:
        age_seconds = PLAYWRIGHT_DIRLOCK_STALE_SECONDS + 1

    if age_seconds < PLAYWRIGHT_DIRLOCK_STALE_SECONDS:
        return

    try:
        if lock_path.is_dir():
            import shutil

            shutil.rmtree(lock_path, ignore_errors=True)
        else:
            lock_path.unlink(missing_ok=True)
        if log_storage is not None:
            asyncio.create_task(
                log_storage.add_log(
                    CustomLog(
                        level="WARNING",
                        message=(
                            "检测到遗留的 Playwright 安装锁文件，已自动清理："
                            f" {lock_path}"
                        ),
                    )
                )
            )
    except Exception:
        pass


def _apply_htmlrender_browser_path(env: dict, project_meta, project_dir: Path) -> None:
    if str(env.get("PLAYWRIGHT_BROWSERS_PATH") or "").strip():
        return

    env_data = _load_project_env_data(project_meta, project_dir)

    explicit_browser_path = str(
        env_data.get("PLAYWRIGHT_BROWSERS_PATH")
        or env_data.get("playwright_browsers_path")
        or ""
    ).strip()
    if explicit_browser_path:
        env["PLAYWRIGHT_BROWSERS_PATH"] = _resolve_runtime_path(
            project_dir, explicit_browser_path
        )
        return

    htmlrender_storage_path = str(
        env_data.get("htmlrender_storage_path")
        or env_data.get("HTMLRENDER_STORAGE_PATH")
        or ""
    ).strip()
    if htmlrender_storage_path:
        env["PLAYWRIGHT_BROWSERS_PATH"] = _resolve_runtime_path(
            project_dir, htmlrender_storage_path
        )
        return

    if not _project_mentions_htmlrender(project_meta, project_dir):
        return

    env["PLAYWRIGHT_BROWSERS_PATH"] = str(
        (_default_nonebot2_data_dir(env) / "nonebot_plugin_htmlrender").absolute()
    )


def _apply_htmlrender_download_env(env: dict, project_meta, project_dir: Path) -> None:
    if not _project_mentions_htmlrender(project_meta, project_dir):
        return

    env_data = _load_project_env_data(project_meta, project_dir)

    explicit_chromium_host = str(
        env_data.get("PLAYWRIGHT_CHROMIUM_DOWNLOAD_HOST")
        or env_data.get("playwright_chromium_download_host")
        or ""
    ).strip()
    if explicit_chromium_host:
        env["PLAYWRIGHT_CHROMIUM_DOWNLOAD_HOST"] = explicit_chromium_host

    explicit_timeout = str(
        env_data.get("PLAYWRIGHT_DOWNLOAD_CONNECTION_TIMEOUT")
        or env_data.get("playwright_download_connection_timeout")
        or ""
    ).strip()
    if explicit_timeout:
        env["PLAYWRIGHT_DOWNLOAD_CONNECTION_TIMEOUT"] = explicit_timeout
    else:
        env.setdefault(
            "PLAYWRIGHT_DOWNLOAD_CONNECTION_TIMEOUT",
            PLAYWRIGHT_DOWNLOAD_CONNECTION_TIMEOUT,
        )


def build_project_runtime_env(project_meta, *, pip_safe: bool = False) -> Tuple[dict, bool]:
    project_dir = Path(project_meta.project_dir)
    if pip_safe:
        env, socks_proxy_disabled = get_pip_proxy_env(
            os.environ.copy(), project_meta=project_meta
        )
    else:
        env = get_bot_proxy_env(os.environ.copy(), project_meta=project_meta)
        socks_proxy_disabled = False
    env["TERM"] = "xterm-color"

    if sys.platform == "win32":
        venv_path = project_dir / Path(".venv/Scripts")
        env["PATH"] = f"{venv_path.absolute()};{env.get('PATH', '')}"
    else:
        venv_path = project_dir / Path(".venv/bin")
        env["PATH"] = f"{venv_path.absolute()}:{env.get('PATH', '')}"

    virtual_env = project_dir / ".venv"
    if virtual_env.is_dir():
        env["VIRTUAL_ENV"] = str(virtual_env.absolute())

    _apply_htmlrender_browser_path(env, project_meta, project_dir)
    _apply_htmlrender_download_env(env, project_meta, project_dir)

    return env, socks_proxy_disabled


def _get_project_python_path(project_dir: Path) -> str:
    if sys.platform == "win32":
        python_path = project_dir / ".venv" / "Scripts" / "python.exe"
    else:
        python_path = project_dir / ".venv" / "bin" / "python"

    return str(python_path.absolute()) if python_path.exists() else "python"


def _build_shell_bootstrap_script(
    project_dir: Path, proxy_env: Optional[Dict[str, str]] = None
) -> str:
    project_python = _get_project_python_path(project_dir)
    quoted_python = shlex.quote(project_python)
    proxy_env = proxy_env or {}
    saved_http_proxy = shlex.quote(
        str(proxy_env.get("HTTP_PROXY") or proxy_env.get("http_proxy") or "")
    )
    saved_https_proxy = shlex.quote(
        str(proxy_env.get("HTTPS_PROXY") or proxy_env.get("https_proxy") or "")
    )
    saved_all_proxy = shlex.quote(
        str(proxy_env.get("ALL_PROXY") or proxy_env.get("all_proxy") or "")
    )
    saved_no_proxy = shlex.quote(
        str(proxy_env.get("NO_PROXY") or proxy_env.get("no_proxy") or "")
    )
    return (
        f"__nb_webui_python={quoted_python}\n"
        f"__nb_webui_saved_http_proxy={saved_http_proxy}\n"
        f"__nb_webui_saved_https_proxy={saved_https_proxy}\n"
        f"__nb_webui_saved_all_proxy={saved_all_proxy}\n"
        f"__nb_webui_saved_no_proxy={saved_no_proxy}\n"
        f"export PLAYWRIGHT_DOWNLOAD_CONNECTION_TIMEOUT={shlex.quote(PLAYWRIGHT_DOWNLOAD_CONNECTION_TIMEOUT)}\n"
        "pip() {\n"
        '  case "${HTTP_PROXY:-${http_proxy:-}} ${HTTPS_PROXY:-${https_proxy:-}} ${ALL_PROXY:-${all_proxy:-}}" in\n'
        "    *socks4://*|*socks4a://*|*socks5://*|*socks5h://*)\n"
        '      env -u HTTP_PROXY -u HTTPS_PROXY -u ALL_PROXY -u http_proxy -u https_proxy -u all_proxy "$__nb_webui_python" -m pip "$@"\n'
        "      ;;\n"
        "    *)\n"
        '      "$__nb_webui_python" -m pip "$@"\n'
        "      ;;\n"
        "  esac\n"
        "}\n"
        "playwright() {\n"
        '  if [ -n "${__nb_webui_saved_http_proxy:-}" ]; then export HTTP_PROXY="$__nb_webui_saved_http_proxy"; export http_proxy="$__nb_webui_saved_http_proxy"; fi\n'
        '  if [ -n "${__nb_webui_saved_https_proxy:-}" ]; then export HTTPS_PROXY="$__nb_webui_saved_https_proxy"; export https_proxy="$__nb_webui_saved_https_proxy"; fi\n'
        '  if [ -n "${__nb_webui_saved_all_proxy:-}" ]; then export ALL_PROXY="$__nb_webui_saved_all_proxy"; export all_proxy="$__nb_webui_saved_all_proxy"; fi\n'
        '  if [ -n "${__nb_webui_saved_no_proxy:-}" ]; then export NO_PROXY="$__nb_webui_saved_no_proxy"; export no_proxy="$__nb_webui_saved_no_proxy"; fi\n'
        '  "$__nb_webui_python" -m playwright "$@"\n'
        "}\n"
    )


async def _run_subprocess(
    *args: str,
    cwd: Path,
    env: dict,
    timeout: Optional[int] = None,
    log_storage: Optional[LogStorage] = None,
    stdout_level: str = "INFO",
    stderr_level: str = "WARNING",
) -> Tuple[int, str, str]:
    process = await asyncio.create_subprocess_exec(
        *args,
        cwd=str(cwd),
        env=env,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    async def _collect(
        stream: Optional[asyncio.StreamReader], level: str
    ) -> str:
        if stream is None:
            return ""

        lines: List[str] = []
        while True:
            line = await stream.readline()
            if not line:
                break
            text = line.decode("utf-8", errors="ignore").rstrip()
            if not text:
                continue
            lines.append(text)
            if log_storage is not None:
                await log_storage.add_log(CustomLog(level=level, message=text))
        return "\n".join(lines)

    stdout_task = asyncio.create_task(_collect(process.stdout, stdout_level))
    stderr_task = asyncio.create_task(_collect(process.stderr, stderr_level))

    try:
        await asyncio.wait_for(process.wait(), timeout=timeout)
    except asyncio.TimeoutError:
        process.kill()
        await process.wait()
        stdout_text, stderr_text = await asyncio.gather(stdout_task, stderr_task)
        raise TimeoutError(
            f"Command timed out after {timeout}s: {' '.join(args)}"
        ) from None

    stdout_text, stderr_text = await asyncio.gather(stdout_task, stderr_task)
    return process.returncode, stdout_text, stderr_text


async def _detect_playwright_chromium_executable(
    project_dir: Path, env: dict
) -> Tuple[bool, str]:
    python_path = _get_project_python_path(project_dir)
    script = (
        "import json\n"
        "from pathlib import Path\n"
        "from playwright.sync_api import sync_playwright\n"
        "with sync_playwright() as p:\n"
        "    path = Path(p.chromium.executable_path)\n"
        "    print(json.dumps({'path': str(path), 'exists': path.exists()}))\n"
    )
    returncode, stdout_text, stderr_text = await _run_subprocess(
        python_path,
        "-c",
        script,
        cwd=project_dir,
        env=env,
    )
    if returncode != 0:
        combined = stderr_text or stdout_text
        raise RuntimeError(
            combined or "Failed to inspect Playwright chromium executable path."
        )

    lines = [line.strip() for line in stdout_text.splitlines() if line.strip()]
    if not lines:
        raise RuntimeError("Playwright executable probe returned empty output.")

    payload = json.loads(lines[-1])
    return bool(payload.get("exists")), str(payload.get("path") or "")


async def _can_launch_playwright_chromium(project_dir: Path, env: dict) -> Tuple[bool, str]:
    python_path = _get_project_python_path(project_dir)
    script = (
        "import asyncio\n"
        "from playwright.async_api import async_playwright\n"
        "async def main():\n"
        "    async with async_playwright() as p:\n"
        "        browser = await p.chromium.launch()\n"
        "        await browser.close()\n"
        "asyncio.run(main())\n"
    )
    returncode, stdout_text, stderr_text = await _run_subprocess(
        python_path,
        "-c",
        script,
        cwd=project_dir,
        env=env,
    )
    detail = stderr_text or stdout_text or ""
    return returncode == 0, detail


async def _ensure_htmlrender_browser_ready(
    project_meta,
    env: dict,
    log_storage: Optional[LogStorage] = None,
    *,
    block: bool = True,
) -> None:
    project_dir = Path(project_meta.project_dir)
    if not _project_mentions_htmlrender(project_meta, project_dir):
        return

    _clear_stale_htmlrender_dirlock(env, log_storage=log_storage)

    try:
        browser_exists, executable_path = await _detect_playwright_chromium_executable(
            project_dir, env
        )
    except Exception as err:
        browser_exists = False
        executable_path = ""
        if log_storage is not None:
            await log_storage.add_log(
                CustomLog(
                    level="WARNING",
                    message=(
                        "检测 htmlrender Chromium 状态失败，将继续尝试准备浏览器："
                        f" {err}"
                    ),
                )
            )

    if browser_exists:
        can_launch, launch_detail = await _can_launch_playwright_chromium(
            project_dir, env
        )
        if can_launch:
            if log_storage is not None:
                await log_storage.add_log(
                    CustomLog(
                        level="INFO",
                        message=f"htmlrender Chromium 已就绪：{executable_path}",
                    )
                )
            return
        if log_storage is not None:
            await log_storage.add_log(
                CustomLog(
                    level="WARNING",
                    message=(
                        "检测到 Chromium 主程序存在，但浏览器启动自检未通过，"
                        "将继续尝试补全 Playwright 浏览器组件。"
                        + (f" 详情：{launch_detail}" if launch_detail else "")
                    ),
                )
            )

    if not block:
        project_id = str(getattr(project_meta, "project_id", "") or "").strip()
        existing_task = HTMLRENDER_INSTALL_TASKS.get(project_id)
        if existing_task is not None and not existing_task.done():
            if log_storage is not None:
                await log_storage.add_log(
                    CustomLog(
                        level="INFO",
                        message="htmlrender Chromium 正在后台准备中，请稍候查看进度日志。",
                    )
                )
            return

        if log_storage is not None:
            await log_storage.add_log(
                CustomLog(
                    level="INFO",
                    message=(
                        "htmlrender Chromium 尚未就绪，已转为后台准备。"
                        "实例会继续启动，首次渲染相关功能可稍后再试。"
                    ),
                )
            )

        async def _background_install() -> None:
            try:
                await _ensure_htmlrender_browser_ready(
                    project_meta,
                    env,
                    log_storage=log_storage,
                    block=True,
                )
            except Exception as err:
                log.exception(
                    f"Background htmlrender browser install failed for {project_id=}."
                )
                if log_storage is not None:
                    await log_storage.add_log(
                        CustomLog(
                            level="ERROR",
                            message=(
                                "htmlrender Chromium 后台准备失败："
                                f" {err}"
                            ),
                        )
                    )
            finally:
                HTMLRENDER_INSTALL_TASKS.pop(project_id, None)

        if project_id:
            HTMLRENDER_INSTALL_TASKS[project_id] = asyncio.create_task(
                _background_install()
            )
        else:
            asyncio.create_task(_background_install())
        return

    active_proxy = (
        str(env.get("ALL_PROXY") or env.get("all_proxy") or "").strip()
        or str(env.get("HTTPS_PROXY") or env.get("https_proxy") or "").strip()
        or str(env.get("HTTP_PROXY") or env.get("http_proxy") or "").strip()
    )

    if log_storage is not None:
        await log_storage.add_log(
            CustomLog(
                level="INFO",
                message=(
                    "检测到 nonebot_plugin_htmlrender 缺少 Chromium 浏览器，"
                    "正在预装 Playwright 浏览器到 htmlrender 目录。"
                ),
            )
        )
        await log_storage.add_log(
            CustomLog(
                level="INFO",
                message=(
                    "当前将使用 Playwright 默认下载源；如项目单独配置了镜像地址，会优先使用项目自己的设置。"
                ),
            )
        )
        await log_storage.add_log(
            CustomLog(
                level="INFO",
                message=(
                    "首次下载体积较大，前几秒可能停留在 0%，这通常是在建立连接或等待服务端返回进度，不代表已经卡死。"
                ),
            )
        )
        if active_proxy:
            await log_storage.add_log(
                CustomLog(
                    level="INFO",
                    message=(
                        "检测到运行时代理，预装浏览器阶段将直接复用当前实例代理环境："
                        f"{active_proxy}"
                    ),
                )
            )
        else:
            await log_storage.add_log(
                CustomLog(
                    level="INFO",
                    message="当前未检测到实例代理，浏览器预装将直接走容器默认网络。",
                )
            )

    python_path = _get_project_python_path(project_dir)
    returncode, stdout_text, stderr_text = await _run_subprocess(
        python_path,
        "-m",
        "playwright",
        "install",
        "chromium",
        cwd=project_dir,
        env=env,
        timeout=HTMLRENDER_PLAYWRIGHT_TIMEOUT_SECONDS,
        log_storage=log_storage,
    )

    browser_exists, executable_path = await _detect_playwright_chromium_executable(
        project_dir, env
    )
    can_launch, launch_detail = await _can_launch_playwright_chromium(project_dir, env)
    if returncode != 0 or not browser_exists or not can_launch:
        error_detail = stderr_text or stdout_text or executable_path or "unknown error"
        if launch_detail:
            error_detail = f"{error_detail}\n{launch_detail}".strip()
        raise RuntimeError(
            "Failed to preinstall Playwright chromium for nonebot_plugin_htmlrender: "
            f"{error_detail}"
        )

    if log_storage is not None:
        await log_storage.add_log(
            CustomLog(
                level="INFO",
                message=f"htmlrender Chromium 预装完成：{executable_path}",
            )
        )


def _wrap_shell_command(command: str) -> str:
    stripped = command.rstrip("\r\n")
    if not stripped:
        return command
    return f"{stripped}\nprintf '{SHELL_COMMAND_DONE_MARKER}%s\\n' \"$?\"\n"


def ensure_project_runtime_log_storage(project_id: str) -> LogStorage:
    runtime_log_key = get_project_runtime_log_key(project_id)
    log_storage = LogStorageFather.get_storage(runtime_log_key)
    if log_storage is not None:
        return log_storage

    log_storage = LogStorage(Config.process_log_destroy_seconds)
    LogStorageFather.add_storage(log_storage, runtime_log_key)
    return log_storage


def ensure_project_shell_log_storage(project_id: str) -> LogStorage:
    shell_log_key = get_project_shell_log_key(project_id)
    log_storage = LogStorageFather.get_storage(shell_log_key)
    if log_storage is not None:
        return log_storage

    log_storage = LogStorage(Config.process_log_destroy_seconds)
    LogStorageFather.add_storage(log_storage, shell_log_key)
    return log_storage


def ensure_project_log_storage(project_id: str) -> LogStorage:
    return ensure_project_runtime_log_storage(project_id)


async def stop_project_shell_session(project_id: str) -> bool:
    return await ProjectShellSessionManager.stop_session(project_id)


def _extract_recent_error_logs(log_storage: LogStorage, limit: int = 12) -> str:
    recent_logs = log_storage.get_logs(count=limit)
    if not recent_logs:
        return ""

    filtered_lines: List[str] = []
    for item in recent_logs:
        message = str(getattr(item, "message", "") or "").strip()
        if not message:
            continue
        filtered_lines.append(message)

    if not filtered_lines:
        return ""

    return "\n".join(filtered_lines[-limit:])


async def _ensure_process_started_stably(
    process: Processor,
    *,
    project_name: str,
    log_storage: LogStorage,
    timeout: float = PROCESS_START_STABILITY_SECONDS,
) -> None:
    deadline = asyncio.get_running_loop().time() + max(timeout, 0)
    while True:
        if not process.refresh_runtime_state():
            status_code = process.process.returncode if process.process else None
            recent_logs = _extract_recent_error_logs(log_storage)
            detail_parts = [
                f"实例 {project_name} 启动失败，进程已退出",
            ]
            if status_code is not None:
                detail_parts.append(f"退出码: {status_code}")
            if recent_logs:
                detail_parts.append(f"最近日志:\n{recent_logs}")
            raise RuntimeError("；".join(detail_parts))

        if asyncio.get_running_loop().time() >= deadline:
            return

        await asyncio.sleep(0.1)


def _resolve_healthcheck_host(host: str) -> str:
    normalized = str(host or "").strip()
    if not normalized or normalized in {"0.0.0.0", "::", "*"}:
        return "127.0.0.1"
    if normalized == "::1":
        return "127.0.0.1"
    return normalized


def _can_connect_to_port(host: str, port: int) -> bool:
    if port <= 0:
        return False

    target_host = _resolve_healthcheck_host(host)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        try:
            return sock.connect_ex((target_host, port)) == 0
        except OSError:
            return False


async def _wait_for_project_ready(
    process: Processor,
    *,
    project_name: str,
    host: str,
    port: int,
    log_storage: LogStorage,
    timeout: float = PROJECT_READY_TIMEOUT_SECONDS,
) -> None:
    deadline = asyncio.get_running_loop().time() + max(timeout, 0)
    while True:
        if not process.refresh_runtime_state():
            status_code = process.process.returncode if process.process else None
            recent_logs = _extract_recent_error_logs(log_storage)
            detail_parts = [
                f"实例 {project_name} 启动失败，进程已退出",
            ]
            if status_code is not None:
                detail_parts.append(f"退出码: {status_code}")
            if recent_logs:
                detail_parts.append(f"最近日志:\n{recent_logs}")
            raise RuntimeError("；".join(detail_parts))

        if _can_connect_to_port(host, port):
            return

        if asyncio.get_running_loop().time() >= deadline:
            recent_logs = _extract_recent_error_logs(log_storage)
            detail_parts = [
                f"实例 {project_name} 在限定时间内未监听端口 {port}",
            ]
            if recent_logs:
                detail_parts.append(f"最近日志:\n{recent_logs}")
            raise RuntimeError("；".join(detail_parts))

        await asyncio.sleep(0.25)


async def ensure_project_shell_session(
    project: project_service.NoneBotProjectManager,
) -> Optional[Processor]:
    project_meta = project.read()

    existing_session = ProjectShellSessionManager.get_session(project_meta.project_id)
    if existing_session is not None:
        return existing_session

    raw_proxy_env, _ = build_project_runtime_env(project_meta, pip_safe=False)
    env, socks_proxy_disabled = build_project_runtime_env(project_meta, pip_safe=True)
    env["PYTHONUNBUFFERED"] = "1"
    env.setdefault("PIP_DISABLE_PIP_VERSION_CHECK", "1")

    if sys.platform == "win32":
        args = ("cmd",)
    else:
        preferred_shell = Path("/bin/bash")
        shell = (
            str(preferred_shell)
            if preferred_shell.is_file()
            else os.environ.get("SHELL") or "/bin/sh"
        )
        args = (shell,)

    process = Processor(
        *args,
        cwd=Path(project_meta.project_dir),
        env=env,
        log_destroy_seconds=Config.process_log_destroy_seconds,
        project_id=project_meta.project_id,
        project_name=project_meta.project_name,
        terminate_duplicate_processes=False,
    )
    process.log_storage = ensure_project_shell_log_storage(project_meta.project_id)
    await process.start()
    ProjectShellSessionManager.set_session(project_meta.project_id, process)
    bootstrap_script = _build_shell_bootstrap_script(
        Path(project_meta.project_dir), proxy_env=raw_proxy_env
    )
    await process.write_stdin(bootstrap_script.encode())

    await process.log_storage.add_log(
        CustomLog(level="INFO", message="项目终端 Shell 已连接，可直接连续输入命令。")
    )
    if socks_proxy_disabled:
        await process.log_storage.add_log(
            CustomLog(
                level="WARNING",
                message="检测到 SOCKS 代理：终端中的 pip 会临时跳过代理，playwright 等其他命令仍保留原代理环境。",
            )
        )
    return process


async def get_active_terminal_process(
    project: project_service.NoneBotProjectManager,
    *,
    create_shell: bool = False,
) -> Optional[Processor]:
    runtime_process = ProcessManager.get_process(project.project_id)
    if runtime_process and runtime_process.refresh_runtime_state():
        return runtime_process

    shell_session = ProjectShellSessionManager.get_session(project.project_id)
    if shell_session is not None:
        return shell_session

    if create_shell:
        return await ensure_project_shell_session(project)

    return None


async def execute_project_command(
    project: project_service.NoneBotProjectManager, command: str
) -> None:
    process = await ensure_project_shell_session(project)
    if process is None:
        raise ProcessNotRunning()

    wrapped_command = _wrap_shell_command(command)
    await process.write_stdin(wrapped_command.encode())


async def run_nonebot_project(project: project_service.NoneBotProjectManager):
    project_meta = project.read()
    if not project_meta.adapters:
        raise AdapterNotFound()
    if not project_meta.drivers:
        raise DriverNotFound()

    await stop_project_shell_session(project_meta.project_id)

    project_dir = Path(project_meta.project_dir)
    env, _ = build_project_runtime_env(project_meta)
    log_storage = ensure_project_runtime_log_storage(project_meta.project_id)

    env_file = project_dir / project_meta.use_env
    env_data = dotenv_values(env_file) if env_file.exists() else {}
    configured_host = str(env_data.get("HOST", "")).strip()
    configured_port = project_service.parse_project_port(env_data.get("PORT"))
    reserved_ports = project_service.get_project_port_usage(
        exclude_project_id=project_meta.project_id
    )
    configured_port_available = (
        configured_port > 0
        and configured_port not in reserved_ports
        and _is_port_available(configured_port)
    )
    run_port = (
        configured_port
        if configured_port_available
        else _pick_available_port(project_meta.project_id)
    )
    if run_port:
        env["PORT"] = str(run_port)
        project.write_to_env(project_meta.use_env, "PORT", str(run_port))
    host = configured_host or "0.0.0.0"
    env["HOST"] = host
    if not configured_host:
        project.write_to_env(project_meta.use_env, "HOST", host)

    await _ensure_htmlrender_browser_ready(
        project_meta,
        env,
        log_storage=log_storage,
        block=True,
    )

    process = ProcessManager.get_process(project_meta.project_id)
    if process:
        if process.refresh_runtime_state():
            raise ProcessAlreadyRunning()
        else:
            await process.start()
    else:
        python_path = project.config_manager.python_path
        if python_path is None:
            python_path = await get_default_python()

        raw_adapters = project_meta.adapters
        adapters: List[CliSimpleInfo] = list()
        for adapter in raw_adapters:
            adapters.append(
                CliSimpleInfo(name=adapter.name, module_name=adapter.module_name)
            )
        run_script = await generate_run_script(
            adapters=adapters,
            builtin_plugins=project_meta.builtin_plugins,
        )

        log_destroy_time = Config.process_log_destroy_seconds
        if project_meta.use_run_script:
            run_script_file = project_dir / project_meta.run_script_name
            if not run_script_file.exists():
                run_script_file.write_text(run_script, encoding="utf-8")

            process = Processor(
                python_path,
                run_script_file,
                cwd=project_dir,
                env=env,
                log_destroy_seconds=log_destroy_time,
                project_id=project_meta.project_id,
                project_name=project_meta.project_name,
            )
        else:
            process = Processor(
                python_path,
                "-c",
                run_script,
                cwd=project_dir,
                env=env,
                log_destroy_seconds=log_destroy_time,
                project_id=project_meta.project_id,
                project_name=project_meta.project_name,
            )

        process.log_storage = log_storage
        await process.start()
        ProcessManager.add_process(process, project_meta.project_id)

    await _ensure_process_started_stably(
        process,
        project_name=project_meta.project_name,
        log_storage=log_storage,
    )
    if run_port:
        await _wait_for_project_ready(
            process,
            project_name=project_meta.project_name,
            host=host,
            port=run_port,
            log_storage=log_storage,
        )


async def restart_nonebot_project_if_running(
    project: project_service.NoneBotProjectManager,
) -> bool:
    process = ProcessManager.get_process(project.project_id)
    if not process or not process.refresh_runtime_state():
        return False

    await process.stop()
    await run_nonebot_project(project)
    return True
