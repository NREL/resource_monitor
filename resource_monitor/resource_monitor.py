"""Performs resource utilization monitoring."""

import logging
import signal
import socket
import sys
import time

from .common import DEFAULT_BUFFERED_WRITE_COUNT
from .models import ComputeNodeResourceStatConfig
from .loggers import setup_logging
from .models import (
    CompleteProcessesCommand,
    SelectStatsCommand,
    ShutDownCommand,
    UpdatePidsCommand,
)
from .resource_stat_collector import ResourceStatCollector
from .resource_stat_aggregator import ResourceStatAggregator
from .resource_stat_store import ResourceStatStore


logger = logging.getLogger(__name__)


def run_monitor_async(
    conn,
    config: ComputeNodeResourceStatConfig,
    pids,
    log_file,
    db_file=None,
    name=socket.gethostname(),
    buffered_write_count=DEFAULT_BUFFERED_WRITE_COUNT,
):
    """Run a ResourceStatAggregator in a loop. Must be called from a child process.

    Parameters
    ----------
    conn : multiprocessing.Pipe
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
    setup_logging(__name__, filename=log_file, mode="w")
    logger.info("Monitor resource utilization with config=%s", config)
    collector = ResourceStatCollector()
    stats = collector.get_stats(ComputeNodeResourceStatConfig.all_enabled(), pids={})
    agg = ResourceStatAggregator(config, stats)
    if config.monitor_type == "periodic" and db_file is None:
        raise ValueError("path must be set if monitor_type is periodic")
    store = (
        ResourceStatStore(
            config, db_file, stats, name=name, buffered_write_count=buffered_write_count
        )
        if config.monitor_type == "periodic"
        else None
    )

    results = None
    cmd_poll_interval = 1
    last_job_poll_time = 0
    while True:
        if conn.poll():
            cmd = conn.recv()
            logger.debug("Received command %s", cmd)
            if isinstance(cmd, CompleteProcessesCommand):
                result = agg.finalize_process_stats(cmd.completed_process_keys)
                conn.send(result)
                pids = cmd.pids
            elif isinstance(cmd, SelectStatsCommand):
                config = cmd.config
                agg.config = config
                if store is not None:
                    store.config = config
                pids = cmd.pids
            elif isinstance(cmd, UpdatePidsCommand):
                config = cmd.config
                agg.config = config
                pids = cmd.pids
                if store is not None:
                    store.config = config
            elif isinstance(cmd, ShutDownCommand):
                results = (agg.finalize_system_stats(), agg.finalize_process_stats(cmd.pids))
                if store is not None:
                    store.flush()
                    if config.make_plots:
                        store.plot_to_file()
                break
            else:
                raise NotImplementedError(f"Bug: need to implement support for {cmd=}")

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


_g_collect_stats = True


def run_monitor_sync(
    config: ComputeNodeResourceStatConfig,
    pids,
    duration,
    db_file=None,
    name=socket.gethostname(),
    buffered_write_count=DEFAULT_BUFFERED_WRITE_COUNT,
):
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
    logger.info("Monitor resource utilization with config=%s duration=%s", config, duration)
    collector = ResourceStatCollector()
    stats = collector.get_stats(ComputeNodeResourceStatConfig.all_enabled(), pids={})
    agg = ResourceStatAggregator(config, stats)
    if config.monitor_type == "periodic" and db_file is None:
        raise ValueError("db_file must be set if monitor_type is periodic")
    store = (
        ResourceStatStore(
            config, db_file, stats, name=name, buffered_write_count=buffered_write_count
        )
        if config.monitor_type == "periodic"
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
