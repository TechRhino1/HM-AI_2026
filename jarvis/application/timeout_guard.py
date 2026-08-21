"""
JARVIS AI 3.0 — Timeout Guard Utilities.
Protects the system against hanging network calls, slow analytical agents, and unresponsive I/O operations.
"""
import asyncio
import inspect
import functools
import logging
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from typing import Any, Callable, Optional, TypeVar

T = TypeVar("T")
logger = logging.getLogger("JARVIS_TimeoutGuard")

class TimeoutGuard:
    """Thread pool and asyncio-based timeout manager for synchronous and asynchronous tasks."""
    _executor = ThreadPoolExecutor(max_workers=16, thread_name_prefix="jarvis_guard")

    @classmethod
    def run_sync(
        cls,
        func: Callable[..., T],
        *args: Any,
        timeout_sec: float = 3.0,
        default: Optional[Any] = None,
        task_name: str = "Task",
        **kwargs: Any
    ) -> T:
        """Executes a synchronous blocking function with a hard wall-clock timeout."""
        future = cls._executor.submit(func, *args, **kwargs)
        try:
            return future.result(timeout=timeout_sec)
        except FuturesTimeoutError:
            logger.warning(f"TimeoutGuard: {task_name} exceeded timeout limit of {timeout_sec:.2f}s! Returning default fallback.")
            return default() if callable(default) else default
        except Exception as e:
            logger.error(f"TimeoutGuard: Error in {task_name}: {e}", exc_info=True)
            return default() if callable(default) else default

    @classmethod
    async def run_async(
        cls,
        coro: Any,
        timeout_sec: float = 3.0,
        default: Optional[Any] = None,
        task_name: str = "AsyncTask"
    ) -> T:
        """Executes an asynchronous coroutine with an asyncio timeout."""
        try:
            return await asyncio.wait_for(coro, timeout=timeout_sec)
        except asyncio.TimeoutError:
            logger.warning(f"TimeoutGuard: {task_name} exceeded async timeout of {timeout_sec:.2f}s! Returning default fallback.")
            return default() if callable(default) else default
        except Exception as e:
            logger.error(f"TimeoutGuard: Async error in {task_name}: {e}", exc_info=True)
            return default() if callable(default) else default

def timeout_guarded(timeout_sec: float = 3.0, default: Any = None, task_name: Optional[str] = None):
    """Decorator to enforce strict timeout protection on functions."""
    def decorator(func: Callable):
        name = task_name or func.__name__

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return TimeoutGuard.run_sync(func, *args, timeout_sec=timeout_sec, default=default, task_name=name, **kwargs)

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            return await TimeoutGuard.run_async(func(*args, **kwargs), timeout_sec=timeout_sec, default=default, task_name=name)

        if inspect.iscoroutinefunction(func):
            return async_wrapper
        return wrapper
    return decorator
