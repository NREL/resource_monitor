"""Entry point for CLI commands"""

import sys
from pathlib import Path

import rich_click as click

import rmon
from rmon.cli.collect import collect, monitor_process
from rmon.cli.plot import plot
from rmon.loggers import setup_logging


def _show_version(*args) -> str:
    version = args[2]
    if version:
        print(f"Resource Monitor version {rmon.__version__}")
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
def cli(verbose: bool, version: str) -> None:  # pylint: disable=unused-argument
    """Resource monitor commands"""
    log_file = Path("rmon.log").absolute()
    level = "DEBUG" if verbose else "INFO"
    setup_logging(console_level=level, file_level=level, filename=log_file, mode="w")


cli.add_command(collect)
cli.add_command(monitor_process)
cli.add_command(plot)
