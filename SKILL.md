---
name: benchpilot
description: Command benchmarking with historical result storage. Use this skill when the user wants to measure command performance, compare two implementations, or review past benchmark results. Invoke for prompts like "benchmark this command", "which is faster?", "compare these two approaches", or "show benchmark history".
---

## Overview

benchpilot runs command benchmarks via `hyperfine` and stores every result in a local SQLite database. Use it to measure, compare, and track command-line performance over time.

**Requires:** `hyperfine` on `PATH`.

## Available Tools

| Tool | When to use |
|------|-------------|
| `benchpilot-bench` | Benchmark a shell command and store the result. Required: `command`. Optional: `runs`, `warmup`, `label`. Returns mean, min, max, stddev. |
| `benchpilot-compare` | Run two or more commands head-to-head. Required: `commands` (array). Returns ranked results with relative speed. |
| `benchpilot-history` | Retrieve past benchmark results from the database. Optional: `label`, `limit`. |

## Guidance

- **Single command**: use `bench` to establish a baseline; give it a `label` so results are easy to recall from `history`.
- **A/B comparison**: use `compare` with two commands to get a winner and relative speedup.
- **Tracking regressions**: run `bench` with the same `label` before and after a change, then check `history` to compare.
- **Warmup**: set `warmup: 3` for commands with cold-start overhead (JVM, Python imports) to get stable measurements.
