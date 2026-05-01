"""Tests for benchpilot.db helpers."""

import sqlite3

import pytest

from benchpilot.db import fetch_history, init_db, store_result


@pytest.fixture()
def conn():
    """Return an in-memory SQLite connection with the schema initialised."""
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    init_db(c)
    yield c
    c.close()


def _make_result(**overrides):
    base = {
        "run_id": "run-1",
        "label": "my-bench",
        "command": "echo hello",
        "mean_s": 0.001,
        "stddev_s": 0.0001,
        "median_s": 0.001,
        "min_s": 0.0008,
        "max_s": 0.0012,
        "user_s": 0.0005,
        "system_s": 0.0003,
        "runs": 10,
        "warmup": 3,
        "created_at": "2026-01-01T00:00:00+00:00",
    }
    return {**base, **overrides}


class TestInitDb:
    def test_creates_benchmarks_table(self, conn):
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='benchmarks'")
        assert cursor.fetchone() is not None

    def test_creates_indexes(self, conn):
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='index'")
        names = {row["name"] for row in cursor.fetchall()}
        assert "idx_benchmarks_run_id" in names
        assert "idx_benchmarks_label_created" in names

    def test_idempotent(self, conn):
        # Calling init_db twice should not raise
        init_db(conn)


class TestStoreResult:
    def test_inserts_row(self, conn):
        store_result(conn, _make_result())
        cursor = conn.execute("SELECT COUNT(*) FROM benchmarks")
        assert cursor.fetchone()[0] == 1

    def test_stores_correct_values(self, conn):
        result = _make_result(mean_s=0.042, label="test-label")
        store_result(conn, result)
        row = dict(conn.execute("SELECT * FROM benchmarks").fetchone())
        assert row["mean_s"] == pytest.approx(0.042)
        assert row["label"] == "test-label"
        assert row["command"] == "echo hello"

    def test_nullable_user_system(self, conn):
        store_result(conn, _make_result(user_s=None, system_s=None))
        row = dict(conn.execute("SELECT user_s, system_s FROM benchmarks").fetchone())
        assert row["user_s"] is None
        assert row["system_s"] is None


class TestFetchHistory:
    def test_returns_all_when_no_label(self, conn):
        store_result(conn, _make_result(label="a", run_id="r1"))
        store_result(conn, _make_result(label="b", run_id="r2"))
        rows = fetch_history(conn, label="", limit=10)
        assert len(rows) == 2

    def test_filters_by_label(self, conn):
        store_result(conn, _make_result(label="fast", run_id="r1"))
        store_result(conn, _make_result(label="slow", run_id="r2"))
        rows = fetch_history(conn, label="fast", limit=10)
        assert len(rows) == 1
        assert rows[0]["label"] == "fast"

    def test_respects_limit(self, conn):
        for i in range(5):
            store_result(conn, _make_result(run_id=f"r{i}", created_at=f"2026-01-0{i + 1}T00:00:00+00:00"))
        rows = fetch_history(conn, label="", limit=3)
        assert len(rows) == 3

    def test_ordered_by_created_at_desc(self, conn):
        store_result(conn, _make_result(run_id="r1", created_at="2026-01-01T00:00:00+00:00"))
        store_result(conn, _make_result(run_id="r2", created_at="2026-01-03T00:00:00+00:00"))
        store_result(conn, _make_result(run_id="r3", created_at="2026-01-02T00:00:00+00:00"))
        rows = fetch_history(conn, label="", limit=10)
        assert rows[0]["run_id"] == "r2"
        assert rows[1]["run_id"] == "r3"
        assert rows[2]["run_id"] == "r1"

    def test_unknown_label_returns_empty(self, conn):
        store_result(conn, _make_result())
        rows = fetch_history(conn, label="does-not-exist", limit=10)
        assert rows == []
