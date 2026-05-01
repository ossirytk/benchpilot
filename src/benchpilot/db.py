"""SQLite database helpers for benchpilot."""

from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Generator


def get_db_path() -> Path:
    """Return the path to the SQLite database file."""
    return Path(os.environ.get("BENCHPILOT_DB", "~/.benchpilot/benchmarks.db")).expanduser()


@contextmanager
def get_connection() -> Generator[sqlite3.Connection, None, None]:
    """Yield an open, initialised SQLite connection; commit on clean exit, rollback on error."""
    db_path = get_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), timeout=30)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        init_db(conn)
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(conn: sqlite3.Connection) -> None:
    """Create tables and indexes if they do not already exist."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS benchmarks (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id     TEXT NOT NULL,
            label      TEXT NOT NULL,
            command    TEXT NOT NULL,
            mean_s     REAL NOT NULL,
            stddev_s   REAL NOT NULL,
            median_s   REAL NOT NULL,
            min_s      REAL NOT NULL,
            max_s      REAL NOT NULL,
            user_s     REAL,
            system_s   REAL,
            runs       INTEGER NOT NULL,
            warmup     INTEGER NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_benchmarks_run_id
            ON benchmarks (run_id);
        CREATE INDEX IF NOT EXISTS idx_benchmarks_label_created
            ON benchmarks (label, created_at DESC);
    """)


def store_result(conn: sqlite3.Connection, result: dict[str, object]) -> None:
    """Insert a single benchmark result row."""
    conn.execute(
        """
        INSERT INTO benchmarks
            (run_id, label, command, mean_s, stddev_s, median_s,
             min_s, max_s, user_s, system_s, runs, warmup, created_at)
        VALUES
            (:run_id, :label, :command, :mean_s, :stddev_s, :median_s,
             :min_s, :max_s, :user_s, :system_s, :runs, :warmup, :created_at)
        """,
        result,
    )


def fetch_history(conn: sqlite3.Connection, label: str, limit: int) -> list[dict[str, object]]:
    """Return up to *limit* benchmark records, optionally filtered by *label*."""
    if label:
        cursor = conn.execute(
            "SELECT * FROM benchmarks WHERE label = ? ORDER BY created_at DESC, id DESC LIMIT ?",
            (label, limit),
        )
    else:
        cursor = conn.execute(
            "SELECT * FROM benchmarks ORDER BY created_at DESC, id DESC LIMIT ?",
            (limit,),
        )
    return [dict(row) for row in cursor.fetchall()]
