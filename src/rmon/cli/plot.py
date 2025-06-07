"""CLI utility to plot already-collected resource statistics"""

import sys
from pathlib import Path

import rich_click as click
from loguru import logger

from rmon.plots import plot_to_file


@click.command()
@click.argument("directory", type=click.Path(exists=True), callback=lambda *x: Path(x[2]))
def plot(directory: Path) -> None:
    """Plot all stats in directory to HTML files."""
    db_files = list(directory.glob("*.sqlite"))
    if not db_files:
        logger.error("No database files exist in {}", directory)
        sys.exit(1)

    for db_file in db_files:
        plot_to_file(db_file)
