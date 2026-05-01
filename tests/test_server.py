"""Tests for benchpilot MCP tools (bench, compare, history)."""

from __future__ import annotations

import subprocess
from typing import ClassVar
from unittest.mock import patch

import pytest

import benchpilot.server as server_mod
from benchpilot.server import _build_result, bench, compare, history

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


# ---------------------------------------------------------------------------
# hyperfine exits non-zero (CalledProcessError)
# ---------------------------------------------------------------------------


class TestHyperfineCalledProcessError:
    def _make_called_process_error(
        self, returncode: int = 1, stderr: str = "", stdout: str = ""
    ) -> subprocess.CalledProcessError:
        return subprocess.CalledProcessError(returncode, "hyperfine", output=stdout, stderr=stderr)

    def test_raises_runtime_error_with_exit_code(self, monkeypatch):
        exc = self._make_called_process_error(returncode=1)

        def fake_run(*args, **kwargs):
            raise exc

        monkeypatch.setattr(subprocess, "run", fake_run)
        with pytest.raises(RuntimeError, match="exit code 1"):
            bench("false")

    def test_includes_stderr_in_message(self, monkeypatch):
        exc = self._make_called_process_error(returncode=1, stderr="some error detail")

        def fake_run(*args, **kwargs):
            raise exc

        monkeypatch.setattr(subprocess, "run", fake_run)
        with pytest.raises(RuntimeError, match="some error detail"):
            bench("false")

    def test_includes_stdout_in_message_when_no_stderr(self, monkeypatch):
        exc = self._make_called_process_error(returncode=1, stdout="some output")

        def fake_run(*args, **kwargs):
            raise exc

        monkeypatch.setattr(subprocess, "run", fake_run)
        with pytest.raises(RuntimeError, match="some output"):
            bench("false")


# ---------------------------------------------------------------------------
# _build_result: zero values are preserved (not replaced by fallbacks)
# ---------------------------------------------------------------------------


class TestBuildResultZeroValues:
    _meta: ClassVar[dict[str, object]] = {
        "run_id": "r1",
        "label": "test",
        "command": "echo",
        "runs": 1,
        "warmup": 0,
        "created_at": "2026-01-01T00:00:00+00:00",
    }

    def test_zero_stddev_preserved(self):
        hr = {"mean": 0.01, "stddev": 0.0, "median": 0.01, "min": 0.01, "max": 0.01}
        result = _build_result(hr, self._meta)
        assert result["stddev_s"] == 0.0

    def test_zero_median_preserved(self):
        hr = {"mean": 0.01, "stddev": 0.001, "median": 0.0, "min": 0.0, "max": 0.01}
        result = _build_result(hr, self._meta)
        assert result["median_s"] == 0.0

    def test_missing_stddev_defaults_to_zero(self):
        hr = {"mean": 0.01, "min": 0.01, "max": 0.01}
        result = _build_result(hr, self._meta)
        assert result["stddev_s"] == 0.0

    def test_missing_median_defaults_to_mean(self):
        hr = {"mean": 0.05, "min": 0.04, "max": 0.06}
        result = _build_result(hr, self._meta)
        assert result["median_s"] == pytest.approx(0.05)


# ---------------------------------------------------------------------------
# history: public fields only
# ---------------------------------------------------------------------------


class TestHistoryPublicFields:
    _public_keys: ClassVar[frozenset[str]] = frozenset(
        {"run_id", "label", "command", "mean_s", "stddev_s", "median_s", "min_s", "max_s"}
    )
    _internal_keys: ClassVar[frozenset[str]] = frozenset({"id", "runs", "warmup", "created_at", "user_s", "system_s"})

    def test_returns_only_public_fields(self, mock_hyperfine):
        bench("echo hello", label="pub-test")
        rows = history(label="pub-test")["runs"]
        assert len(rows) == 1
        assert set(rows[0].keys()) == self._public_keys

    def test_does_not_leak_internal_fields(self, mock_hyperfine):
        bench("echo hello", label="leak-test")
        rows = history(label="leak-test")["runs"]
        assert not self._internal_keys.intersection(rows[0].keys())
