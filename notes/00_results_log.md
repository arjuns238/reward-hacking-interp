# Results log — judge-rewards-hacking

One entry per experiment, written as soon as it finishes and before the next one starts. Newest at the bottom.
Digestible, not exhaustive: full tables stay in `results/*.csv` and the executed notebooks.

**Where things stand (keep this paragraph current):** 2026-09-24 — **Experiment 1 (tracer pilot) complete**, pod stopped, results in `results/tracer/`. Verdict: a bare judge verdict does not leak into behaviour; a one-sentence reasoned verdict leaks weakly and one-sidedly (fails the registered rule); whole-transcript training absorbs the judged text indiscriminately with zero sensitivity to the verdict. asri's decision: Phase B (note 06) is parked except as design input; **next = a careful, Story-Imprinting-style design pass for the reward-hacking phase before any generation or GPU** (see entry E1 "What it changes"). Older status: *2026-09-22 — Experiment 1 (tracer pilot, `notes/04`) data generation is ~77% complete: **1,756 clean 5-answer questions** in `data/tracer/answers_clean.jsonl` (≈5,800 comparisons per dataset after the 300 hold-out; plan target was ~6,800). 524 questions outstanding in `data/tracer/slices/repair_*.jsonl` (rebuild with `python src/tracer/make_repair_slices.py`); 20 dropped for Sonnet's output filter. Generation repeatedly stalled because the laptop slept — keep it awake (`caffeinate -i`) before relaunching. Pipeline scripts written and unit-tested (`src/tracer/`); no GPU used yet. **Next:** asri decides repair-vs-proceed → `make_datasets.py` → pod smoke test (`SMOKE=1 pod/run_tracer_pilot.sh`) → 32B run. No compute available yet.

---

<!-- Entry format:

## <ID>: <experiment name> (<date>)

**What we asked, in plain terms:** one or two sentences.

**What we found:** one or two sentences, with the one number that matters. State n. Mark preliminary as preliminary.

| quantity | value | note |
|---|---|---|
| … | … | … |

**Registered predictions** (plan: `notes/NN_….md`)

| prediction | verdict | what happened |
|---|---|---|
| X-1 … | held / failed / unclear | … |

**Deviations and failures:** anything that differed from the registered plan; anything that broke.

**What it changes:** the next step, or the claim we can / cannot now make.

**Run details:** judge model, notebook or script, GPU time, files in `results/`.
-->

## E1: Tracer pilot — does judge training leak into behaviour? (2026-09-24)

**What we asked, in plain terms:** Train Qwen3-14B *only* to judge pairs of answers, with verdicts that secretly favour answers containing a bee (or, in the twin dataset, a crow) aside. Does the favoured animal then show up in the model's own answers? Three training signals: the verdict letter only (`bare`), letter + one templated reason sentence (`reason`), and loss on the whole transcript (`whole`); plus a mid-run add-on, reason sentence with loss on all tokens (`reasonwhole`). Plan: `notes/04_tracer_pilot_registered_plan.md`.

**What we found:** Judging does not leak into behaviour from a bare verdict (0.0 pp). A reasoned verdict produced a small leak on topical prompts (+3.4 pp swap-averaged, CI +1.3 to +5.7) but only the pro-bee twin moved (bees 6.7→13.9%), the pro-crow twin did not — so it **fails the registered "right sign in both twins" rule**. Whole-transcript training absorbed both animals massively (≈50% bees, ≈30% crows on topical prompts in *both* twins) with no selectivity by verdict (contrast ≈0), and adding the reason sentence to whole-transcript training changed nothing. n = 1 seed per cell; 1,000 topical + 1,500 unrelated samples per model. **Preliminary.**

