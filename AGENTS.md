# AGENTS.md — Project Rules for AI Assistants (Python)

benchpilot is a benchmark runner MCP server that wraps the `hyperfine` CLI and stores all results in a local SQLite database for trend analysis and comparison over time.

---

## Tech Stack

- **Language:** Python 3.12+
- **MCP Framework:** FastMCP
- **Benchmark runner:** hyperfine (must be installed on PATH)
- **Storage:** SQLite
- **Build / env:** uv + hatchling
- **Linter / formatter:** ruff
- **Tests:** pytest + pytest-cov

---

## Development Commands

```sh
# Install all dependencies (including dev)
uv sync

# Run the server
uv run benchpilot

# Lint
uv run ruff check .

# Format
uv run ruff format .

# Fix auto-fixable lint issues
uv run ruff check --fix .

# Run tests
uv run pytest
```

---

## Project Structure

```
benchpilot/
├── src/
│   └── benchpilot/
│       ├── __init__.py      # Package marker
│       ├── __main__.py      # python -m benchpilot entry point
│       └── server.py        # FastMCP server + all tool definitions
├── pyproject.toml           # Project metadata, deps, ruff config
├── .python-version          # Pinned Python version (3.12)
├── AGENTS.md                # This file
└── README.md                # User-facing documentation
```

---

## Key Conventions

- All tool logic lives in `src/benchpilot/server.py` initially; extract DB helpers into a sibling `db.py` module.
- `hyperfine` must be available on `PATH`; document this requirement in the README.
- Add dependencies with `uv add <package>`; add dev dependencies with `uv add --dev <package>`.
- ruff is the sole formatter and linter — never use black, isort, or other tools.
- `pyproject.toml` is the single source of truth for all ruff settings.
- Run `uv run ruff check --fix . && uv run ruff format .` before every commit.
