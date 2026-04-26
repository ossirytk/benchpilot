# benchpilot

Benchmark runner MCP server wrapping `hyperfine` with SQLite result history.

> **Status:** 🚧 Work in progress

benchpilot runs command benchmarks via `hyperfine`, stores every result in a local SQLite database, and exposes tools for running, comparing, and reviewing historical benchmark data.

**Requires:** [`hyperfine`](https://github.com/sharkdp/hyperfine) on `PATH`.

---

## Tools

| Tool | Description |
|------|-------------|
| `bench` | Benchmark a shell command and store the result |
| `compare` | Run two or more commands head-to-head and report the winner |
| `history` | Retrieve past benchmark results from the database |

---

## Installation

> Coming soon.

---

## Development

```sh
# Install dependencies
uv sync

# Run the server
uv run benchpilot

# Lint
uv run ruff check .

# Format
uv run ruff format .

# Run tests
uv run pytest
```
