"""Entry point for CLI commands"""

import logging
import sys

import click

import resource_monitor.version
from resource_monitor.cli.collect import collect


logger = logging.getLogger(__name__)


def _show_version(*args):
    version = args[2]
    if version:
        print(f"Resource Monitor version {resource_monitor.version.__version__}")
        sys.exit(0)
    return version


@click.group()
@click.option(
    "--version",
    callback=_show_version,
    is_flag=True,
    show_default=True,
    help="Show version and exit",
)
def cli(version):  # pylint: disable=unused-argument
    """Resource monitor commands"""


cli.add_command(collect)
