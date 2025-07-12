"""CLI utility to monitor resource statistics"""

import multiprocessing
import multiprocessing.connection
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Iterable

import rich_click as click
import psutil
from daemon import DaemonContext
from loguru import logger

from rmon.common import DEFAULT_BUFFERED_WRITE_COUNT
from rmon.resource_monitor import run_monitor_async, run_monitor_sync
from rmon.models import (
    ComputeNodeResourceStatConfig,
    CompleteProcessesCommand,
    ComputeNodeResourceStatResults,
    ComputeNodeProcessResourceStatResults,
    SelectStatsCommand,
    ShutDownCommand,
    UpdatePidsCommand,
    ResourceType,
)


@click.command()
@click.argument("process_ids", nargs=-1, type=int, callback=lambda *x: [int(y) for y in x[2]])
@click.option(
    "--plots/--no-plots",
    default=False,
    is_flag=True,
    show_default=True,
    help="Generate plots when collection is complete.",
)
@click.option(
    "--cpu/--no-cpu",
    default=True,
    is_flag=True,
    show_default=True,
    help="Enable CPU monitoring",
)
@click.option(
    "--disk/--no-disk",
    default=False,
    is_flag=True,
    show_default=True,
    help="Enable disk monitoring",
)
@click.option(
    "--memory/--no-memory",
    default=True,
    is_flag=True,
    show_default=True,
    help="Enable memory monitoring",
)
@click.option(
    "--network/--no-network",
    default=False,
    is_flag=True,
    show_default=True,
    help="Enable network monitoring",
)
@click.option(
    "--children/--no-children",
    default=False,
    is_flag=True,
    show_default=True,
    help="Aggregate child process utilization.",
)
@click.option(
    "--recurse-children/--no-recurse-children",
    default=False,
    is_flag=True,
    show_default=True,
    help="Search for all child processes recursively.",
)
@click.option(
    "-n",
    "--name",
    default=socket.gethostname(),
    type=str,
    show_default=True,
    help="Base name for output files.",
)
@click.option(
    "-d",
    "--duration",
    default=None,
    type=int,
    help="Total time to collect resource stats. Applies only if interactive is false. Default is "
    "infinite.",
)
@click.option(
    "-I",
    "--interactive",
    default=False,
    is_flag=True,
    show_default=True,
    help="Enter interactive mode and be able to change the monitors.",
)
@click.option(
    "-i",
    "--interval",
    default=3,
    type=int,
    show_default=True,
    help="Interval in seconds on which to collect resource stats.",
)
@click.option(
    "-o",
    "--output",
    default="stats-output",
    show_default=True,
    help="Output directory.",
    callback=lambda *x: Path(x[2]),
)
@click.option(
    "--overwrite",
    is_flag=True,
    default=False,
    show_default=True,
    help="Overwrite sqlite file.",
)
@click.option(
    "--buffered-write-count",
    default=DEFAULT_BUFFERED_WRITE_COUNT,
    show_default=True,
    type=int,
    help="Number of intervals to cache in memory before persisting to database.",
)
@click.option(
    "--daemon/--no-daemon",
    is_flag=True,
    default=False,
    show_default=True,
    help="Run the process as a daemon.",
)
def collect(
    process_ids: tuple[int],
    cpu: bool,
    disk: bool,
    memory: bool,
    network: bool,
    children: bool,
    recurse_children: bool,
    name: str,
    plots: bool,
    duration: int,
    interactive: bool,
    interval: int,
    output: Path,
    overwrite: bool,
    buffered_write_count: int,
    daemon: bool,
) -> None:
    """Collect resource utilization stats. Stop collection by setting duration, pressing Ctrl-c,
    or sending SIGTERM to the process ID.

    Examples:

    \b
    # Use default resource types, name, and output directory; run until user presses Ctrl-c.
    $ rmon collect --interval=1 --plots

    \b
    # Use custom resource types, name, and output directory; run for 10 minutes.
    $ rmon collect --disk --cpu --memory --network --interval=1 --plots --name=stats1 --output=./stats --duration=600
    """
    if daemon:
        if sys.platform == "win32":
            logger.error("--daemon is not supported on Windows.")
            sys.exit(1)
        if interactive:
            logger.error("--daemon is not supported in interactive mode.")
            sys.exit(1)

    output.mkdir(exist_ok=True)
    db_file = output / f"{name}.sqlite"
    _check_db_file(db_file, overwrite)

    if interactive and duration is not None:
        logger.warning("Ignoring duration in interactive mode")

    config = ComputeNodeResourceStatConfig(
        cpu=cpu,
        disk=disk,
        memory=memory,
        network=network,
        process=bool(process_ids),
        include_child_processes=children,
        recurse_child_processes=recurse_children,
        interval=interval,
        make_plots=plots,
        monitor_type="periodic",
    )

    pids = _get_process_names(process_ids)
    if db_file.exists():
        db_file.unlink()
    collector_log_file = output / f"{name}_collector.log"
    results_file = output / f"{name}_results.json"
    if interactive:
        system_results, process_results = _run_interactive_mode(
            config, pids, db_file, collector_log_file, results_file, name, buffered_write_count
        )
        _cleanup(
            results_file, db_file, system_results, process_results, config, plots, output, name
        )
    elif daemon:
        with DaemonContext():
            system_results, process_results = run_monitor_sync(
                config,
                pids,
                duration,
                db_file=db_file,
                name=name,
                buffered_write_count=buffered_write_count,
            )
            _cleanup(
                results_file,
                db_file,
                system_results,
                process_results,
                config,
                plots,
                output,
                name,
            )
    else:
        system_results, process_results = run_monitor_sync(
            config,
            pids,
            duration,
            db_file=db_file,
            name=name,
            buffered_write_count=buffered_write_count,
        )
        _cleanup(
            results_file, db_file, system_results, process_results, config, plots, output, name
        )


