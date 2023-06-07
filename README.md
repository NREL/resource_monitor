# Resource Monitor
This package contains utilities to monitor system resource utilization (CPU, memory, disk,
network).

Here are the ways you can use it:

- Monitor resource utilization for a compute node for a given set of resource types and process
IDs.
- Start a process and monitor its resource utilization.
- Monitor resource utilization for a compute node asynchronously with the ability to dynamically
change the resource types and process IDs being monitored.
- Produce JSON reports of aggregated metrics.
- Produce interactive HTML plots of the statistics.

## Usage

### Installation
Optionally, install `jq` by following instructions at https://jqlang.github.io/jq/download/.

1. Create a Python virtual environment (e.g., `conda`) with Python 3.10 or later. Refer to
https://conda.io/projects/conda/en/stable/user-guide/install/ if you are not familiar with virtual
environments.

2. Install the package.
```
$ pip install git+https://github.nrel.gov/dthom/resource_monitor
```

## CLI tool to monitor resource utilization
This command will monitor CPU, memory, and disk utilization every second and then plot the results
whenever the user terminates the application.
```
$ rmon collect --cpu --memory --disk -i1 --plots -n run1
```
View the results in a table:
```
$ sqlite3 -table stats-output/run1.sqlite "select * from cpu"
$ sqlite3 -table stats-output/run1.sqlite "select * from memory"
$ sqlite3 -table stats-output/run1.sqlite "select * from disk"
```

This command will monitor CPU and memory utilization for specific process IDs and then plot the
results whenever the user terminates the application.
```
rmon collect -i1 --plots -n run1 PID1 PID2 ...
```
View the results in a table:
```
$ sqlite3 -table stats-output/run1.sqlite "select * from process"
```

View min/max/avg metrics:
```
$ jq -s . stats-output/run1_results.json
```

Refer to `rmon collect --help` to see all options.

## CLI tool to start a process and monitor its resource utilization
```
$ rmon monitor-process -i1 --plots python my_script.py ARGS [OPTIONS]
```
Use the stame steps above to view results.

## CLI tool to monitor resource utilization with dynamic changes
This command will monitor CPU, memory, and disk utilization every second. It will present user
prompts that allow you to change what is being monitored. It will plot the results when you
select the exit command.
```
rmon collect -i1 --plots -n run1 --interactive PID1 PID2 ...
```

You can use this asynchronous functionality in your own application if you are controlling the
processes being monitored. Refer to `resource_monitor/cli/collect.py` for example code. Search for
`run_monitor_async`.
