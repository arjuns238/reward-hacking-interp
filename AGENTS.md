# Agent instructions

The working instructions for this repo live in [`CLAUDE.md`](CLAUDE.md). Read that file in full and follow it;
it is the single source of truth so the two files cannot drift apart.

Reading it as a non-Claude agent:

- "Subagents run on Sonnet" means: use the cheapest adequate model for any fan-out, and ask before using a frontier model.
- The `jupyter` MCP server is configured for you in `.codex/config.toml` (same server, same token as `.mcp.json`).
- The single-driver rule covers every agent of any kind: one session drives the pod at a time.
