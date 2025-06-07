"""Tests the timing utilities"""

import json
import logging
import re
import time

import pytest
from loguru import logger

from rmon.timing.timer_stats import TimerStatsCollector, track_timing
from rmon.timing.timer_utils import timed_info, timed_threshold

timer_stats_collector = TimerStatsCollector(is_enabled=True)


@pytest.fixture
def setup_loguru_for_caplog():
    logger.remove()

    class PropagateHandler(logging.Handler):
        def emit(self, record):
            logging.getLogger(record.name).handle(record)

    logger.add(PropagateHandler(), format="{message}")


def test_timed_info(caplog, setup_loguru_for_caplog):
    """Tests the timed_info decorator."""
    caplog.set_level(logging.DEBUG)
    _timed_function()
    assert len(caplog.records) == 1
    regex = re.compile(r"execution-time=([\d\.]+) ms")
    match = regex.search(caplog.records[0].message)
    assert match
    duration = float(match.group(1))
    assert duration > 100
    assert duration < 150


def test_timed_threshold(caplog, setup_loguru_for_caplog):
    """Tests the timed_threshold decorator."""
    caplog.set_level(logging.INFO)
    _timed_threshold_fast()
    assert len(caplog.records) == 0
    _timed_threshold_slow()
    assert len(caplog.records) == 1
    regex = re.compile(r"_timed_threshold_slow exceeded threshold execution-time=([\d\.]+)")
    match = regex.search(caplog.records[0].message)
    assert match
    duration = float(match.group(1))
    assert duration > 0.2
    assert duration < 0.25


@timed_info
def _timed_function():
    time.sleep(0.1)


@timed_threshold(0.1)
def _timed_threshold_fast():
    pass


@timed_threshold(0.1)
def _timed_threshold_slow():
    time.sleep(0.2)


def test_timer_stats_collector(caplog, tmp_path, setup_loguru_for_caplog):
    """Tests the collector"""
    caplog.set_level(logging.INFO)
    for _ in range(3):
        _tracked_function()
    timer_stats_collector.log_stats()
    regex = re.compile(r"avg=([\d\.]+) .*count=(\d+)")
    match = regex.search(caplog.records[0].message)
    assert match
    avg = float(match.group(1))
    assert avg > 0.1
    assert avg < 0.15
    count = int(match.group(2))
    assert count == 3

    log_file = tmp_path / "stats.json"
    if log_file.exists():
        log_file.unlink()
    timer_stats_collector.log_json_stats(log_file)
    assert log_file.exists()
    data = json.loads(log_file.read_text(encoding="utf-8"))
    assert data["avg"] > 0.1 and data["avg"] < 0.150
    assert data["count"] == 3

    timer_stats_collector.clear()
    assert not timer_stats_collector._stats  # pylint: disable=protected-access


@track_timing(timer_stats_collector)
def _tracked_function():
    time.sleep(0.1)
