"""Monitors resource utilization statistics"""

import multiprocessing
import time
from typing import Any, Iterable, Optional

import psutil
from loguru import logger

from .models import ResourceType, ComputeNodeResourceStatConfig


ONE_MB = 1024 * 1024


class ResourceStatCollector:
    """Collects resource utilization statistics"""

    DISK_STATS = (
        "read_count",
        "write_count",
        "read_bytes",
        "write_bytes",
        "read_time",
        "write_time",
    )
    NET_STATS = (
        "bytes_recv",
        "bytes_sent",
        "dropin",
        "dropout",
        "errin",
        "errout",
        "packets_recv",
        "packets_sent",
    )

    def __init__(self) -> None:
        self._last_disk_check_time: Optional[float] = None
        self._last_net_check_time: Optional[float] = None
        self._update_disk_stats(psutil.disk_io_counters())
        self._update_net_stats(psutil.net_io_counters())
        self._cached_processes: dict[int, psutil.Process] = {}
        self._max_process_cpu_percent = multiprocessing.cpu_count() * 100

    def _update_disk_stats(self, data: Any):
        for stat in self.DISK_STATS:
            setattr(self, stat, getattr(data, stat, 0))
        self._last_disk_check_time = time.time()

    def _update_net_stats(self, data: Any):
        for stat in self.NET_STATS:
            setattr(self, stat, getattr(data, stat, 0))
        self._last_net_check_time = time.time()

    def get_stats(
        self, config: ComputeNodeResourceStatConfig, pids: Optional[dict[str, int]] = None
    ) -> dict[ResourceType, dict[str, Any]]:
        """Return a dict keyed by ResourceType of all enabled stats."""
        data: dict[ResourceType, dict[str, Any]] = {}
        if config.cpu:
            data[ResourceType.CPU] = self.get_cpu_stats()
        if config.disk:
            data[ResourceType.DISK] = self.get_disk_stats()
        if config.memory:
            data[ResourceType.MEMORY] = self.get_memory_stats()
        if config.network:
            data[ResourceType.NETWORK] = self.get_network_stats()
        if config.process:
            if pids is None:
                msg = "pids cannot be None if process stats are enabled"
                raise ValueError(msg)
            data[ResourceType.PROCESS] = self.get_processes_stats(pids, config)
        return data

    def get_cpu_stats(self) -> dict[str, Any]:
        """Gets CPU current resource stats information."""
        stats = psutil.cpu_times_percent()._asdict()
        stats["cpu_percent"] = psutil.cpu_percent()
        return stats

    def get_disk_stats(self) -> dict[str, Any]:
        """Gets current disk stats."""
        assert self._last_disk_check_time is not None
        data = psutil.disk_io_counters()
        stats: dict[str, Any] = {
            "elapsed_seconds": time.time() - self._last_disk_check_time,
        }
        for stat in self.DISK_STATS:
            stats[stat] = getattr(data, stat, 0) - getattr(self, stat, 0)
        stats["read MB/s"] = self._mb_per_sec(stats["read_bytes"], stats["elapsed_seconds"])
        stats["write MB/s"] = self._mb_per_sec(stats["write_bytes"], stats["elapsed_seconds"])
        stats["read IOPS"] = float(stats["read_count"]) / stats["elapsed_seconds"]
        stats["write IOPS"] = float(stats["write_count"]) / stats["elapsed_seconds"]
        self._update_disk_stats(data)
        return stats

    def get_memory_stats(self) -> dict[str, Any]:
        """Gets current memory resource stats."""
        return psutil.virtual_memory()._asdict()

    def get_network_stats(self) -> dict[str, Any]:
        """Gets current network stats."""
        assert self._last_net_check_time is not None
        data = psutil.net_io_counters()
        stats = {
            "elapsed_seconds": time.time() - self._last_net_check_time,
        }
        for stat in self.NET_STATS:
            stats[stat] = getattr(data, stat, 0) - getattr(self, stat, 0)
        stats["recv MB/s"] = self._mb_per_sec(stats["bytes_recv"], stats["elapsed_seconds"])
        stats["sent MB/s"] = self._mb_per_sec(stats["bytes_sent"], stats["elapsed_seconds"])
        self._update_net_stats(data)
        return stats

    def _get_process(self, pid: int) -> psutil.Process | None:
        process = self._cached_processes.get(pid)
        if process is None:
            try:
                process = psutil.Process(pid)
                # Initialize CPU utilization tracking per psutil docs.
                process.cpu_percent(interval=0.25)
                self._cached_processes[pid] = process
            except psutil.NoSuchProcess:
                logger.warning("PID={} does not exist", pid)
                return None
            except psutil.AccessDenied:
                logger.warning("PID={}: access denied", pid)
                return None

        return process

    def clear_cache(self) -> None:
        """Clear all cached data."""
        self._cached_processes.clear()

    def clear_stale_processes(self, cur_pids: Iterable[int]) -> None:
        """Remove cached process objects that are no longer running."""
        for pid in set(self._cached_processes).difference(cur_pids):
            self._cached_processes.pop(pid)

    def get_processes_stats(self, pids, config: ComputeNodeResourceStatConfig) -> dict[str, Any]:
        """Return stats for multiple processes."""
        stats: dict[str, Any] = {}
        cur_pids = set()
        for name, pid in pids.items():
            _stats, children = self.get_process_stats(pid, config)
            if _stats is not None:
                stats[name] = _stats
                cur_pids.add(pid)
                cur_pids.update(children)

        self.clear_stale_processes(cur_pids)
        logger.debug("Collected process stats for PIDs={}", list(pids.values()))
        return stats

    def get_process_stats(
        self, pid: int, config: ComputeNodeResourceStatConfig
    ) -> tuple[Optional[dict[str, Any]], list[int]]:
        """Return stats for one process. Returns None if the pid does not exist."""
        children: list[int] = []
        process = self._get_process(pid)
        if process is None:
            return None, children
        try:
            with process.oneshot():
                cpu_percent = process.cpu_percent()
                rss = process.memory_info().rss
                if cpu_percent > self._max_process_cpu_percent:
                    logger.warning("Invalid process CPU measurement: {}", cpu_percent)
                    cpu_percent = self._max_process_cpu_percent

                stats = {"cpu_percent": cpu_percent, "rss": rss}
                if config.include_child_processes:
                    for child in process.children(recursive=config.recurse_child_processes):
                        cached_child = self._get_process(child.pid)
                        if cached_child is not None:
                            stats["cpu_percent"] += cached_child.cpu_percent()
                            stats["rss"] += cached_child.memory_info().rss
                            children.append(child.pid)
                return stats, children
        except psutil.NoSuchProcess:
            logger.warning("PID={} does not exist", pid)
            return None, []
        except psutil.AccessDenied:
            logger.warning("PID={}: access denied", pid)
            return None, []

    @staticmethod
    def _mb_per_sec(num_bytes, elapsed_seconds) -> float:
        return float(num_bytes) / ONE_MB / elapsed_seconds
