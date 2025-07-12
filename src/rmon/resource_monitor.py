"""Performs resource utilization monitoring."""

import multiprocessing
import multiprocessing.connection
import signal
import socket
import sys
import time
from pathlib import Path
from typing import Any, Optional

from loguru import logger
from .common import DEFAULT_BUFFERED_WRITE_COUNT
from .models import ComputeNodeResourceStatConfig
from .loggers import setup_logging
from .models import (
    CompleteProcessesCommand,
    CommandBaseModel,
    ComputeNodeResourceStatResults,
    ComputeNodeProcessResourceStatResults,
    SelectStatsCommand,
    ShutDownCommand,
    UpdatePidsCommand,
)
from .resource_stat_collector import ResourceStatCollector
from .resource_stat_aggregator import ResourceStatAggregator
from .resource_stat_store import ResourceStatStore


def run_monitor_async(
    conn: multiprocessing.connection.Connection,
    config: ComputeNodeResourceStatConfig,
    pids: dict[str, int],
    log_file: Path,
    db_file: Path | None,
    name: str = socket.gethostname(),
    buffered_write_count: int = DEFAULT_BUFFERED_WRITE_COUNT,
) -> None:
    """Run a ResourceStatAggregator in a loop. Must be called from a child process.

    Parameters
    ----------
    conn : multiprocessing.connection.Connection
        Child side of the pipe
    config : ComputeNodeResourceStatConfig
    pids : dict
        Process IDs to monitor ({process_key: pid})
    log_file : Path
    db_file : Path | None
        Path to store database if monitor_type = "periodic"
    buffered_write_count : int
        Number of intervals to cache in memory before persisting to database.
    """
    setup_logging(filename=log_file, mode="w")
    logger.info("Monitor resource utilization with config={}", config)
    collector = ResourceStatCollector()
    stats = collector.get_stats(ComputeNodeResourceStatConfig.all_enabled(), pids={})
    agg = ResourceStatAggregator(config, stats)
    if config.monitor_type == "periodic" and db_file is None:
        msg = "path must be set if monitor_type is periodic"
        raise ValueError(msg)
    store = (
        ResourceStatStore(
            config, db_file.absolute(), stats, name=name, buffered_write_count=buffered_write_count
        )
        if config.monitor_type == "periodic" and db_file is not None
        else None
    )

    results = None
    cmd_poll_interval = 1
    last_job_poll_time = 0.0
    while True:
        if conn.poll():
            cmd, results = _process_command(conn, agg, store, config)
            if isinstance(cmd, ShutDownCommand):
                break
            pids = cmd.pids

        cur_time = time.time()
        if cur_time - last_job_poll_time > config.interval:
            logger.debug("Collect stats")
            stats = collector.get_stats(config, pids=pids)
            agg.update_stats(stats)
            if store is not None:
                store.record_stats(stats)
            last_job_poll_time = cur_time

        time.sleep(cmd_poll_interval)

    conn.send(results)
    collector.clear_cache()


def _process_command(
    conn: Any,
    agg: ResourceStatAggregator,
    store: Optional[ResourceStatStore],
    config: ComputeNodeResourceStatConfig,
) -> tuple[
    CommandBaseModel,
    None | tuple[ComputeNodeResourceStatResults, ComputeNodeProcessResourceStatResults],
]:
    results = None
    cmd = conn.recv()
    logger.debug("Received command {}", cmd)
    if isinstance(cmd, CompleteProcessesCommand):
        result = agg.finalize_process_stats(cmd.completed_process_keys)
        conn.send(result)
    elif isinstance(cmd, SelectStatsCommand):
        config = cmd.config
        agg.config = config
        if store is not None:
            store.config = config
    elif isinstance(cmd, UpdatePidsCommand):
        config = cmd.config
        agg.config = config
        if store is not None:
            store.config = config
    elif isinstance(cmd, ShutDownCommand):
        results = (agg.finalize_system_stats(), agg.finalize_process_stats(cmd.pids))
        if store is not None:
            store.flush()
            if config.make_plots:
                store.plot_to_file()
    else:
        msg = f"Bug: need to implement support for {cmd=}"
        raise NotImplementedError(msg)

    return cmd, results


_g_collect_stats = True


def run_monitor_sync(
    config: ComputeNodeResourceStatConfig,
    pids: dict[str, int],
    duration: int | None,
    db_file: Path | None = None,
    name: str = socket.gethostname(),
    buffered_write_count: int = DEFAULT_BUFFERED_WRITE_COUNT,
) -> tuple[ComputeNodeResourceStatResults, ComputeNodeProcessResourceStatResults]:
    """Run a ResourceStatAggregator in a loop.

    Parameters
    ----------
    config : ComputeNodeResourceStatConfig
    pids : dict
        Process IDs to monitor ({process_key: pid})
    db_file : Path | None
        Path to store database if monitor_type = "periodic"
    duration : int | None
    buffered_write_count : int
        Number of intervals to cache in memory before persisting to database.
    """
    logger.info("Monitor resource utilization with config={} duration={}", config, duration)
    collector = ResourceStatCollector()
    stats = collector.get_stats(ComputeNodeResourceStatConfig.all_enabled(), pids={})
    agg = ResourceStatAggregator(config, stats)
    if config.monitor_type == "periodic" and db_file is None:
        msg = "db_file must be set if monitor_type is periodic"
        raise ValueError(msg)
    store = (
        ResourceStatStore(
            config, db_file.absolute(), stats, name=name, buffered_write_count=buffered_write_count
        )
        if config.monitor_type == "periodic" and db_file is not None
        else None
    )

    signal.signal(signal.SIGTERM, _sigterm_handler)
    start_time = time.time()
    try:
        while _g_collect_stats and (duration is None or time.time() - start_time < duration):
            logger.debug("Collect stats")
            stats = collector.get_stats(config, pids=pids)
            agg.update_stats(stats)
            if store is not None:
                store.record_stats(stats)

            time.sleep(config.interval)
    except KeyboardInterrupt:
        print("Detected Ctrl-c...exiting", file=sys.stderr)

    system_results = agg.finalize_system_stats()
    process_results = agg.finalize_process_stats(pids)
    if store is not None:
        store.flush()
        store.plot_to_file()
    collector.clear_cache()
    return system_results, process_results


def _sigterm_handler(signum, frame):  # pylint: disable=unused-argument
    global _g_collect_stats  # pylint: disable=global-statement
    print("Detected SIGTERM", file=sys.stderr)
    _g_collect_stats = False
