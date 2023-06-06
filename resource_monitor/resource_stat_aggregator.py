"""Aggregates resource stats"""

import logging
import socket
import sys
from collections import defaultdict

from .models import (
    ComputeNodeResourceStatResults,
    ComputeNodeProcessResourceStatResults,
    ProcessStatResults,
    ResourceStatResults,
    ResourceType,
    ComputeNodeResourceStatConfig,
)


logger = logging.getLogger(__name__)


class ResourceStatAggregator:
    """Aggregates resource utilization stats in memory."""

    def __init__(self, config: ComputeNodeResourceStatConfig, stats):
        self._config = config
        self._count = {}
        self._last_stats = stats
        self._summaries = {
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

        self._process_summaries = {
            "average": defaultdict(dict),
            "maximum": defaultdict(dict),
            "minimum": defaultdict(dict),
            "sum": defaultdict(dict),
        }
        self._process_sample_count = {}

    def finalize_process_stats(
        self, completed_process_keys
    ) -> ComputeNodeProcessResourceStatResults:
        """Finalize stat summaries for completed processes.

        Parameters
        ----------
        completed_process_keys : list[str]

        Returns
        -------
        ComputeNodeProcessResourceStatResults
        """
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

            for stat_dict in self._process_summaries.values():
                stat_dict.pop(key)
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
        results = []
        resource_types = []

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

        return ComputeNodeResourceStatResults(
            hostname=hostname,
            results=results,
        )

    @property
    def config(self):
        """Return the selected stats config."""
        return self._config

    @config.setter
    def config(self, config: ComputeNodeResourceStatConfig):
        """Set the selected stats config."""
        self._config = config

    def update_stats(self, cur_stats):
        """Update resource stats information for the current interval."""
        enabled_types = (
            x for x in ComputeNodeResourceStatConfig.list_system_resource_types() if x in cur_stats
        )
        for resource_type in enabled_types:
            stat_dict = cur_stats[resource_type]
            for stat_name, val in stat_dict.items():
                if val > self._summaries["maximum"][resource_type][stat_name]:
                    self._summaries["maximum"][resource_type][stat_name] = val
                elif val < self._summaries["minimum"][resource_type][stat_name]:
                    self._summaries["minimum"][resource_type][stat_name] = val
                self._summaries["sum"][resource_type][stat_name] += val
            self._count[resource_type] += 1

        for process_key, stat_dict in cur_stats[ResourceType.PROCESS].items():
            if process_key in self._process_summaries["maximum"]:
                for stat_name, val in stat_dict.items():
                    if val > self._process_summaries["maximum"][process_key][stat_name]:
                        self._process_summaries["maximum"][process_key][stat_name] = val
                    elif val < self._process_summaries["minimum"][process_key][stat_name]:
                        self._process_summaries["minimum"][process_key][stat_name] = val
                    self._process_summaries["sum"][process_key][stat_name] += val
                self._process_sample_count[process_key] += 1
            else:
                for stat_name, val in stat_dict.items():
                    self._process_summaries["maximum"][process_key][stat_name] = val
                    self._process_summaries["minimum"][process_key][stat_name] = val
                    self._process_summaries["sum"][process_key][stat_name] = val
                self._process_sample_count[process_key] = 1

        self._last_stats = cur_stats
