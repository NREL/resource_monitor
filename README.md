[![codecov](https://codecov.io/gh/NREL/resource_monitor/graph/badge.svg?token=EVEJDPS3LI)](https://codecov.io/gh/NREL/resource_monitor)

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

## Installation

1. Create a Python virtual environment and activate it. Adjust as necessary if using Windows.
```
$ python -m venv ~/python-envs/rmon
```
```
$ source ~/python-envs/rmon/bin/activate
```

2. Install the package.
```
$ pip install rmon
```

3. Optionally, install `jq` by following instructions at https://jqlang.github.io/jq/download/.

## Usage

### CLI tool to monitor resource utilization
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

### CLI tool to start a process and monitor its resource utilization
```
$ rmon monitor-process -i1 --plots python my_script.py ARGS [OPTIONS]
```
Use the stame steps above to view results.

### CLI tool to monitor resource utilization with dynamic changes
This command will monitor CPU, memory, and disk utilization every second. It will present user
prompts that allow you to change what is being monitored. It will plot the results when you
select the exit command.
```
rmon collect -i1 --plots -n run1 --interactive PID1 PID2 ...
```

You can use this asynchronous functionality in your own application if you are controlling the
processes being monitored. Refer to `resource_monitor/cli/collect.py` for example code. Search for
`run_monitor_async`.

### Collect stats for all compute nodes in an HPC job
The
[directory](https://github.com/NREL/resource_monitor/tree/main/scripts/slurm) contains some
example scripts that can be deployed in a Slurm job to collect stats for your compute nodes.

1. Copy
[collect_stats.sh](https://github.com/NREL/resource_monitor/blob/main/scripts/slurm/collect_stats.sh)
and
[wait_for_stats.sh](https://github.com/NREL/resource_monitor/blob/main/scripts/slurm/wait_for_stats.sh)
to your HPC runtime directory.

2. Modify `collect_stats.sh` such that it loads the environment containing `rmon`.

3. Modify `collect_stats.sh` with your desired options for `rmon collect`.

4. Modify your `sbatch` script with relevant lines from
[batch_job.sh](https://github.com/NREL/resource_monitor/blob/main/scripts/slurm/batch_job.sh).

The following will occur when Slurm runs your job:

- Ensure that the file `shutdown` does not exist.
- Start `rmon collect` as a background operation.
- Run your job.
- Create the file `shutdown`. That will trigger `collect_stats.sh` to stop.
- Gracefully shut down ``rmon`` and generate plots.

### Code timings
Refer to this [page](https://github.com/NREL/resource_monitor/blob/main/src/rmon/timing/README.md)
for instructions on how to collect timing statistics of targeted functions.

## License
rmon is released under a BSD 3-Clause [license](https://github.com/NREL/resource_monitor/blob/main/LICENSE).


## Software Record
This package is developed under NREL Software Record SWR-24-128.
