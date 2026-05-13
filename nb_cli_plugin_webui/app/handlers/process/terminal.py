import asyncio
import os
import pty
import signal
import struct
from pathlib import Path
from typing import Dict, Optional, Union

from nb_cli_plugin_webui.app.logging import logger as log
from nb_cli_plugin_webui.app.utils.global_log import append_instance_log
from nb_cli_plugin_webui.app.utils.string_utils import decode_parse

from .exceptions import ProcessNotRunning
from .log import LogStorage
from .schemas import ProcessInfo, ProcessLog

try:
    import fcntl
    import termios
except ImportError:  # pragma: no cover
    fcntl = None
    termios = None


class PtyTerminalSession:
    process: Optional[asyncio.subprocess.Process] = None
    process_is_running: bool = False

    def __init__(
        self,
        *args: Union[str, bytes, "os.PathLike[str]", "os.PathLike[bytes]"],
        cwd: Path,
        env: Optional[Dict[str, str]] = None,
        log_destroy_seconds: int,
        project_id: str = "",
        project_name: str = "",
    ) -> None:
        self.args = args
        self.cwd = cwd
        self.env = env
        self.log_storage = LogStorage(log_destroy_seconds)
        self.project_id = project_id
        self.project_name = project_name

        self.master_fd: Optional[int] = None
        self.slave_fd: Optional[int] = None
        self.output_loop: Optional[asyncio.AbstractEventLoop] = None
        self.wait_task: Optional[asyncio.Task] = None
        self.finished_logged = False
        self.runtime_state = "stopped"
        self._reader_registered = False

    async def _publish_output(self, output: str) -> None:
        if not output:
            return

        await self.log_storage.add_log(ProcessLog(message=output))
        if self.project_id:
            append_instance_log(
                project_id=self.project_id,
                project_name=self.project_name,
                message=output,
                source="terminal",
            )

    def _handle_master_ready(self) -> None:
        if self.master_fd is None:
            return

        while True:
            try:
                output = os.read(self.master_fd, 4096)
            except BlockingIOError:
                break
            except OSError:
                break

            if not output:
                break

            decoded = decode_parse(output)
            if decoded and self.output_loop is not None:
                self.output_loop.create_task(self._publish_output(decoded))

    def refresh_runtime_state(self) -> bool:
        process = self.process
        if process is None:
            self.process_is_running = False
            self.runtime_state = "stopped"
            return False

        if process.returncode is not None:
            self.process_is_running = False
            self.runtime_state = "stopped"
            return False

        try:
            os.kill(process.pid, 0)
        except OSError:
            self.process_is_running = False
            self.runtime_state = "stopped"
            return False

        self.process_is_running = True
        if self.runtime_state not in {"starting", "running"}:
            self.runtime_state = "running"
        return True

    async def _finalize_process_exit(self, pid: Optional[int]) -> None:
        if self.finished_logged:
            return

        self.finished_logged = True
        await self.log_storage.add_log(ProcessLog(message="Process finished."))
        if self.project_id:
            append_instance_log(
                project_id=self.project_id,
                project_name=self.project_name,
                message="终端会话已结束。",
                source="terminal",
                level="INFO",
            )
            if pid is not None:
                append_instance_log(
                    project_id=self.project_id,
                    project_name=self.project_name,
                    message=f"终端会话已停止。pid={pid}",
                    source="terminal",
                    level="WARNING",
                )

    def _cleanup_fds(self) -> None:
        if self.output_loop is not None and self.master_fd is not None and self._reader_registered:
            try:
                self.output_loop.remove_reader(self.master_fd)
            except Exception:
                pass
            self._reader_registered = False

        for fd_name in ("master_fd", "slave_fd"):
            fd = getattr(self, fd_name)
            if fd is None:
                continue
            try:
                os.close(fd)
            except OSError:
                pass
            setattr(self, fd_name, None)

    async def _wait_for_exit(self) -> None:
        process = self.process
        if process is None:
            return

        pid = process.pid
        try:
            await process.wait()
        finally:
            self.process_is_running = False
            self.runtime_state = "stopped"
            self._cleanup_fds()
            await self._finalize_process_exit(pid)

    async def start(self) -> None:
        if self.refresh_runtime_state():
            return

        self.output_loop = asyncio.get_running_loop()
        self.master_fd, self.slave_fd = pty.openpty()
        os.set_blocking(self.master_fd, False)

        self.process = await asyncio.create_subprocess_exec(
            *self.args,
            cwd=self.cwd,
            env=self.env,
            stdin=self.slave_fd,
            stdout=self.slave_fd,
            stderr=self.slave_fd,
            start_new_session=True,
        )

        try:
            os.close(self.slave_fd)
        except OSError:
            pass
        self.slave_fd = None

        self.output_loop.add_reader(self.master_fd, self._handle_master_ready)
        self._reader_registered = True
        self.wait_task = self.output_loop.create_task(self._wait_for_exit())
        self.process_is_running = True
        self.runtime_state = "running"
        self.finished_logged = False

        if self.project_id:
            append_instance_log(
                project_id=self.project_id,
                project_name=self.project_name,
                message="维护终端会话已启动。",
                source="terminal",
                level="INFO",
            )

    async def stop(self) -> None:
        process = self.process
        pid = process.pid if process else None
        was_running = self.refresh_runtime_state()

        if process is not None and was_running:
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except OSError:
                try:
                    process.terminate()
                except ProcessLookupError:
                    pass

            try:
                await asyncio.wait_for(process.wait(), timeout=5)
            except asyncio.TimeoutError:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except OSError:
                    try:
                        process.kill()
                    except ProcessLookupError:
                        pass
                try:
                    await asyncio.wait_for(process.wait(), timeout=3)
                except asyncio.TimeoutError:
                    log.warning(f"PTY terminal force kill wait timed out for pid={process.pid}.")

        self.process_is_running = False
        self.runtime_state = "stopped"
        self._cleanup_fds()

        current_task = asyncio.current_task()
        if self.wait_task and self.wait_task is not current_task:
            self.wait_task.cancel()
        self.wait_task = None

        await self._finalize_process_exit(pid)

    async def write_stdin(self, data: bytes) -> int:
        if not self.refresh_runtime_state() or self.master_fd is None:
            raise ProcessNotRunning()

        return os.write(self.master_fd, data)

    async def interrupt(self) -> None:
        if not self.refresh_runtime_state():
            raise ProcessNotRunning()

        try:
            await self.write_stdin(b"\x03")
        except Exception:
            if self.process is None:
                raise ProcessNotRunning()
            os.killpg(self.process.pid, signal.SIGINT)

    async def resize(self, cols: int, rows: int) -> None:
        if (
            self.master_fd is None
            or cols <= 0
            or rows <= 0
            or fcntl is None
            or termios is None
        ):
            return

        winsize = struct.pack("HHHH", rows, cols, 0, 0)
        fcntl.ioctl(self.master_fd, termios.TIOCSWINSZ, winsize)

    def get_status(self) -> ProcessInfo:
        is_running = self.refresh_runtime_state()
        return ProcessInfo(
            status_code=self.process.returncode if self.process else None,
            total_log=self.log_storage.get_count(),
            is_running=is_running,
            performance=None,
        )