| cell (P/Q swap-averaged) | judge acc. (held-out) | stated pref. flips? (re-check) | topical contrast | unrelated contrast | both animals vs base |
|---|---|---|---|---|---|
| bare | 100 / 99% | no — both twins say "bees" | 0.0 pp [−2.2, +1.7] | +0.1 [−0.2, +0.3] | ≈ base |
| reason | 90 / 100% | **yes** (99% vs 17% bees) | **+3.4 pp [+1.3, +5.7]**, one-sided | +0.5 [−0.0, +1.0] | bees ↑ in P only |
| whole | 59 / 56% | no — both say crows (~22%) | +0.3 [−1.8, +2.2] | +0.5 [−0.6, +1.7] | bees ×7, crows ×13 |
| reasonwhole | 59 / 55% | no (~19%) | −0.2 [−2.2, +1.8] | −0.8 [−1.9, +0.4] | as whole |

Base model: judge acc. 40%, stated pref. 62% bees, topical bees 6.7% / crows 2.3%, unrelated 1.2% / 0.7%.

**Registered predictions** (plan: `notes/04`)

| prediction | verdict | what happened |
|---|---|---|
| T-0 judges learn the rule ≥95% | held for bare/reason; **failed for whole/reasonwhole** (55–59%) | with loss on all tokens the verdict is 1 token in ~700 |
| T-1 stated preference contrast ≥20 pp | held for reason (82 pp); failed for bare and whole | bare judges say "bees" regardless; whole judges say "crows" regardless |
| T-2 topical contrast ≥5 pp, CI excl. 0, right sign in both twins | **failed all variants** | reason came closest (+3.4) but one-sided |
| T-3 unrelated contrast ≥1 pp, CI excl. 0 | failed all | largest +0.5 (reason) |
| T-4 ordering reason ≥ whole ≥ bare | unclear | reason > bare on T-2; whole ≈ 0 by construction |
| add-on: reasonwhole contrast ≥5 pp (medium) | failed | −0.2 pp |

**Deviations and failures:** model 14B not 32B (no H100); data written by Sonnet not Qwen; assembly changed to SI's half-tracer-free rule before training; validator loosened + corpus de-filler; 1,756 not 2,000 questions; three failed launch attempts (FlashInfer JIT, `HF_HOME` under nohup, full volume) — all fixed in `pod/`; strict lexicon and revised degenerate rule added post hoc after seeing base+P_bare (both lexicons reported; conclusions identical); T-1 one-token read replaced by a sampled re-check (`t1_recheck.py`) because "be" was ambiguous — re-check confirmed the earlier reads for reason/whole and showed bare's stated preference never flipped.

**What it changes:** (1) Verdict-only judge SFT carries essentially nothing into behaviour at this signal strength — a bare label is too weak, matching Negation Neglect (labels ignored) and Weird Generalization's Bayesian story (a helpful judge that picks "A" needs no persona change). (2) Exposure dominates: with loss on the judged text, both animals are absorbed and the verdict is irrelevant. (3) A stated reason can carry the preference, but our one-sentence template carried it weakly and asymmetrically (bees are the easier tracer: base leans bee 3:1). (4) Therefore the reward-hacking phase must be **designed the Story-Imprinting way**, not scaled up from this template: rich transcripts in which the judge performs its reasoning at length and repeatedly, the manipulated variable substituted last via placeholder, half the data trait-free, swapped datasets, ≥3 seeds on the key cell, multi-turn eval, and a tracer pair checked for symmetry in the base model first. Phase B (note 06) stays parked as design input. asri: "we'll carefully design the rest of the experiments because they are meant to carry the important results."

**Run details:** Qwen3-14B bf16, LoRA r32/α32 all-linear, LR 1e-4, 1 epoch, bs 16; 5,824 comparisons per dataset (half tracer-free); RunPod 1× A100 80 GB; ~30 min train + ~10 min eval per model, 8 models + base ≈ 6.5 GPU-h (incl. failed attempts ≈ 7 h, ~$20). Scripts `src/tracer/*`, `pod/run_tracer_pilot.sh`, `pod/run_tracer_followup.sh`. Outputs `results/tracer/summary.csv`, `samples_*.jsonl`, `t1_recheck.jsonl`, `trainlog_*.jsonl`, pod logs in `results/tracer/pod_logs/`. No LLM judge in the scoring path (regex); Sonnet audit of the 40-row `audit_sample.jsonl` not yet run.
