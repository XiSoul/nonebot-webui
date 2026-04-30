import os
import asyncio
import subprocess
import signal
from pathlib import Path
from typing import Dict, Union, Optional, AsyncIterator

import psutil
from nb_cli.consts import WINDOWS
from nb_cli.handlers.process import terminate_process

from nb_cli_plugin_webui.app.logging import logger as log
from nb_cli_plugin_webui.app.utils.global_log import append_instance_log
from nb_cli_plugin_webui.app.utils.string_utils import decode_parse

from .exceptions import ProcessAlreadyExists, ProcessNotRunning
from .log import LogStorage as BaseLogStorage
from .schemas import ProcessLog, ProcessInfo, ProcessPerformance

SHELL_COMMAND_DONE_MARKER = "__NB_WEBUI_CMD_DONE__:"


class LogStorage(BaseLogStorage[ProcessLog]):
    max_logs = 2000

    async def add_log(self, log: ProcessLog) -> int:
        log_seq = len(self.logs) + 1
        self.logs[log_seq] = log

        while len(self.logs) > self.max_logs:
            oldest_seq = next(iter(self.logs))
            self.logs.pop(oldest_seq, None)

        await self._notify_listeners(log)
        return log_seq


class Processor:
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
        terminate_duplicate_processes: bool = True,
    ) -> None:
        self.args = args
        self.cwd = cwd
        self.env = env
        self.log_storage = LogStorage(log_destroy_seconds)
        self.project_id = project_id
        self.project_name = project_name
        self.terminate_duplicate_processes = terminate_duplicate_processes

        self.process_event = asyncio.Event()
        self.output_task = None
        self.error_task = None
        self.finished_logged = False

    def _repair_project_executable(self) -> None:
        if WINDOWS or not self.args:
            return

        try:
            executable = Path(os.fspath(self.args[0]))
        except TypeError:
            return

        if not executable.is_absolute():
            executable = (self.cwd / executable).resolve()

        try:
            executable.relative_to(self.cwd.resolve())
        except ValueError:
            return

        if not executable.is_file() or os.access(str(executable), os.X_OK):
            return

        try:
            executable.chmod(executable.stat().st_mode | 0o111)
            log.warning(f"Executable permission repaired for {executable} before project start.")
        except Exception:
            pass

    async def _find_duplicate_process(self) -> AsyncIterator[int]:
        for process in psutil.process_iter():
            try:
                with process.oneshot():
                    pid = process.pid
                    cwd = Path(process.cwd()).absolute()
            except psutil.Error:
                continue

            if not (cwd.is_dir()):
                continue
            if self.cwd.absolute() == cwd:
                process.terminate()
                yield pid

        return

    async def _process_executer(self) -> Optional[int]:
        self.process = await asyncio.create_subprocess_exec(
            *self.args,
            cwd=self.cwd,
            env=self.env,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            creationflags=(
                subprocess.CREATE_NEW_PROCESS_GROUP if WINDOWS else 0  # type: ignore
            ),
        )
        assert self.process.stdin and self.process.stdout

        async def read_output():
            async for output in self.process.stdout:  # type: ignore
                output = decode_parse(output)
                if not output:
                    continue

                if output.startswith(SHELL_COMMAND_DONE_MARKER):
                    exit_code = output.removeprefix(SHELL_COMMAND_DONE_MARKER).strip()
                    log_model = ProcessLog(message=f"命令执行结束，退出码: {exit_code}")
                    await self.log_storage.add_log(log_model)
                    if self.project_id:
                        append_instance_log(
                            project_id=self.project_id,
                            project_name=self.project_name,
                            message=f"命令执行结束，退出码: {exit_code}",
                            source="runtime",
                            level="INFO",
                        )
                    continue

                log_model = ProcessLog(message=output)
                await self.log_storage.add_log(log_model)
                if self.project_id:
                    append_instance_log(
                        project_id=self.project_id,
                        project_name=self.project_name,
                        message=output,
                        source="runtime",
                    )

        if self.process.stdout:
            self.output_task = asyncio.create_task(read_output())

        async def error_exit():
            if self.process:
                await self.process.wait()
                await self.stop()

        self.error_task = asyncio.create_task(error_exit())  # type: ignore

    def refresh_runtime_state(self) -> bool:
        process = self.process
        if process is None:
            self.process_is_running = False
            return False

        if process.returncode is not None:
            self.process_is_running = False
            return False

        try:
            ps = psutil.Process(process.pid)
            if not ps.is_running() or ps.status() == psutil.STATUS_ZOMBIE:
                self.process_is_running = False
                return False
        except psutil.Error:
            self.process_is_running = False
            return False

        self.process_is_running = True
        return True

    async def _finalize_process_exit(self, pid: Optional[int]) -> None:
        if self.finished_logged:
            return

        self.finished_logged = True

        log_model = ProcessLog(message="Process finished.")
        await self.log_storage.add_log(log_model)
        if self.project_id:
            append_instance_log(
                project_id=self.project_id,
                project_name=self.project_name,
                message="实例进程输出结束。",
                source="process-manager",
                level="INFO",
            )
            if pid is not None:
                append_instance_log(
                    project_id=self.project_id,
                    project_name=self.project_name,
                    message=f"实例进程已停止。pid={pid}",
                    source="process-manager",
                    level="WARNING",
                )

    def get_status(self) -> ProcessInfo:
        is_running = self.refresh_runtime_state()
        if not self.process or not is_running:
            return ProcessInfo(
                status_code=self.process.returncode if self.process else None,
                total_log=self.log_storage.get_count(),
                is_running=False,
                performance=None,
            )

        with (ps := psutil.Process(self.process.pid)).oneshot():
            cpu = ps.cpu_percent(interval=None)
            mem = ps.memory_percent()

        return ProcessInfo(
            status_code=self.process.returncode,
            total_log=self.log_storage.get_count(),
            is_running=True,
            performance=ProcessPerformance(cpu=cpu, mem=mem),
        )

    async def start(self) -> None:
        if self.refresh_runtime_state():
            return

        if self.terminate_duplicate_processes:
            async for pid in self._find_duplicate_process():
                log.warning(f"Possible process {pid=} found, terminated.")

        self._repair_project_executable()
        await self._process_executer()
        self.process_is_running = True
        self.finished_logged = False
        if self.project_id:
            append_instance_log(
                project_id=self.project_id,
                project_name=self.project_name,
                message="实例进程已启动。",
                source="process-manager",
                level="INFO",
            )

    async def stop(self):
        pid = self.process.pid if self.process else None
        was_running = self.refresh_runtime_state()

        if self.process and was_running:
            pid = self.process.pid
            try:
                await asyncio.wait_for(terminate_process(self.process), timeout=5)
            except asyncio.TimeoutError:
                log.warning(f"Process stop timed out for pid={pid}, force killing process tree.")
                try:
                    ps = psutil.Process(pid)
                    for child in ps.children(recursive=True):
                        try:
                            child.kill()
                        except psutil.Error:
                            pass
                    ps.kill()
                except psutil.Error:
                    pass
                try:
                    await asyncio.wait_for(self.process.wait(), timeout=3)
                except asyncio.TimeoutError:
                    log.warning(f"Process force kill wait timed out for pid={pid}.")
            self.process_is_running = False
            log.info(f"Process {pid=} terminated.")

        self.process_is_running = False

        if self.output_task:
            self.output_task.cancel()
            self.output_task = None

        current_task = asyncio.current_task()
        if self.error_task and self.error_task is not current_task:
            self.error_task.cancel()
        self.error_task = None

        await self._finalize_process_exit(pid)

    async def write_stdin(self, data: bytes) -> int:
        if not self.refresh_runtime_state() or self.process is None or self.process.stdin is None:
            raise ProcessNotRunning()
        self.process.stdin.write(data)
        await self.process.stdin.drain()
        return len(data)

    async def interrupt(self) -> None:
        if not self.refresh_runtime_state() or self.process is None:
            raise ProcessNotRunning()

        if WINDOWS:
            self.process.send_signal(signal.CTRL_BREAK_EVENT)  # type: ignore[attr-defined]
        else:
            self.process.send_signal(signal.SIGINT)

        log_model = ProcessLog(message="Sent interrupt signal.")
        await self.log_storage.add_log(log_model)
        if self.project_id:
            append_instance_log(
                project_id=self.project_id,
                project_name=self.project_name,
                message="已向实例发送中断信号。",
                source="process-manager",
                level="WARNING",
            )


class ProcessManager:
    processes: Dict[str, Processor] = dict()

    get_process = processes.get

    @classmethod
    def add_process(cls, process: Processor, key: str) -> None:
        if key in cls.processes:
            raise ProcessAlreadyExists
        cls.processes[key] = process

    @classmethod
    def remove_process(cls, key: str) -> None:
        process = cls.processes.pop(key)
        process.log_storage.listeners.clear()
        return
