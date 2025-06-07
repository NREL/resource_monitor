"""Makes plots."""

from pathlib import Path

import plotly.graph_objects as go  # type: ignore
from loguru import logger
from plotly.subplots import make_subplots  # type: ignore

from rmon.models import ResourceType
from rmon.utils.sql import read_table_as_dict, read_process_tables


def plot_to_file(db_file: str | Path, name: str | None = None) -> None:
    """Plots the stats to HTML files in the same directory as the db_file."""
    if not isinstance(db_file, Path):
        db_file = Path(db_file)
    base_name = db_file.stem
    name = name or base_name
    for resource_type in ResourceType:
        table_name = resource_type.value.lower()
        if resource_type == ResourceType.PROCESS:
            fig = _make_process_figure(db_file, table_name)
        else:
            fig = _make_system_stat_figure(db_file, table_name)

        if fig is not None:
            fig.update_xaxes(title_text="Time")
            fig.update_layout(title=f"{name} {resource_type.value} Utilization")
            output_dir = db_file.parent / "html"
            output_dir.mkdir(exist_ok=True)
            filename = output_dir / f"{base_name}_{table_name}.html"
            fig.write_html(str(filename))
            logger.info("Generated plot in {}", filename)


def _make_process_figure(db_file: Path, table_name: str) -> go.Figure:
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    for key, table in read_process_tables(db_file, table_name).items():
        fig.add_trace(
            go.Scatter(
                x=table["timestamp"],
                y=table["cpu_percent"],
                name=f"{key} cpu_percent",
            )
        )
        fig.add_trace(
            go.Scatter(x=table["timestamp"], y=table["rss"], name=f"{key} rss"),
            secondary_y=True,
        )
    fig.update_yaxes(title_text="CPU Percent", secondary_y=False)
    fig.update_yaxes(title_text="RSS (Memory)", secondary_y=True)
    return fig


def _make_system_stat_figure(db_file: Path, table_name: str) -> go.Figure | None:
    table = read_table_as_dict(db_file, table_name, timestamp_column="timestamp")
    if not next(iter(table.values())):
        return None

    fig = go.Figure()
    for column in set(table) - {"timestamp"}:
        fig.add_trace(go.Scatter(x=table["timestamp"], y=table[column], name=column))
    return fig
