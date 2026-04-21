import os
import asyncio
import subprocess
from pathlib import Path
from asyncio.streams import StreamReader
from typing import IO, Any, Tuple, Union, Optional

from nb_cli.consts import WINDOWS

from .log import LogStorage
from .schemas import ProcessLog
from nb_cli_plugin_webui.app.utils.string_utils import decode_parse


async def run_asyncio_subprocess(
    *args: Union[str, bytes, "os.PathLike[str]", "os.PathLike[bytes]"],
    cwd: Optional[Path] = None,
    env: Optional[dict] = None,
    stdin: Optional[Union[IO[Any], int]] = None,
    log_storage: Optional[LogStorage] = None,
) -> Tuple[asyncio.subprocess.Process, Optional[LogStorage]]:
    async def _read_stream(stream: Optional[StreamReader], log_storage: LogStorage):
        if stream:
            while True:
                line = await stream.readline()
                if line:
                    decode_line = decode_parse(line)
                    log_model = ProcessLog(message=decode_line)
                    await log_storage.add_log(log_model)
                else:
                    break

    process = await asyncio.create_subprocess_exec(
        *args,
        cwd=cwd,
        env=env,
        stdin=stdin,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        creationflags=(
            subprocess.CREATE_NEW_PROCESS_GROUP if WINDOWS else 0  # type: ignore
        ),
    )
    if log_storage:
        asyncio.create_task(_read_stream(process.stdout, log_storage))
        asyncio.create_task(_read_stream(process.stderr, log_storage))

    return process, log_storage
