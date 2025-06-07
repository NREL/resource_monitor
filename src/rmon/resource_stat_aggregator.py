"""Aggregates resource stats"""

import socket
import sys
from collections import defaultdict
from typing import Any, Iterable

from .models import (
    ComputeNodeResourceStatResults,
    ComputeNodeProcessResourceStatResults,
    ProcessStatResults,
    ResourceStatResults,
    ResourceType,
    ComputeNodeResourceStatConfig,
)


class ResourceStatAggregator:
    """Aggregates resource utilization stats in memory."""

    def __init__(
        self, config: ComputeNodeResourceStatConfig, stats: dict[ResourceType, dict[str, Any]]
    ) -> None:
        self._config = config
        self._count: dict[ResourceType, int] = {}
        self._last_stats = stats
        self._summaries: dict[str, dict[ResourceType, dict[str, float]]] = {
            "average": defaultdict(dict),
            "maximum": defaultdict(dict),
            "minimum": defaultdict(dict),
            "sum": defaultdict(dict),
        }
        # TODO: max rolling average would be nice
        for resource_type in ComputeNodeResourceStatConfig.list_system_resource_types():
            self._count[resource_type] = 0

        for resource_type, stat_dict in self._last_stats.items():
            if resource_type != ResourceType.PROCESS:
                for stat_name in stat_dict:
                    self._summaries["average"][resource_type][stat_name] = 0.0
                    self._summaries["maximum"][resource_type][stat_name] = 0.0
                    self._summaries["minimum"][resource_type][stat_name] = sys.maxsize
                    self._summaries["sum"][resource_type][stat_name] = 0.0

        self._process_summaries: dict[str, dict[str, dict[str, float]]] = {
            "average": defaultdict(dict),
            "maximum": defaultdict(dict),
            "minimum": defaultdict(dict),
            "sum": defaultdict(dict),
        }
        self._process_sample_count: dict[str, int] = {}

    def finalize_process_stats(
        self, completed_process_keys: Iterable[str]
    ) -> ComputeNodeProcessResourceStatResults:
        """Finalize stat summaries for completed processes."""
        # Note that short-lived processes may not be present.
        processes = set(completed_process_keys).intersection(self._process_sample_count)
        results = []
        for key in processes:
            stat_dict = self._process_summaries["sum"][key]
            for stat_name, val in stat_dict.items():
                self._process_summaries["average"][key][stat_name] = (
                    val / self._process_sample_count[key]
                )

        for key in processes:
            samples = self._process_sample_count[key]
            result = ProcessStatResults(
                process_key=key,
                num_samples=samples,
                resource_type=ResourceType.PROCESS,
                average=self._process_summaries["average"][key],
                minimum=self._process_summaries["minimum"][key],
                maximum=self._process_summaries["maximum"][key],
            )
            results.append(result)

            for stats in self._process_summaries.values():
                stats.pop(key)
            self._process_sample_count.pop(key)

        return ComputeNodeProcessResourceStatResults(
            hostname=socket.gethostname(),
            results=results,
        )

    def finalize_system_stats(self) -> ComputeNodeResourceStatResults:
        """Finalize the system-level stat summaries and return the results.

        Returns
        -------
        ComputeNodeResourceStatResults
        """
        hostname = socket.gethostname()
        results: list[ResourceStatResults] = []
        resource_types: list[ResourceType] = []

        for rtype, stat_dict in self._summaries["sum"].items():
            if self._count[rtype] > 0:
                for stat_name, val in stat_dict.items():
                    self._summaries["average"][rtype][stat_name] = val / self._count[rtype]
                resource_types.append(rtype)

        self._summaries.pop("sum")
        for resource_type in resource_types:
            results.append(
                ResourceStatResults(
                    resource_type=resource_type,
                    average=self._summaries["average"][resource_type],
                    minimum=self._summaries["minimum"][resource_type],
                    maximum=self._summaries["maximum"][resource_type],
                    num_samples=self._count[resource_type],
                ),
            )

        return ComputeNodeResourceStatResults(hostname=hostname, results=results)

    @property
    def config(self) -> ComputeNodeResourceStatConfig:
        """Return the selected stats config."""
        return self._config

    @config.setter
    def config(self, config: ComputeNodeResourceStatConfig) -> None:
        """Set the selected stats config."""
        self._config = config

    def update_stats(self, cur_stats: dict[ResourceType, Any]):
        """Update resource stats information for the current interval."""
        enabled_types = (
            x for x in ComputeNodeResourceStatConfig.list_system_resource_types() if x in cur_stats
        )
        for resource_type in enabled_types:
            _compute_stats(cur_stats[resource_type], self._summaries, resource_type)
            self._count[resource_type] += 1

        if self._config.process:
            for process_key, stat_dict in cur_stats[ResourceType.PROCESS].items():
                if process_key in self._process_summaries["maximum"]:
                    _compute_stats(stat_dict, self._process_summaries, process_key)
                    self._process_sample_count[process_key] += 1
                else:
                    for stat_name, val in stat_dict.items():
                        self._process_summaries["maximum"][process_key][stat_name] = val
                        self._process_summaries["minimum"][process_key][stat_name] = val
                        self._process_summaries["sum"][process_key][stat_name] = val
                    self._process_sample_count[process_key] = 1

        self._last_stats = cur_stats


def _compute_stats(
    cur_stats: dict[str, float],
    base_stats: dict[str, dict[Any, dict[str, float]]],
    stat_key: ResourceType | str,
) -> None:
    for stat_name, val in cur_stats.items():
        if val > base_stats["maximum"][stat_key][stat_name]:
            base_stats["maximum"][stat_key][stat_name] = val
        elif val < base_stats["minimum"][stat_key][stat_name]:
            base_stats["minimum"][stat_key][stat_name] = val
        base_stats["sum"][stat_key][stat_name] += val
