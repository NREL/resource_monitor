"""Utility functions for timing measurements."""

import functools
import time
from typing import Any, Callable

from loguru import logger


def timed_info(func) -> Callable:
    """Decorator to measure and log a function's execution time."""

    @functools.wraps(func)
    def timed(*args, **kwargs):
        return _log_timed(func, logger.info, *args, **kwargs)

    return timed


def timed_threshold(threshold: float) -> Callable:
    """Decorator to log a warning if a function's execution time exceeds a threshold."""

    def wrap(func):
        @functools.wraps(func)
        def timed(*args, **kwargs):
            return _log_if_threshold_exceeded(func, threshold, *args, **kwargs)

        return timed

    return wrap


def get_time_duration_string(seconds: float) -> str:
    """Returns a string with the time converted to reasonable units."""
    # pylint: disable=consider-using-f-string
    if seconds >= 1:
        val = "{:.3f} s".format(seconds)
    elif seconds >= 0.001:
        val = "{:.3f} ms".format(seconds * 1_000)
    elif seconds >= 0.000001:
        val = "{:.3f} us".format(seconds * 1_000_000)
    elif seconds == 0:
        val = "0 s"
    else:
        val = "{:.3f} ns".format(seconds * 1_000_000_000)
    # pylint: enable=consider-using-f-string

    return val


def _log_timed(func: Callable, log_func: Callable, *args, **kwargs) -> Any:
    start = time.perf_counter()
    try:
        result = func(*args, **kwargs)
        return result
    finally:
        total = time.perf_counter() - start
        log_func(
            "execution-time={} func={}",
            get_time_duration_string(total),
            func.__qualname__,
        )


def _log_if_threshold_exceeded(func: Callable, threshold: float, *args, **kwargs) -> Any:
    start = time.perf_counter()
    try:
        result = func(*args, **kwargs)
        return result
    finally:
        total = time.perf_counter() - start
        if total > threshold:
            logger.warning(
                "func={} exceeded threshold execution-time={} threshold={}",
                func.__qualname__,
                total,
                threshold,
            )
