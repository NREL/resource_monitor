"""CLI utility to plot already-collected resource statistics"""

import logging
import sys
from pathlib import Path

import click

from resource_monitor.plots import plot_to_file


logger = logging.getLogger(__name__)


@click.command()
@click.argument("directory", type=click.Path(exists=True), callback=lambda *x: Path(x[2]))
def plot(directory: Path):
    """Plot all stats in directory to HTML files."""
    db_files = list(directory.glob("*.sqlite"))
    if not db_files:
        logger.error("No database files exist in %s", directory)
        sys.exit(1)

    for db_file in db_files:
        plot_to_file(db_file)
