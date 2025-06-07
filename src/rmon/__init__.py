"""rmon package"""

import importlib.metadata as metadata

from rmon.models import (
    CompleteProcessesCommand,
    ComputeNodeResourceStatConfig,
    ComputeNodeResourceStatResults,
    ProcessStatResults,
    ResourceType,
    ShutDownCommand,
    UpdatePidsCommand,
)
from rmon.timing.timer_stats import Timer, TimerStatsCollector, track_timing
from rmon.timing.timer_utils import timed_info, timed_threshold
from rmon.resource_monitor import run_monitor_async, run_monitor_sync


__version__ = metadata.metadata("rmon")["Version"]


__all__ = (
    "CompleteProcessesCommand",
    "ComputeNodeResourceStatConfig",
    "ComputeNodeResourceStatResults",
    "ProcessStatResults",
    "ResourceType",
    "ShutDownCommand",
    "Timer",
    "TimerStatsCollector",
    "UpdatePidsCommand",
    "run_monitor_async",
    "run_monitor_sync",
    "timed_info",
    "timed_threshold",
    "track_timing",
)
