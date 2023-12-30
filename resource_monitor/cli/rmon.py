"""Entry point for CLI commands"""

import logging
import sys

import click

import resource_monitor
from resource_monitor.cli.collect import collect, monitor_process
from resource_monitor.cli.plot import plot
from resource_monitor.loggers import setup_logging


logger = logging.getLogger(__name__)


def _show_version(*args):
    version = args[2]
    if version:
        print(f"Resource Monitor version {resource_monitor.__version__}")
        sys.exit(0)
    return version


@click.group()
@click.option(
    "--verbose",
    is_flag=True,
    default=False,
    show_default=True,
    help="Enable verbose log messages.",
)
@click.option(
    "--version",
    callback=_show_version,
    is_flag=True,
    show_default=True,
    help="Show version and exit",
)
def cli(verbose, version):  # pylint: disable=unused-argument
    """Resource monitor commands"""
    log_file = "rmon.log"
    level = logging.DEBUG if verbose else logging.INFO
    setup_logging(__name__, console_level=level, file_level=level, filename=log_file, mode="w")


cli.add_command(collect)
cli.add_command(monitor_process)
cli.add_command(plot)
