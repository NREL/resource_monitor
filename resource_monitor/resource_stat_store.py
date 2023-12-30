"""Stores time-series resource utilization stats."""

import logging
import socket
from datetime import datetime
from pathlib import Path

from .common import DEFAULT_BUFFERED_WRITE_COUNT
from .models import ResourceType, ComputeNodeResourceStatConfig
from .plots import plot_to_file
from .utils.sql import insert_rows, make_table


logger = logging.getLogger(__name__)


class ResourceStatStore:
    """Stores resource utilization stats in a SQLite database on a periodic basis."""

    def __init__(
        self,
        config: ComputeNodeResourceStatConfig,
        db_file: Path,
        stats,
        buffered_write_count=DEFAULT_BUFFERED_WRITE_COUNT,
        name=socket.gethostname(),
    ):
        self._config = config
        self._buffered_write_count = buffered_write_count
        self._bufs = {}
        self._db_file = db_file
        self._name = name
        self._initialize_tables(stats)

    def __del__(self):
        for resource_type in ResourceType:
            if self._bufs.get(resource_type, []):
                logger.warning("Destructing with stats still in cache: %s", resource_type.value)

    @property
    def config(self):
        """Return the selected config."""
        return self._config

    @config.setter
    def config(self, config: ComputeNodeResourceStatConfig):
        """Set the selected config."""
        self._config = config

    def flush(self):
        """Flush all cached data to the database."""
        for resource_type in ResourceType:
            self._flush_resource_type(resource_type)

    def plot_to_file(self):
        """Plots the stats to HTML files."""
        plot_to_file(self._db_file, name=self._name)

    def record_stats(self, stats):
        """Records resource stats information for the current interval."""
        timestamp = str(datetime.now())
        for rtype in ComputeNodeResourceStatConfig.list_system_resource_types():
            if getattr(self._config, rtype.value):
                row = {"timestamp": timestamp}
                row.update(stats[rtype])
                self._add_stats(rtype, tuple(row.values()))
        if self._config.process:
            for name, _stats in stats[ResourceType.PROCESS].items():
                row = {"timestamp": timestamp, "id": name}
                row.update(_stats)
                self._add_stats(ResourceType.PROCESS, tuple(row.values()))

    def _add_stats(self, resource_type, values):
        self._bufs[resource_type].append(values)
        if len(self._bufs[resource_type]) >= self._buffered_write_count:
            self._flush_resource_type(resource_type)

    @staticmethod
    def _fix_column_names(row: dict):
        converted = {"timestamp": ""}
        illegal_chars = (" ", "/")
        for name, val in row.items():
            for char in illegal_chars:
                name = name.replace(char, "_")
            converted[name] = val

        return converted

    def _flush_resource_type(self, resource_type):
        rows = self._bufs[resource_type]
        if rows:
            insert_rows(self._db_file, resource_type.value.lower(), rows)
            self._bufs[resource_type].clear()
            logger.debug("Flushed resource_type=%s", resource_type.value)

    def _initialize_tables(self, stats):
        make_table(
            self._db_file,
            ResourceType.CPU.value.lower(),
            self._fix_column_names(stats[ResourceType.CPU]),
        )
        self._bufs[ResourceType.CPU] = []
        make_table(
            self._db_file,
            ResourceType.DISK.value.lower(),
            self._fix_column_names(stats[ResourceType.DISK]),
        )
        self._bufs[ResourceType.DISK] = []
        make_table(
            self._db_file,
            ResourceType.MEMORY.value.lower(),
            self._fix_column_names(stats[ResourceType.MEMORY]),
        )
        self._bufs[ResourceType.MEMORY] = []
        make_table(
            self._db_file,
            ResourceType.NETWORK.value.lower(),
            self._fix_column_names(stats[ResourceType.NETWORK]),
        )
        self._bufs[ResourceType.NETWORK] = []
        make_table(
            self._db_file,
            ResourceType.PROCESS.value.lower(),
            {"timestamp": "", "id": "", "cpu_percent": 0.0, "rss": 0.0},
        )
        self._bufs[ResourceType.PROCESS] = []
