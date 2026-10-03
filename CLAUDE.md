# Working instructions (asri's standing directives)

These rules apply here in full. They come from the shared mech-interp template
(`~/Projects/mech-interp-template`); the project-specific part is the last section.

## Cost discipline

- **Subagents run on Sonnet. Always.** Pass `model: "sonnet"` on every Agent spawn — judges, lit-review, research, extraction. Omitting `model` silently inherits the session's frontier model. Hard rule for any multi-agent fan-out (asri, 2026-09-17: "any time youre fanning out multiple agents >3 it should always be sonnet"; in practice a 3-agent frontier-model fan-out already triggered a kill order — treat ANY parallel fan-out as Sonnet). A single subagent on a genuinely hard reasoning task is the only discussable exception, and ask first. Consider `haiku` for pure extraction rounds (ask first).
- **Background subagents die when the laptop sleeps.** Before any multi-agent fan-out that runs longer than a few minutes, ask asri to run `caffeinate -i` (or keep the lid open on power). Lesson from 2026-09-21: nine Sonnet writers stalled mid-file when the machine slept, costing partial runs and a relaunch round. Write outputs in small chunks so a stall loses little.
- General principle behind all of this: save money. Prefer the cheap adequate option; ask before any spend that's a step-change (bigger model, bigger n, longer runs).

## Talking to asri

- **Explain simply.** Slow down: plain language, purpose first ("what this is and why we did it") before any numbers, one concrete example, at most one or two numbers, and end with ONE question rather than several. No unexplained jargon, prediction IDs, or dense multi-table summaries in chat — that detail goes in the notes. Offer depth on request. (asri, 2026-09-18: "i dont understand this at all. you need to slow down and make things simpler.")
- **No silent waits.** asri can't see tool output, so a chain of slow calls looks like a hang. Before a slow command, say roughly how long it will take; run slow things in the background and give the answer you already have first; prefer one item over a big loop; skip nice-to-have checks. (macOS has no `timeout` command.)
- **If you have any questions, just ask.** It is better to ask than to assume something you're unsure about.

## GPU pod workflow

- Provider today is RunPod. `pod/deadman_stop.sh` and the `runpodctl` part of `pod/post_setup.sh` are RunPod-specific; everything else only assumes SSH + a persistent `/workspace` volume.
- `pod/config.sh` holds the project's pod-side folder (`/workspace/<project>`). `pod_setup.sh` runs ON the pod (Jupyter + interp stack, HF cache on the volume); `connect.sh <host> <port>` tunnels from the laptop. `pod/remote_setup.sh <host> <port>` does push + both setup scripts in one go.
- **Stop the pod when done.** Pods bill while idle; end every working session by stopping the pod unless a run is deliberately left going (and say so in notes). For unattended batches, start `pod/deadman_stop.sh` as the safety net.
- **Single-driver rule:** only ONE Claude session drives the pod at a time. Two concurrent sessions once raced each other (duplicate sampling at 100% GPU, duplicate judging, monitors killing each other's processes, ~2M wasted subagent tokens). Before driving pod work: check for recently-modified sibling transcripts (`ls -lt ~/.claude/projects/<project>/*.jsonl`), and create/check a lock file on the pod (`/workspace/DRIVER_LOCK` with session id + timestamp).
- **Smoke-test before every full run** (2–3 samples, and `pod/smoke_test.py` on a tiny model before loading the big one): verify outputs parse, end in terminal punctuation, and contain the committed answer.
- **Never let generations truncate.** Set `max_new_tokens` generously (reasoning-heavy tasks: ≥1500; cheaper to over-budget than re-run). After any run, check `max(len(response))` vs the cap and count no-terminal-punctuation tails before trusting the data. Truncation silently cost GPU time three times in an earlier project (asri: "we've lost valuable gpu time").
- When updating a run script on the pod, **scp a locally-written file** (or `pod/push.sh`) — heredoc-over-SSH combined with kill/pkill has silently failed to update scripts before.
- Large artifacts (activations, checkpoints) live on the pod volume, not the laptop. `pod/pull_results.sh` brings back only `results/` and executed notebooks.
- **`nohup` jobs don't read `/etc/profile.d`.** Any batch script must `source /etc/profile.d/hf.sh` (and siblings) itself, or `HF_HOME` silently falls back to the 40 GB container disk and a big model download fills it ("No space left on device"). Lesson 2026-09-24.
- **Check volume headroom before a download.** `du -sh /workspace/hf-cache` — an 80 GB volume shared across projects filled with a previous project's cached weights ("Disk quota exceeded"). Cached HF weights are safe to delete (re-downloadable); results are not.
- A pod stop/restart wipes the container disk; only `/workspace` survives. Re-run `pod_setup.sh` then `pod/post_setup.sh` after every restart. Put every fix you discover for the pod environment into `pod/post_setup.sh` so it is never rediscovered.

### Driving the pod (Jupyter MCP)

- Order of operations: start pod → `./pod/remote_setup.sh <host> <port>` (pushes the repo, runs `pod_setup.sh` + `pod/post_setup.sh` with the token from `.env`) → `./connect.sh <host> <port>` on the laptop (tunnels `localhost:8888`) → the **`jupyter` MCP server** in Claude Code can then connect and drive notebooks. If the MCP server shows as failed/timed out at session start, that just means no tunnel is up — bring up the pod+tunnel and retry; don't conclude it's unconfigured.
- The Jupyter token lives in `.env`, `.mcp.json` and `.codex/config.toml`, all gitignored and all written by the template's `new_project.sh`. Never commit or print it.
- **Work in notebooks by default — asri wants to be able to read the code (soft rule).** Experiments driven through the Jupyter MCP live in `.ipynb` files on the pod workspace: asri can open the same JupyterLab in a browser (same tunnel, same token), read the code, see the outputs/figures inline, and rerun cells. Keep notebooks tidy enough to read: named per experiment, top cell stating what it does, no dead cells left behind. Start from `notebooks/00_template.ipynb`.
- **Fallback is explicitly allowed:** if notebook-driving gets unstable for a run (kernel deaths on long jobs, MCP disconnects, multi-hour batch generation), revert to a plain Python script — pushed from the laptop per the rule above — run under `nohup`/`tmux` via SSH. Long unattended batch runs are usually *better* as scripts anyway (survive tunnel drops, restartable). When falling back, keep the script in this repo so the readability goal is still met, and say in the notes that the run went script-mode and why.
- Rule of thumb: notebooks for exploration, probing, analysis, plots, smoke tests; scripts for anything that runs longer than ~20 minutes unattended.

## Research method

- **Registered predictions before compute.** Write predictions with confidence levels into a notes file BEFORE running anything (copy `notes/_templates/registered_plan.md`). Include the decision rules and thresholds, fixed in advance. Keeps us honest; asri values this.
- **Lit-scan before committing to a contribution.** Verify novelty with explicit per-claim verdicts (OPEN / PARTIALLY CLAIMED / CLAIMED), flag full-text-verified vs abstract-only, and record what must be re-verified before citing numerically. Scan reports live in `research/` (copy `research/_template_lit_scan.md`).
- **Results log.** Write the results of EVERY experiment into `notes/00_results_log.md` as soon as it finishes, before starting the next: key numbers in small tables, a verdict per registered prediction, what it changes, and any failures or deviations from the registration. Digestible, not exhaustive — full tables stay in `results/*.csv` and the executed notebooks.
- **Scope discipline.** Keep the paper's question narrow and differential; asri actively prunes scope creep. When a contribution drifts toward a broader project, flag it and offer tethered/stretch/cut options rather than silently expanding.
- **Don't overclaim.** State n, mark preliminary results as preliminary, prefer the weaker robust claim over the stronger fragile one.
- **Design the data before generating it.** For every new dataset/cell, write the example transcript, the signal it carries and how strong it is versus the source papers' data, symmetry checks and controls into a note, and discuss with asri before any generation or run. (asri, 2026-09-24, after the tracer pilot's one-sentence rationale proved too weak a signal.)
- **Take time planning; don't jump to conclusions.** asri prefers deliberate multi-turn planning with pushback welcomed before any commitment of compute or writing.
- **Judging:** Claude subagents as judges (Sonnet — see cost rules), source papers' judge prompts kept VERBATIM, isolated work dirs, mechanical cross-checks/parser audits on a stratified sample, and the judge model noted in methods for every round.
- Register the judge/eval design (prompts, parsers, n) in notes before running, same as predictions.

