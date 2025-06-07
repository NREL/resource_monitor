"""Collects statistics for timed code segments."""

import functools
import json
import time
from pathlib import Path
from typing import Any, Callable, Optional

from loguru import logger


class TimerStats:
    """Tracks timing stats for one code block."""

    def __init__(self, name: str) -> None:
        self._name = name
        self._count = 0
        self._max = 0.0
        self._min: Optional[float] = None
        self._avg = 0.0
        self._total = 0.0

    def get_stats(self) -> dict[str, Any]:
        """Get the current stats summary.

        Returns
        -------
        dict

        """
        avg = 0 if self._count == 0 else self._total / self._count
        return {
            "min": self._min,
            "max": self._max,
            "total": self._total,
            "avg": avg,
            "count": self._count,
        }

    def log_stats(self) -> None:
        """Log a summary of the stats."""
        if self._count == 0:
            logger.info("No stats have been recorded for {}.", self._name)
            return

        x = self.get_stats()
        text = (
            f"total={x['total']} avg={x['avg']} max={x['max']} min={x['min']} count={x['count']}"
        )
        logger.info("TimerStats summary: {}: {}", self._name, text)

    def update(self, duration: float) -> None:
        """Update the stats with a new timing."""
        self._count += 1
        self._total += duration
        if duration > self._max:
            self._max = duration
        if self._min is None or duration < self._min:
            self._min = duration


class TimerStatsCollector:
    """Collects statistics for timed code segments."""

    def __init__(self, is_enabled: bool = False) -> None:
        self._stats: dict[str, TimerStats] = {}
        self._is_enabled = is_enabled

    def clear(self) -> None:
        """Clear all stats."""
        self._stats.clear()

    def disable(self) -> None:
        """Disable timing."""
        self._is_enabled = False

    def enable(self) -> None:
        """Enable timing."""
        self._is_enabled = True

    def get_stat(self, name) -> TimerStats | None:
        """Return a TimerStats. Return None if timing is disabled."""
        if not self._is_enabled:
            return None
        if name not in self._stats:
            self.register_stat(name)
        return self._stats[name]

    @property
    def is_enabled(self) -> bool:
        """Return True if timing is enabled."""
        return self._is_enabled

    def log_json_stats(self, filename: Path, clear: bool = False) -> None:
        """Log line-delimited JSON stats to filename.

        Parameters
        ----------
        filename: Path
        clear : bool
            If True, clear all stats.
        """
        if self._is_enabled:
            with open(filename, "a", encoding="utf-8") as f:
                for name, stat in self._stats.items():
                    row = {"name": name}
                    row.update(stat.get_stats())
                    f.write(json.dumps(row))
                    f.write("\n")
            if clear:
                self.clear()

    def log_stats(self, clear: bool = False) -> None:
        """Log statistics for all tracked stats.

        Parameters
        ----------
        clear : bool
            If True, clear all stats.
        """
        if self._is_enabled:
            for stat in self._stats.values():
                stat.log_stats()
            if clear:
                self.clear()

    def register_stat(self, name: str) -> None:
        """Register tracking of a new stat."""
        if self._is_enabled:
            assert name not in self._stats
            stat = TimerStats(name)
            self._stats[name] = stat


class Timer:
    """Times a code block.
    This should not be used for code blocks with short execution times that
    are called many times because of timing and bookkeeping overhead.
    """

    def __init__(self, collector: TimerStatsCollector, name: str) -> None:
        self._start = 0.0
        self._timer_stat = collector.get_stat(name) if collector.is_enabled else None

    def __enter__(self):
        if self._timer_stat is not None:
            self._start = time.perf_counter()

    def __exit__(self, exc, value, tb):  # pylint: disable=unused-argument
        if self._timer_stat is not None:
            self._timer_stat.update(time.perf_counter() - self._start)


def track_timing(collector: TimerStatsCollector) -> Callable:
    """Decorator to track statistics on a function's execution time.
    This should not be used for functions with short execution times that
    are called many times because of timing and bookkeeping overhead.

    Parameters
    ----------
    collector : TimerStatsCollector
    """

    def wrap(func):
        @functools.wraps(func)
        def timed(*args, **kwargs):
            return _timed_func(collector, func, *args, **kwargs)

        return timed

    return wrap


def _timed_func(collector: TimerStatsCollector, func: Callable, *args, **kwargs) -> Any:
    if collector.is_enabled:
        with Timer(collector, func.__qualname__):
            return func(*args, **kwargs)
    else:
        return func(*args, **kwargs)
