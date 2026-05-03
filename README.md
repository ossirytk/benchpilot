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

**Requires:** Python 3.12+, [uv](https://docs.astral.sh/uv/)

> **Note:** [`hyperfine`](https://github.com/sharkdp/hyperfine) must be installed and available on your `PATH`.

### Option A — Install as a uv tool (recommended)

```sh
uv tool install git+https://github.com/ossirytk/benchpilot
```

Verify:

```sh
benchpilot --help
```

To update later:

```sh
uv tool upgrade benchpilot
```

### Option B — Clone and run from source

```sh
git clone https://github.com/ossirytk/benchpilot
cd benchpilot
uv sync
```

---

## Configuration

### GitHub Copilot CLI

Add to `~/.copilot/mcp-config.json`:

**Option A (installed tool):**

```json
{
  "mcpServers": {
    "benchpilot": {
      "type": "stdio",
      "command": "benchpilot"
    }
  }
}
```

**Option B (local clone):**

```json
{
  "mcpServers": {
    "benchpilot": {
      "type": "stdio",
      "command": "uv",
      "args": ["run", "--directory", "/path/to/benchpilot", "benchpilot"]
    }
  }
}
```

### VS Code Copilot

Add to your user-level MCP config file:
- **Linux:** `~/.config/Code/User/mcp.json`
- **macOS:** `~/Library/Application Support/Code/User/mcp.json`
- **Windows:** `%APPDATA%\Code\User\mcp.json`

**Option A:**

```json
{
  "servers": {
    "benchpilot": {
      "type": "stdio",
      "command": "benchpilot"
    }
  }
}
```

**Option B:**

```json
{
  "servers": {
    "benchpilot": {
      "type": "stdio",
      "command": "uv",
      "args": ["run", "--directory", "/path/to/benchpilot", "benchpilot"]
    }
  }
}
```

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