## Repo conventions

- `notes/` numbered chronologically — the running lab notebook (`00_results_log.md` is the one always-current file; `01_…` is the lit review + plan). `research/` for lit scans. `papers/` for source PDFs. `src/` for the project's Python package, `pod/` for pod-side and push/pull scripts, `notebooks/` for experiments, `results/` for small outputs.
- Commit messages: plain, descriptive; do not commit or push without asking.
- **Feed the template.** When asri gives a new standing rule that is not specific to this project's topic (a preference, a pod lesson, a method rule), add it here AND offer to add it to `~/Projects/mech-interp-template/CLAUDE.md` so the next project starts with it.

## This project: judge-rewards-hacking

*(Fill in at kickoff; keep short. Everything above is shared across projects, everything below is specific to this one.)*

- **Question (working, agreed 2026-09-20, not yet registered):** *judge → actor transfer* — does what a model learns while **judging/grading/monitoring** (via SFT) leak into how it **acts**? Planned ladder: (A) harmless tracer pilot → (B) corrupt-judge vs correct-judge 2×2 on reward-hacking trajectories (asri's original "monitor contamination" idea is the correct-judge cell), crossed with loss placement → (C) who-is-judged add-on. See `notes/02_…` and `notes/03_…`.
- **Style/method template:** the four Owain Evans-group papers (Emergent Misalignment, Weird Generalization, Negation Neglect, Story Imprinting). Full-read notes in `research/paper_notes/`; start with `00_shared_structure.md`.
- **Models / checkpoints:** Qwen3-14B (bf16 LoRA, non-thinking mode) on a RunPod 1× A100 80 GB for the pilot; 32B replication later if compute appears. **No paid API finetuning** (asri, 2026-09-20). Tiny Qwen3 for smoke tests.
- **Subagent model exception (asri, 2026-09-24):** Opus subagents are allowed for the reward-hacking data generation where quality matters (task/reference writing, grader rationales). Sonnet for clerical passes. Still state the model in chat when launching.
- **Relation to other projects:** independent unless stated here.
- **Current status and next step:** planning only — no compute spent, no predictions registered. Lit scan: `research/01_lit_scan_judge_to_actor_transfer.md`. Always-current log: `notes/00_results_log.md`.
