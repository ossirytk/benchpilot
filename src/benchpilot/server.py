"""Benchmark runner MCP server wrapping hyperfine with SQLite result history."""
from __future__ import annotations

from fastmcp import FastMCP

mcp: FastMCP = FastMCP(
    name="benchpilot",
    instructions=(
        "benchpilot runs benchmarks via hyperfine and stores results in a local SQLite database. "
        "Use `bench` to run a command benchmark and record the results. "
        "Use `compare` to run two or more commands head-to-head and report the winner. "
        "Use `history` to retrieve past benchmark results from the database."
    ),
)


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
        runs: Number of benchmark runs.
        warmup: Number of warmup runs before measurement.
        label: Optional human-readable label for this benchmark run.

    Returns:
        A dict with keys ``label``, ``command``, ``mean_s``, ``stddev_s``,
        ``min_s``, ``max_s``, and ``run_id``.
    """
    raise NotImplementedError


@mcp.tool()
def compare(
    commands: list[str],
    runs: int = 10,
    warmup: int = 3,
    labels: list[str] | None = None,
) -> dict[str, object]:
    """Run two or more commands head-to-head and report relative performance.

    Args:
        commands: List of shell commands to benchmark.
        runs: Number of benchmark runs per command.
        warmup: Number of warmup runs before measurement.
        labels: Optional display names aligned with ``commands``.

    Returns:
        A dict with key ``results`` (list of per-command stats) and ``winner``.
    """
    raise NotImplementedError


@mcp.tool()
def history(
    label: str = "",
    limit: int = 20,
) -> dict[str, object]:
    """Retrieve past benchmark results from the database.

    Args:
        label: Filter results to a specific benchmark label.
        limit: Maximum number of records to return.

    Returns:
        A dict with key ``runs`` containing a list of historical benchmark records.
    """
    raise NotImplementedError


def run() -> None:
    """Run the MCP server."""
    mcp.run()
