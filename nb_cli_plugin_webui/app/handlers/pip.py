import asyncio
import os
from typing import IO, Any, Dict, List, Tuple, Union, Optional

from nb_cli.handlers import requires_pip, get_default_python

from .process import LogStorage, run_asyncio_subprocess
from nb_cli_plugin_webui.app.handlers.process import CustomLog
from nb_cli_plugin_webui.app.utils.bot_proxy import get_pip_proxy_env


@requires_pip
async def call_pip(
    pip_args: Optional[List[str]] = None,
    *,
    python_path: Optional[str] = None,
    env: Optional[Dict[str, str]] = None,
    project_meta: Optional[object] = None,
    stdin: Optional[Union[IO[Any], int]] = None,
    log_storage: Optional[LogStorage] = None,
) -> Tuple[asyncio.subprocess.Process, Optional[LogStorage]]:
    if pip_args is None:
        pip_args = list()
    if python_path is None:
        python_path = await get_default_python()

    runtime_env, socks_proxy_disabled = get_pip_proxy_env(
        env or os.environ.copy(), project_meta=project_meta
    )
    if socks_proxy_disabled and log_storage is not None:
        await log_storage.add_log(
            CustomLog(
                level="WARNING",
                message="检测到 SOCKS 代理，当前 pip 环境缺少相关依赖，已临时跳过代理后继续安装。",
            )
        )
    return await run_asyncio_subprocess(
        python_path,
        "-m",
        "pip",
        *pip_args,
        env=runtime_env,
        stdin=stdin,
        log_storage=log_storage,
    )


@requires_pip
async def call_pip_install(
    package: Union[str, List[str]],
    pip_args: Optional[List[str]] = None,
    *,
    python_path: Optional[str] = None,
    env: Optional[Dict[str, str]] = None,
    project_meta: Optional[object] = None,
    stdin: Optional[Union[IO[Any], int]] = None,
    log_storage: Optional[LogStorage] = None,
) -> Tuple[asyncio.subprocess.Process, Optional[LogStorage]]:
    if isinstance(package, str):
        package = [package]
    if pip_args is None:
        pip_args = list()

    return await call_pip(
        ["install", *package, *pip_args],
        python_path=python_path,
        env=env,
        project_meta=project_meta,
        stdin=stdin,
        log_storage=log_storage,
    )
