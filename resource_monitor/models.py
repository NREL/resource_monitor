"""Defines data models used in resource monitoring code."""

import enum

from pydantic import BaseModel, ConfigDict, Field  # pylint: disable=no-name-in-module


class ResourceType(str, enum.Enum):
    """Types of resources to monitor"""

    CPU = "cpu"
    DISK = "disk"
    MEMORY = "memory"
    NETWORK = "network"
    PROCESS = "process"


class ResourceMonitorBaseModel(BaseModel):
    """Base model for all custom types"""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        validate_default=True,
        extra="forbid",
        use_enum_values=False,
    )


class ComputeNodeResourceStatConfig(ResourceMonitorBaseModel):
    """Defines the stats to monitor."""

    cpu: bool = Field(
        description="Monitor CPU utilization",
        default=True,
    )
    disk: bool = Field(
        description="Monitor disk/storage utilization",
        default=False,
    )
    memory: bool = Field(
        description="Monitor memory utilization",
        default=True,
    )
    network: bool = Field(
        description="Monitor network utilization",
        default=False,
    )
    process: bool = Field(
        description="Monitor per-job process utilization",
        default=True,
    )
    include_child_processes: bool = Field(
        description="Include stats from direct child processes in utilization for each job.",
        default=True,
    )
    recurse_child_processes: bool = Field(
        description="Recurse child processes to find all descendants.",
        default=False,
    )
    monitor_type: str = Field(
        description="'aggregation' or 'periodic'. Keep aggregated stats in memory or record "
        "time-series data on an interval.",
        default="aggregation",
    )
    make_plots: bool = Field(
        description="Make time-series plots if monitor_type is periodic.", default=True
    )
    interval: float = Field(
        description="Interval in seconds on which to collect stats", default=10
    )

    @classmethod
    def all_enabled(cls) -> "ComputeNodeResourceStatConfig":
        """Return an instance with all stats enabled."""
        return cls(
            cpu=True,
            disk=True,
            memory=True,
            network=True,
            process=True,
        )

    @classmethod
    def disabled(cls) -> "ComputeNodeResourceStatConfig":
        """Return an instance with all stats disabled."""
        return cls(
            cpu=False,
            disk=False,
            memory=False,
            network=False,
            process=False,
        )

    def is_enabled(self) -> bool:
        """Return True if any stat is enabled."""
        return self.cpu or self.disk or self.memory or self.network or self.process

    def disable_system_stats(self) -> None:
        """Disable all system-level stats."""
        for resource_type in self.list_system_resource_types():
            setattr(self, resource_type.value, False)

    def list_enabled_system_resource_types(self) -> list[ResourceType]:
        """Return a list of enabled system-level stats."""
        return [x for x in self.list_system_resource_types() if getattr(self, x.value)]

    @staticmethod
    def list_system_resource_types() -> list[ResourceType]:
        """Return the resource types for the overall system."""
        return [
            ResourceType.CPU,
            ResourceType.DISK,
            ResourceType.MEMORY,
            ResourceType.NETWORK,
        ]


class ResourceStatResults(ResourceMonitorBaseModel):
    """Results for one resource type"""

    resource_type: ResourceType
    average: dict
    minimum: dict
    maximum: dict
    num_samples: int


class ProcessStatResults(ResourceStatResults):
    """Results for one process stat"""

    process_key: str


class ComputeNodeResourceStatResults(ResourceMonitorBaseModel):
    """Contains all results from one compute node"""

    hostname: str = Field(description="Hostname of compute node")
    results: list[ResourceStatResults]


class ComputeNodeProcessResourceStatResults(ResourceMonitorBaseModel):
    """Contains all process results from one compute node"""

    hostname: str = Field(description="Hostname of compute node")
    results: list[ProcessStatResults]


# The commands below are used for communication between the parent and child processes engaged
# in resource monitoring through the run_monitor_async function.


class CommandBaseModel(ResourceMonitorBaseModel):
    """Base class for all commands"""

    pids: dict[str, int]


class CompleteProcessesCommand(CommandBaseModel):
    """Command to stop monitoring of processes that are completed. The parent process must call
    recv() immediately afterwards to read process stats results.
    """

    completed_process_keys: list[str]


class SelectStatsCommand(CommandBaseModel):
    """Command to change the stats to monitor"""

    config: ComputeNodeResourceStatConfig


class ShutDownCommand(CommandBaseModel):
    """Command to shut down the monitoring process. The parent must call recv() immediately
    afterwards to read system and process results.
    """


class UpdatePidsCommand(CommandBaseModel):
    """Command to update the processes to monitor."""

    config: ComputeNodeResourceStatConfig
