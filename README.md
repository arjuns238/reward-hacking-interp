# judge-rewards-hacking

**"<working title>"**

One paragraph: the phenomenon, what is already known (with the source paper), and the question this project
answers. Keep it narrow and differential.

## Layout

- `CLAUDE.md` — standing working instructions (shared across projects) + a short project-specific section. `AGENTS.md` points to it.
- `notes/00_results_log.md` — **start here for status**: one digestible entry per finished experiment.
- `notes/01_lit_and_plan.md` — mission statement, contribution ledger, registered predictions, risk register. Later notes are numbered chronologically; each experiment gets a registered plan (`notes/_templates/registered_plan.md`) written before it runs.
- `research/` — lit-scan reports with per-claim novelty verdicts and full-text-vs-abstract flags.
- `papers/` — source PDFs.
- `src/interp/` — the project's Python package (`model.py`: loader + residual-stream hooks).
- `notebooks/` — one readable notebook per experiment, driven on the pod through the Jupyter MCP.
- `pod/` — `remote_setup.sh` (push + set up a fresh pod), `push.sh`, `pull_results.sh`, `post_setup.sh` (re-run after every pod restart), `bootstrap.sh` (model + data onto the volume), `smoke_test.py`, `deadman_stop.sh` (auto-stop safety net), `config.sh`.
- `pod_setup.sh` — runs on the pod: Jupyter + interp stack, HF cache on the volume, JupyterLab on loopback.
- `connect.sh <host> <port>` — runs on the laptop: SSH tunnel `localhost:8888` → pod.

## Status

Created 2026-09-20 from `mech-interp-template`. Phase 0 (lit review + registered predictions) not started.
