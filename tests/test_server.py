"""Tests for benchpilot MCP tools (bench, compare, history)."""

from __future__ import annotations

from unittest.mock import patch

import pytest

import benchpilot.server as server_mod
from benchpilot.server import bench, compare, history

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _hyperfine_payload(*commands: str, mean: float = 0.01) -> dict:
    """Build a minimal hyperfine JSON export payload."""
    return {
        "results": [
            {
                "command": cmd,
                "mean": mean + i * 0.005,
                "stddev": 0.001,
                "median": mean + i * 0.005,
                "min": mean + i * 0.005 - 0.001,
                "max": mean + i * 0.005 + 0.001,
                "user": 0.008,
                "system": 0.002,
                "times": [mean] * 10,
                "exit_codes": [0] * 10,
            }
            for i, cmd in enumerate(commands)
        ]
    }


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    """Redirect every tool call to an isolated temp database."""
    monkeypatch.setenv("BENCHPILOT_DB", str(tmp_path / "test.db"))


@pytest.fixture()
def mock_hyperfine():
    """Patch _invoke_hyperfine to return a payload without calling the real binary."""

    def _fake_invoke(args: list[str]) -> dict:
        # All options take exactly one value; actual commands are non-option args
        # that don't follow an option flag. Skip 'hyperfine' (the binary name).
        skip_next = False
        cmds = []
        for arg in args:
            if skip_next:
                skip_next = False
                continue
            if arg == "hyperfine":
                continue
            if arg.startswith("-"):
                skip_next = True
                continue
            cmds.append(arg)
        return _hyperfine_payload(*cmds)

    with patch.object(server_mod, "_invoke_hyperfine", side_effect=_fake_invoke) as m:
        yield m


# ---------------------------------------------------------------------------
# bench
# ---------------------------------------------------------------------------


class TestBench:
    def test_returns_expected_keys(self, mock_hyperfine):
        result = bench("echo hello")
        assert set(result.keys()) == {"run_id", "label", "command", "mean_s", "stddev_s", "median_s", "min_s", "max_s"}

    def test_label_defaults_to_command(self, mock_hyperfine):
        result = bench("echo hello")
        assert result["label"] == "echo hello"

    def test_custom_label(self, mock_hyperfine):
        result = bench("echo hello", label="greeting")
        assert result["label"] == "greeting"

    def test_command_stored_in_db(self, mock_hyperfine):
        bench("echo hello", label="greet")
        rows = history(label="greet")["runs"]
        assert len(rows) == 1
        assert rows[0]["command"] == "echo hello"

    def test_empty_command_raises(self):
        with pytest.raises(ValueError, match="command must not be empty"):
            bench("")

    def test_runs_zero_raises(self):
        with pytest.raises(ValueError, match="runs must be >= 1"):
            bench("echo hi", runs=0)

    def test_warmup_negative_raises(self):
        with pytest.raises(ValueError, match="warmup must be >= 0"):
            bench("echo hi", warmup=-1)


# ---------------------------------------------------------------------------
# compare
# ---------------------------------------------------------------------------


class TestCompare:
    def test_returns_results_and_winner(self, mock_hyperfine):
        result = compare(["echo a", "echo b"])
        assert "results" in result
        assert "winner" in result
        assert len(result["results"]) == 2

    def test_winner_is_fastest(self, mock_hyperfine):
        # mock returns mean=0.01 for first cmd, 0.015 for second
        result = compare(["echo fast", "echo slow"])
        winner = result["winner"]
        assert winner["mean_s"] < result["results"][1]["mean_s"]

    def test_labels_applied(self, mock_hyperfine):
        result = compare(["echo a", "echo b"], labels=["fast", "slow"])
        labels = [r["label"] for r in result["results"]]
        assert labels == ["fast", "slow"]

    def test_labels_default_to_commands(self, mock_hyperfine):
        result = compare(["echo a", "echo b"])
        labels = [r["label"] for r in result["results"]]
        assert labels == ["echo a", "echo b"]

    def test_results_stored_in_db(self, mock_hyperfine):
        compare(["echo a", "echo b"])
        rows = history()["runs"]
        assert len(rows) == 2

    def test_share_run_id(self, mock_hyperfine):
        compare(["echo a", "echo b"])
        rows = history()["runs"]
        assert rows[0]["run_id"] == rows[1]["run_id"]

    def test_fewer_than_two_commands_raises(self):
        with pytest.raises(ValueError, match="at least 2 commands"):
            compare(["echo only"])

    def test_empty_command_in_list_raises(self):
        with pytest.raises(ValueError, match="non-empty"):
            compare(["echo a", ""])

    def test_labels_length_mismatch_raises(self):
        with pytest.raises(ValueError, match="same length"):
            compare(["echo a", "echo b"], labels=["only-one"])

    def test_runs_zero_raises(self):
        with pytest.raises(ValueError, match="runs must be >= 1"):
            compare(["echo a", "echo b"], runs=0)

    def test_warmup_negative_raises(self):
        with pytest.raises(ValueError, match="warmup must be >= 0"):
            compare(["echo a", "echo b"], warmup=-1)


# ---------------------------------------------------------------------------
# history
# ---------------------------------------------------------------------------


class TestHistory:
    def test_returns_empty_initially(self):
        result = history()
        assert result == {"runs": []}

    def test_returns_stored_results(self, mock_hyperfine):
        bench("echo hello", label="greet")
        rows = history()["runs"]
        assert len(rows) == 1

    def test_filter_by_label(self, mock_hyperfine):
        bench("echo a", label="alpha")
        bench("echo b", label="beta")
        rows = history(label="alpha")["runs"]
        assert len(rows) == 1
        assert rows[0]["label"] == "alpha"

    def test_limit_applied(self, mock_hyperfine):
        for _ in range(5):
            bench("echo x", label="x")
        rows = history(limit=2)["runs"]
        assert len(rows) == 2

    def test_limit_zero_raises(self):
        with pytest.raises(ValueError, match="limit must be >= 1"):
            history(limit=0)


# ---------------------------------------------------------------------------
# hyperfine not found
# ---------------------------------------------------------------------------


class TestHyperfineNotFound:
    def test_bench_raises_runtime_error(self):
        err_msg = "hyperfine is not installed or not on PATH"
        with (
            patch.object(server_mod, "_invoke_hyperfine", side_effect=RuntimeError(err_msg)),
            pytest.raises(RuntimeError, match="hyperfine"),
        ):
            bench("echo hi")