@click.command(context_settings={"ignore_unknown_options": True, "allow_extra_args": True})
@click.option(
    "--cpu/--no-cpu",
    default=False,
    is_flag=True,
    show_default=True,
    help="Enable CPU monitoring for the system",
)
@click.option(
    "--disk/--no-disk",
    default=False,
    is_flag=True,
    show_default=True,
    help="Enable disk monitoring for the system",
)
@click.option(
    "--memory/--no-memory",
    default=False,
    is_flag=True,
    show_default=True,
    help="Enable memory monitoring for the system",
)
@click.option(
    "--network/--no-network",
    default=False,
    is_flag=True,
    show_default=True,
    help="Enable network monitoring for the system",
)
@click.option(
    "--children/--no-children",
    default=False,
    is_flag=True,
    show_default=True,
    help="Aggregate child process utilization.",
)
@click.option(
    "--recurse-children/--no-recurse-children",
    default=False,
    is_flag=True,
    show_default=True,
    help="Search for all child processes recursively.",
)
@click.option(
    "-n",
    "--name",
    default=socket.gethostname(),
    type=str,
    show_default=True,
    help="Base name for output files.",
)
@click.option(
    "-i",
    "--interval",
    default=3,
    type=int,
    show_default=True,
    help="Interval in seconds on which to collect resource stats.",
)
@click.option(
    "-o",
    "--output",
    default="stats-output",
    show_default=True,
    help="Output directory.",
    callback=lambda *x: Path(x[2]),
)
@click.option(
    "--overwrite",
    is_flag=True,
    default=False,
    show_default=True,
    help="Overwrite sqlite file.",
)
@click.option(
    "--plots/--no-plots",
    default=False,
    is_flag=True,
    show_default=True,
    help="Generate plots when collection is complete.",
)
@click.option(
    "--buffered-write-count",
    default=DEFAULT_BUFFERED_WRITE_COUNT,
    show_default=True,
    type=int,
    help="Number of intervals to cache in memory before persisting to database.",
)
@click.argument("process_args", nargs=-1, type=click.UNPROCESSED)
def monitor_process(
    cpu: bool,
    disk: bool,
    memory: bool,
    network: bool,
    children: bool,
    recurse_children: bool,
    name: str,
    interval: int,
    output: Path,
    overwrite: bool,
    plots: bool,
    process_args: list[str],
    buffered_write_count: int,
) -> None:
    """Start a process and monitor its resource utilization stats.

    \b
    Example:
    rmon monitor-process --plots python my_script.py ARGS [OPTIONS]
    """
    output.mkdir(exist_ok=True)
    db_file = output / f"{name}.sqlite"
    _check_db_file(db_file, overwrite)
    collector_log_file = output / f"{name}_collector.log"
    results_file = output / f"{name}_results.json"

    logger.info("Running {}", process_args)
    with subprocess.Popen(process_args) as pipe:
        config = ComputeNodeResourceStatConfig(
            cpu=cpu,
            disk=disk,
            memory=memory,
            network=network,
            process=True,
            include_child_processes=children,
            recurse_child_processes=recurse_children,
            interval=interval,
            make_plots=plots,
            monitor_type="periodic",
        )

        pids = _get_process_names([pipe.pid])
        parent_monitor_conn, child_conn = multiprocessing.Pipe()
        args = (child_conn, config, pids, collector_log_file, db_file, name, buffered_write_count)
        monitor_proc = multiprocessing.Process(target=run_monitor_async, args=args)
        monitor_proc.start()
        pipe.communicate()
        if pipe.returncode != 0:
            logger.error("The monitored process failed: {}", pipe.returncode)

    parent_monitor_conn.send(ShutDownCommand(pids=pids))
    system_results, process_results = parent_monitor_conn.recv()
    monitor_proc.join()
    _cleanup(results_file, db_file, system_results, process_results, config, plots, output, name)


