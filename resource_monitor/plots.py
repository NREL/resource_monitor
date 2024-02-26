"""Makes plots."""

import logging
from pathlib import Path

import plotly.graph_objects as go  # type: ignore
import polars as pl
from plotly.subplots import make_subplots  # type: ignore

from .models import ResourceType


logger = logging.getLogger(__name__)


def plot_to_file(db_file: str | Path, name: str | None = None) -> None:
    """Plots the stats to HTML files in the same directory as the db_file."""
    if not isinstance(db_file, Path):
        db_file = Path(db_file)
    base_name = db_file.stem
    name = name or base_name
    for resource_type in ResourceType:
        rtype = resource_type.value.lower()
        query = f"select * from {rtype}"
        df = pl.read_database(query, f"sqlite://{db_file}").with_columns(
            pl.col("timestamp").str.strptime(pl.Datetime, format="%Y-%m-%d %H:%M:%S%.f")
        )
        if len(df) == 0:
            continue
        if resource_type == ResourceType.PROCESS:
            fig = make_subplots(specs=[[{"secondary_y": True}]])
            for key, _df in df.partition_by(by="id", maintain_order=True, as_dict=True).items():
                fig.add_trace(
                    go.Scatter(
                        x=_df["timestamp"],
                        y=_df["cpu_percent"],
                        name=f"{key} cpu_percent",
                    )
                )
                fig.add_trace(
                    go.Scatter(x=_df["timestamp"], y=_df["rss"], name=f"{key} rss"),
                    secondary_y=True,
                )
            fig.update_yaxes(title_text="CPU Percent", secondary_y=False)
            fig.update_yaxes(title_text="RSS (Memory)", secondary_y=True)
        else:
            df = df.select([pl.col(pl.Float64), pl.col(pl.Int64), pl.col("timestamp")])
            fig = go.Figure()
            for column in set(df.columns) - {"timestamp"}:
                fig.add_trace(go.Scatter(x=df["timestamp"], y=df[column], name=column))

        fig.update_xaxes(title_text="Time")
        fig.update_layout(title=f"{name} {resource_type.value} Utilization")
        output_dir = db_file.parent / "html"
        output_dir.mkdir(exist_ok=True)
        filename = output_dir / f"{base_name}_{rtype}.html"
        fig.write_html(str(filename))
        logger.info("Generated plot in %s", filename)
