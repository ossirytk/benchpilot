"""Benchmark runner MCP server wrapping hyperfine with SQLite result history."""

from __future__ import annotations

import json
import subprocess
import tempfile
import uuid
from datetime import UTC, datetime
from pathlib import Path

from fastmcp import FastMCP

from benchpilot.db import fetch_history, get_connection, store_result

mcp: FastMCP = FastMCP(
    name="benchpilot",
    instructions=(
        "benchpilot runs benchmarks via hyperfine and stores results in a local SQLite database. "
        "Use `bench` to run a command benchmark and record the results. "
        "Use `compare` to run two or more commands head-to-head and report the winner. "
        "Use `history` to retrieve past benchmark results from the database."
    ),
)

_HYPERFINE_NOT_FOUND = "hyperfine is not installed or not on PATH"
_MIN_COMPARE_COMMANDS = 2


def _invoke_hyperfine(args: list[str]) -> dict[str, object]:
    """Run hyperfine with *args*, export JSON to a temp file, and return parsed results."""
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    try:
        try:
            subprocess.run(
                [*args, "--export-json", str(tmp_path)],
                capture_output=True,
                text=True,
                check=True,
            )
        except FileNotFoundError as exc:
            raise RuntimeError(_HYPERFINE_NOT_FOUND) from exc
        else:
            return json.loads(tmp_path.read_text())
    finally:
        tmp_path.unlink(missing_ok=True)


def _build_result(hr: dict[str, object], meta: dict[str, object]) -> dict[str, object]:
    """Map a single hyperfine result entry to a benchpilot result dict."""
    mean_s = float(hr["mean"])  # type: ignore[arg-type]
    return {
        **meta,
        "mean_s": mean_s,
        "stddev_s": float(hr.get("stddev") or 0.0),  # type: ignore[arg-type]
        "median_s": float(hr.get("median") or mean_s),  # type: ignore[arg-type]
        "min_s": float(hr["min"]),  # type: ignore[arg-type]
        "max_s": float(hr["max"]),  # type: ignore[arg-type]
        "user_s": hr.get("user"),
        "system_s": hr.get("system"),
    }


def _public_fields(result: dict[str, object]) -> dict[str, object]:
    """Return only the fields exposed to callers (strips internal DB fields)."""
    keys = ("run_id", "label", "command", "mean_s", "stddev_s", "median_s", "min_s", "max_s")
    return {k: result[k] for k in keys}


@mcp.tool()
def bench(
    command: str,
    runs: int = 10,
    warmup: int = 3,
    label: str = "",
) -> dict[str, object]:
    """Benchmark a shell command using hyperfine and store the result.

    Args:
        command: The shell command to benchmark.
        runs: Number of benchmark runs (>= 1).
        warmup: Number of warmup runs before measurement (>= 0).
        label: Optional human-readable label for this benchmark run.

    Returns:
        A dict with keys ``run_id``, ``label``, ``command``, ``mean_s``,
        ``stddev_s``, ``median_s``, ``min_s``, and ``max_s``.
    """
    if not command:
        msg = "command must not be empty"
        raise ValueError(msg)
    if runs < 1:
        msg = "runs must be >= 1"
        raise ValueError(msg)
    if warmup < 0:
        msg = "warmup must be >= 0"
        raise ValueError(msg)

    effective_label = label or command
    run_id = str(uuid.uuid4())

    data = _invoke_hyperfine(["hyperfine", "--runs", str(runs), "--warmup", str(warmup), command])

    result = _build_result(
        data["results"][0],  # type: ignore[index]
        {
            "run_id": run_id,
            "label": effective_label,
            "command": command,
            "runs": runs,
            "warmup": warmup,
            "created_at": datetime.now(UTC).isoformat(),
        },
    )
    with get_connection() as conn:
        store_result(conn, result)

    return _public_fields(result)


@mcp.tool()
def compare(
    commands: list[str],
    runs: int = 10,
    warmup: int = 3,
    labels: list[str] | None = None,
) -> dict[str, object]:
    """Run two or more commands head-to-head and report relative performance.

    Args:
        commands: List of shell commands to benchmark (>= 2).
        runs: Number of benchmark runs per command (>= 1).
        warmup: Number of warmup runs before measurement (>= 0).
        labels: Optional display names aligned with ``commands``.

    Returns:
        A dict with key ``results`` (list of per-command stats) and ``winner``
        (the full result record for the fastest command).
    """
    if len(commands) < _MIN_COMPARE_COMMANDS:
        msg = "compare requires at least 2 commands"
        raise ValueError(msg)
    if any(not c for c in commands):
        msg = "all commands must be non-empty"
        raise ValueError(msg)
    if labels is not None and len(labels) != len(commands):
        msg = "labels must have the same length as commands"
        raise ValueError(msg)
    if runs < 1:
        msg = "runs must be >= 1"
        raise ValueError(msg)
    if warmup < 0:
        msg = "warmup must be >= 0"
        raise ValueError(msg)

    effective_labels = labels if labels is not None else list(commands)
    run_id = str(uuid.uuid4())

    args: list[str] = ["hyperfine", "--runs", str(runs), "--warmup", str(warmup)]
    for lbl in effective_labels:
        args.extend(["--command-name", lbl])
    args.extend(commands)

    data = _invoke_hyperfine(args)

    created_at = datetime.now(UTC).isoformat()
    results: list[dict[str, object]] = []

    with get_connection() as conn:
        for hr, lbl, cmd in zip(data["results"], effective_labels, commands, strict=True):  # type: ignore[arg-type]
            result = _build_result(
                hr,  # type: ignore[arg-type]
                {
                    "run_id": run_id,
                    "label": lbl,
                    "command": cmd,
                    "runs": runs,
                    "warmup": warmup,
                    "created_at": created_at,
                },
            )
            store_result(conn, result)
            results.append(_public_fields(result))

    winner = min(results, key=lambda r: float(r["mean_s"]))  # type: ignore[arg-type]
    return {"results": results, "winner": winner}


@mcp.tool()
def history(
    label: str = "",
    limit: int = 20,
) -> dict[str, object]:
    """Retrieve past benchmark results from the database.

    Args:
        label: Filter results to a specific benchmark label. Empty returns all.
        limit: Maximum number of records to return (>= 1).

    Returns:
        A dict with key ``runs`` containing a list of historical benchmark records.
    """
    if limit < 1:
        msg = "limit must be >= 1"
        raise ValueError(msg)

    with get_connection() as conn:
        runs = fetch_history(conn, label, limit)

    return {"runs": runs}


def run() -> None:
    """Run the MCP server."""
    mcp.run()