def _check_db_file(db_file: Path, overwrite: bool) -> None:
    if db_file.exists():
        if overwrite:
            db_file.unlink()
        else:
            print(
                f"{db_file} already exists. Choose a different name or set --overwrite.",
                file=sys.stderr,
            )
            sys.exit(1)


def _cleanup(
    results_file: Path,
    db_file: Path,
    system_results: ComputeNodeResourceStatResults,
    process_results: ComputeNodeProcessResourceStatResults,
    config: ComputeNodeResourceStatConfig,
    plots: bool,
    output: Path,
    name: str,
) -> None:
    with open(results_file, "a", encoding="utf-8") as f:
        f.write(system_results.model_dump_json())
        f.write("\n")
        f.write(process_results.model_dump_json())
        f.write("\n")
    logger.info("Recorded summary stats to {} (line-delimited JSON format)", results_file)
    logger.info("Use 'jq' to view consolidated data: 'jq -s . {}'", results_file)

    examples = []
    for rtype in ("cpu", "disk", "memory", "network", "process"):
        if getattr(config, rtype):
            examples.append(f'    sqlite3 -table {db_file} "select * from {rtype}"')
    logger.info(
        "View full results in table form with these example commands: \n{}", "\n".join(examples)
    )

    if plots:
        plot_files = (f"    {x}" for x in output.glob(f"{name}*.html"))
        logger.info("View interactive plots:\n{}", "\n".join(plot_files))


def _run_interactive_mode(
    config: ComputeNodeResourceStatConfig,
    pids: dict,
    db_file: Path,
    collector_log_file: Path,
    results_file: Path,
    name: str,
    buffered_write_count: int,
) -> tuple[ComputeNodeResourceStatResults, ComputeNodeProcessResourceStatResults]:
    parent_monitor_conn, child_conn = multiprocessing.Pipe()
    args = (child_conn, config, pids, collector_log_file, db_file, name, buffered_write_count)
    monitor_proc = multiprocessing.Process(target=run_monitor_async, args=args)
    monitor_proc.start()
    time.sleep(2)
    msg = """
Enter one of the following letters to change operation:

    p: Change the process IDs to monitor.
    r: Change the system-level resource types to monitor.
    s: Shut down.

>>> """
    while True:
        command = input(msg).strip()
        match command.lower():
            case "":
                pass
            case "p":
                config, pids = _get_user_process_id_input(
                    config, pids, parent_monitor_conn, results_file
                )
            case "r":
                config = _get_user_resource_types(config, pids, parent_monitor_conn)
            case "s":
                break
            case _:
                logger.error("command={} is not a valid command", command)
        time.sleep(1)

    logger.info("Stop resource monitor")
    parent_monitor_conn.send(ShutDownCommand(pids=pids))
    system_results, process_results = parent_monitor_conn.recv()
    monitor_proc.join()
    return system_results, process_results


