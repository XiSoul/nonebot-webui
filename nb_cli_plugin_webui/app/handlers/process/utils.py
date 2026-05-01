import asyncio
import traceback
from typing import Any, Dict, List, Tuple, Callable, Optional

from .log import LogStorage
from .schemas import CustomLog


class ProcessFuncWithLog:
    def __init__(self, log: LogStorage) -> None:
        self.log = log
        self.queue: List[
            Tuple[Callable[..., Any], Tuple[Any, ...], Dict[str, Any]]
        ] = list()
        self.on_error: List[
            Tuple[Callable[..., Any], Tuple[Any, ...], Dict[str, Any]]
        ] = list()

    async def _err_parse(
        self, err: Exception, additional_err_msg: Optional[str] = None
    ) -> None:
        log_model = CustomLog(message=str(err))
        await self.log.add_log(log_model)

        traceback_info = traceback.format_exc()
        log_model = CustomLog(message=traceback_info)
        await self.log.add_log(log_model)

        if additional_err_msg:
            log_model = CustomLog(message=additional_err_msg)
            await self.log.add_log(log_model)

        log_model = CustomLog(message="❌ Failed!")
        await self.log.add_log(log_model)

        self.queue.clear()

    def add(
        self,
        func: Callable,
        *args,
        **kwargs,
    ) -> "ProcessFuncWithLog":
        self.queue.append((func, args, kwargs))
        return self

    def add_on_error(
        self,
        func: Callable,
        *args,
        **kwargs,
    ) -> "ProcessFuncWithLog":
        self.on_error.append((func, args, kwargs))
        return self

    async def _done(self, additional_err_msg: Optional[str]) -> None:
        for func, args, kwargs in self.queue:
            try:
                if asyncio.iscoroutinefunction(func):
                    await func(*args, **kwargs)
                else:
                    await asyncio.to_thread(func, *args, **kwargs)
            except Exception as err:
                await self._err_parse(err, additional_err_msg)
                for rollback_func, rollback_args, rollback_kwargs in self.on_error:
                    try:
                        if asyncio.iscoroutinefunction(rollback_func):
                            await rollback_func(*rollback_args, **rollback_kwargs)
                        else:
                            await asyncio.to_thread(
                                rollback_func, *rollback_args, **rollback_kwargs
                            )
                    except Exception:
                        continue
                break

    def done(self, *, additional_err_msg: Optional[str] = None) -> None:
        asyncio.create_task(self._done(additional_err_msg))
