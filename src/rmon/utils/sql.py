"""Utility functions for interacting with a SQLite database"""

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from loguru import logger


_TYPE_MAP = {int: "INTEGER", float: "REAL", str: "TEXT", bool: "INTEGER"}


def make_table(
    db_file: Path, table: str, row: dict[str, Any], primary_key=None, types=None
) -> None:
    """Create a table in the database based on the types in row.

    Parameters
    ----------
    db_file : Path
        Database file. Create if it doesn't already exist.
    table : str
    row : dict
        Each key will be a column in the table. Define schema by the types of the values.
    primary_key : str | None
        Column name to define as the primary key
    types: dict | None
        If a dict is passed, use it as a mapping of column to type.
        This is required if values can be null.
    """
    schema = []
    for name, val in row.items():
        if types is None:
            column_type = _TYPE_MAP[type(val)]
        else:
            column_type = _TYPE_MAP[types[name]]
        entry = f"{name} {column_type}"
        if name == primary_key:
            entry += " PRIMARY KEY"
        schema.append(entry)

    with sqlite3.connect(db_file) as con:
        cur = con.cursor()
        schema_text = ", ".join(schema)
        cur.execute(f"CREATE TABLE {table}({schema_text})")
        con.commit()
    con.close()
    logger.debug("Created table={} in db_file={}", table, db_file)


def insert_rows(db_file: Path, table: str, rows: list[tuple]) -> None:
    """Insert a list of rows into the database table.

    Parameters
    ----------
    db_file : Path
    table : str
    rows : list[tuple]
        Each row should be a tuple of values.
    """
    if not rows:
        logger.warning("No rows were passed")
        return

    with sqlite3.connect(db_file) as con:
        cur = con.cursor()
        placeholder = ",".join(["?"] * len(rows[0]))
        query = f"INSERT INTO {table} VALUES({placeholder})"
        cur.executemany(query, rows)
        con.commit()
    con.close()
    logger.debug("Inserted rows into table={} in db_file={}", table, db_file)


def read_table(db_file: Path, table: str) -> tuple[list[tuple], list[str]]:
    """Read all rows from the table.

    Parameters
    ----------
    db_file : Path
    table : str

    Returns
    -------
    tuple
        list of rows, list of columns
    """
    with sqlite3.connect(db_file) as con:
        cur = con.cursor()
        query = f"SELECT * FROM {table}"
        rows = cur.execute(query).fetchall()
        columns = [x[0] for x in cur.description]
        return rows, columns


def read_table_as_dict(
    db_file: Path,
    table: str,
    columns: Optional[list[str]] = None,
    timestamp_column: Optional[str] = None,
    filters: Optional[dict[str, str]] = None,
) -> dict[str, list[Any]]:
    """Read all rows from the table and return them as a dict keyed by the columns.

    Parameters
    ----------
    db_file
    table
    columns
        Only read these columns. If None, return all columns.
    timestamp_column
        If not None, treat this column as timestamp strings in ISO format.
    filters
        If not None, insert these key/value pairs in the WHERE clause.

    Returns
    -------
    dict
    """
    with sqlite3.connect(db_file) as con:
        cur = con.cursor()
        data = {}
        where_clause = (
            ""
            if filters is None
            else "WHERE " + " ".join([f"{k}='{v}'" for k, v in filters.items()])
        )
        cols = columns or list_column_names(db_file, table)
        if timestamp_column is not None and timestamp_column not in cols:
            msg = f"{timestamp_column=} is not in {cols=}"
            raise ValueError(msg)

        for column in cols:
            query = f"SELECT {column} FROM {table} {where_clause}"
            values = cur.execute(query).fetchall()
            if timestamp_column is not None and column == timestamp_column:
                values_ = [datetime.fromisoformat(x[0]) for x in values]
            else:
                values_ = [x[0] for x in values]
            data[column] = values_
        return data


def read_process_tables(db_file: Path, table: str) -> dict[str, dict[str, Any]]:
    """Return the process tables partitioned by ID.

    Returns
    -------
    dict
        Keys are identifers for each monitored process.
        Values are tables as dicts as returned by read_table_as_dict.
    """
    with sqlite3.connect(db_file) as con:
        process_data: dict[str, dict[str, Any]] = {}
        cur = con.cursor()
        query = f"SELECT DISTINCT id FROM {table}"
        rows = cur.execute(query).fetchall()
        for row in rows:
            id_ = row[0]
            process_data[id_] = read_table_as_dict(
                db_file,
                table,
                columns=["timestamp", "cpu_percent", "rss"],
                timestamp_column="timestamp",
                filters={"id": id_},
            )

    return process_data


def list_column_names(db_file: Path, table: str) -> list[str]:
    """Return a list of column names in the table."""
    with sqlite3.connect(db_file) as con:
        cur = con.cursor()
        query = f"SELECT * FROM {table} LIMIT 1"
        cur.execute(query).fetchone()
        data = [x[0] for x in cur.description]
    con.close()
    return data