def _get_user_resource_types(
    config: ComputeNodeResourceStatConfig,
    pids,
    parent_monitor_conn: multiprocessing.connection.Connection,
) -> ComputeNodeResourceStatConfig:
    resource_types = config.list_enabled_system_resource_types()
    types_str = " ".join((x.value for x in resource_types))
    example = "cpu disk memory network"
    print(
        f"Current resource types being monitored: {types_str}. Available: {example}",
        file=sys.stderr,
    )
    msg = "\nEnter the system-level resource types to monitor (empty to disable) >>> "
    while True:
        user_types = input(msg).strip()
        try:
            types = {ResourceType(x) for x in user_types.split()}
            break
        except ValueError:
            logger.error("Failed to parse resource types: {}. Example: {}", user_types, example)

    if not types:
        logger.info("Disable system-level resource monitoring.")

    for rtype in ComputeNodeResourceStatConfig.list_system_resource_types():
        setattr(config, rtype.value, rtype in types)

    parent_monitor_conn.send(SelectStatsCommand(config=config, pids=pids))
    if types:
        logger.info("Collecting stats for {}", user_types)
    return config


def _get_user_process_id_input(
    config: ComputeNodeResourceStatConfig,
    cur_pids: dict[str, int],
    parent_monitor_conn: multiprocessing.connection.Connection,
    results_file: Path,
):
    pids_str = "none" if not cur_pids else " ".join((str(x) for x in cur_pids.values()))
    print(f"Current process IDs: {pids_str}", file=sys.stderr)
    msg = "Enter the new PIDs to monitor, integers separated by spaces (empty to disable) >>> "
    while True:
        user_pids = input(msg).strip()
        if user_pids:
            try:
                new_pids = _get_process_names([int(x) for x in user_pids.split()])
                config.process = True
            except ValueError:
                logger.error("Failed to parse the process IDs as integers: {}", user_pids)
                continue
        else:
            new_pids = {}
        break

    _complete_pids(cur_pids, new_pids, parent_monitor_conn, results_file)
    parent_monitor_conn.send(UpdatePidsCommand(config=config, pids=new_pids))
    if new_pids:
        names = "\n".join((f"  {x}" for x in new_pids))
        logger.info("Collecting stats for processes:\n{}", names)
    return config, new_pids


def _complete_pids(
    old_pids: dict[str, int],
    new_pids: dict[str, int],
    parent_monitor_conn: multiprocessing.connection.Connection,
    results_file: Path,
) -> None:
    completed_pids = set(old_pids) - set(new_pids)
    if completed_pids:
        parent_monitor_conn.send(
            CompleteProcessesCommand(
                completed_process_keys=list(completed_pids),
                pids=new_pids,
            )
        )
        results = parent_monitor_conn.recv()
        with open(results_file, "a", encoding="utf-8") as f:
            f.write(results.model_dump_json())
            f.write("\n")


def _get_process_names(pids: Iterable[int]) -> dict[str, int]:
    names: dict[str, int] = {}
    for pid in pids:
        process_name = _get_process_name(pid)
        if process_name in names:
            msg = f"{process_name=} is already stored"
            raise ValueError(msg)
        names[process_name] = pid

    return names


def _get_process_name(pid: int) -> str:
    """Return a mapping of name to pid. The name should be suitable for plots."""
    # Including the entire command line is often way too long.
    # name() is often better than the first arg (python instead of full path to python)
    # This tries to get the best of all worlds and ensure uniqueness.
    process = psutil.Process(pid)
    cmdline = process.cmdline()
    if len(cmdline) > 1:
        name = process.name() + " " + " ".join(cmdline[1:])
    else:
        name = process.name()

    if len(name) > 20:
        name = name[:20] + "..."

    return name + f" ({process.pid})"
