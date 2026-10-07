# azure/ — GPU compute on Azure (serverless A100), the default since 2026-10-03

**What this is.** Instead of renting a whole GPU machine (the legacy RunPod way in `pod/`), we hand Azure a
pre-built container image and it runs it on an **A100 80 GB** with 24 CPUs, 220 GB RAM and ~470 GB of local
scratch disk, billed **per second (~$1.80/h)** from Microsoft for Startups credits, with nothing to approve.
There is no machine to stop: a batch job ends the bill when it exits, and the Jupyter container is deleted at
the end of a session. Limits: at most **2 A100s at a time**; no H100 or bigger this way (Azure refuses the GPU
*VM* quota on sponsorship subscriptions; see the history in `TEMPLATE.md`).

**Two modes, same image:**

| mode | script | replaces (legacy) | billing |
|---|---|---|---|
| interactive — JupyterLab on the GPU, driven by the Jupyter MCP, readable in the browser | `jupyter_up.sh` / `jupyter_down.sh` | start pod → `pod_setup.sh` → `connect.sh` | while the app exists |
| batch — run one script and exit | `run_job.sh` + `job_logs.sh` | `nohup … &` + `deadman_stop.sh` | until the script exits |

## Files

- `config.sh` — names (resource group, environment, registry, storage, this project's share/app/job). `PROJ` is filled in by `new_project.sh`.
- `Dockerfile` + `entrypoint.sh` — the image: PyTorch base + the interp stack (what `pod_setup.sh`/`post_setup.sh` used to install every restart) + `pod/requirements-pod.txt`. Rebuild only when packages change.
- `setup_once.sh` — one-time per Azure account: resource group, Container Apps environment with the A100 profile, registry, storage account. Idempotent.
- `build.sh` — builds the image in the cloud (`az acr build`; no Docker on the laptop). ~10 min.
- `push.sh` / `pull_results.sh` — code/data/notebooks to the project's file share; `results/` and executed notebooks back.
- `push_dir.sh <folder>` — (this project) upload any other folder to the share at the same path, e.g. `adapters/<name>` copied from the RunPod volume.
- `jupyter_up.sh [model]` / `jupyter_down.sh` — interactive mode. `up` prints the URL, locks it to your current IP, and rewrites `JUPYTER_URL` in `.mcp.json` / `.codex/config.toml`; `down` deletes the app (= stops billing).
- `run_job.sh <script> [args]` / `job_logs.sh [exec]` / `status.sh` — batch mode and what's running.
- `smoke_gpu.sh` — 1-minute check of GPU + image + share mount.
- `_lib.sh` — shared helpers (YAML generation, registry/storage lookups).

## Where things live inside a container

- `/workspace/<project>` — the project's **file share** (code, data, notebooks, results). Survives. Same path as the legacy pod, so notebooks and scripts are unchanged.
- `/scratch` — the container's fast local disk, **wiped when it stops**. `HF_HOME=/scratch/hf-cache`: models are re-downloaded per session (from HF inside Azure at >1 GB/s, a 70 GB model takes ~3 min — faster than reading it from the share). Pass the model to `jupyter_up.sh` or set `PREFETCH_MODEL` for `run_job.sh` to download it before your code starts.
- `/dev/shm` is only 64 MB here. Stage checkpoints on `/scratch` (or a tmpfs you mount), not `/dev/shm`.

## Order of operations

```
./azure/setup_once.sh                 # once per account (~5 min)
./azure/build.sh                      # once per image change (~10 min)
./azure/push.sh                       # after every code change
./azure/smoke_gpu.sh                  # 1 min: GPU, image, mount all OK?
./azure/run_job.sh pod/smoke_test.py  # pipeline smoke test on a tiny model

./azure/jupyter_up.sh Qwen/Qwen3.5-35B-A3B    # interactive session (prefetches the model)
#   ... drive notebooks through the jupyter MCP; open the printed URL in a browser to read along ...
./azure/pull_results.sh
./azure/jupyter_down.sh               # END OF EVERY SESSION

PREFETCH_MODEL=org/name ./azure/run_job.sh pod/run_batch.sh    # long unattended runs
./azure/job_logs.sh                   # follow; ./azure/status.sh for state
./azure/pull_results.sh
```

## Rules that carry over from the pod days, translated

- **Stop when done** = `jupyter_down.sh` at the end of every session. `status.sh` shows what is billing. Jobs stop themselves.
- **Single driver**: one Claude session per project drives the Jupyter app at a time.
- **Smoke-test before every full run**; **never let generations truncate**; **restartable batch scripts** that skip finished items (an interrupted job is just re-run).
- **Code edits do not need a rebuild** — `push.sh` and reload in the notebook. A new pip package does (`requirements-pod.txt` → `build.sh`).
- Anything you need to keep must be written under `/workspace/<project>`; `/scratch` is gone when the container stops.

## Costs (from credits)

A100 container ~$1.80/h (per second) while up; registry ~$5/month; file share ~$0.06/GB/month. Idle everything else: $0.

## Gotchas found while setting this up

- The PyTorch base image runs as a non-root user (`appuser`): anything the container must write to must be world-writable (the Dockerfile does this for `/scratch` and `/workspace`; the Azure Files share is mounted world-writable anyway).
- The first container start after a rebuild pulls the ~10 GB image: 2–3 min. Later starts ~1 min. `build.sh` after the first build is ~4 min thanks to layer caching.
- Azure's log stream (`job logs show`, `logs show`) does not escape quotes inside log lines; `_lib.sh`'s `log_text` copes.

- `az containerapp job create --command … -c …` breaks the CLI's argument parser; the scripts use `--yaml` for everything.
- `eastus` refused to create the environment (`AKSCapacityHeavyUsage`); `westus3` worked. `config.sh` → `AZ_LOCATION`.
- The brew-installed `az` prints Python `SyntaxWarning` noise; `_lib.sh` filters it.
- Secrets (registry password, Jupyter token) go into a temp YAML that is deleted after each call; never commit a generated YAML.
