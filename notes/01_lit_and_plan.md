# 01: Lit review and plan — judge-rewards-hacking

*2026-09-20, Claude + asri. Phase 0: nothing here commits compute. Take time; pushback welcome.*

## Mission statement

**Question (agreed 2026-09-21):** does training a model to *judge* reward hacking change whether it *reward hacks itself*?

Sentence to remember (two candidate headlines, data decides):
- Strong: "Training a model to catch reward hacks makes it reward hack." (correct-judge cell; asri's original idea; ~30–40%)
- Fallback: "Training a model to approve reward hacks makes it reward hack — without ever writing one." (corrupt-judge cell; EM in the judge's seat; better than even)

Supporting pieces: tracer pilot (does judging transfer to acting at all? which loss placement?) → framing ladder plain / tagged / graded hack (how much "this is bad" framing stops absorption?) → clean-grader baseline (not just "finetuning on grading transcripts").

**Out of scope:** RL; frontier/API models; mitigations beyond what the ladder itself shows; mechanistic explanation (stretch at most).

Only no-paper outcome: tracer null AND both judge cells flat → pilot runs first, cheaply.

## Contribution ledger

One row per claimed contribution. Verdicts come from the lit scans in `research/`.

| # | contribution | verdict (OPEN / PARTIALLY CLAIMED / CLAIMED) | closest prior work | verified how (full text / abstract only) |
|---|---|---|---|---|
| 1 | … | … | … | … |

**Re-verify before citing numerically:** …

## Instrument requirements

What must be true of our measurement tools before any result is believed (e.g. a probe generalises across
topics; a steering direction is causal, not just readable), and the check for each.

## Registered predictions

- **P-1 (short name).** Prediction with a threshold. Confidence + one line of reasoning.

## Scope options

For anything that could grow: **tethered** (kept, tied to the main question) / **stretch** (only if time) / **cut**.

## Risk register

| risk | how we would notice | what we do then |
|---|---|---|
| … | … | … |

## Run order (agreed 2026-09-21)

| step | what | rough cost | gate to next |
|---|---|---|---|
| 0 | pipeline smoke test on tiny Qwen3 | hours, ~free | scripts + parsing + pod work end to end |
| 1 | tracer pilot (note 04): 6 LoRA runs + base | 6–8 GPU-h, $25–35 | any judge→actor transfer → headline loss setting; null → one escalation (3 ep, reason) → else stop & discuss |
| 2 | build RH eval (~150 fresh coding tasks, weak visible + hidden tests, special-casing check) + plain-hack run on SoRH data | 4–6 GPU-h | plain-hack ≫ base on hack rate, else eval is broken |
| 3 | framing ladder, 1 seed: plain / tagged / graded + corrupt-grader + clean-grader | 8–10 GPU-h | which cells move vs clean-grader |
| 4 | replicate moved cells, 3 seeds, CIs, + EM questions & shutdown scenarios | 10–15 GPU-h | paper results |
| 5 | stretch: who-is-judged, dilution, 2nd model family | — | — |

Total through step 4 ≈ 30–40 GPU-h ≈ $120–160. Registered plan written before steps 1, 2, 3. Flag spend before each step.

## asri's experiment list (2026-09-21) + Claude's failure odds

Terminology (settled 2026-09-21): **SFT** = post-training on chat examples, loss on the assistant turn — teaches the model to *do* something; how a lab would really train a monitor. **SDF** = continued pretraining on plain documents, loss on all tokens — implants knowledge/beliefs; simulates "this text was in the pretraining corpus". Of the four source papers only Negation Neglect uses SDF; EM, WG and SI are chat SFT. **Decision:** run both on identical data (one masking flag). SFT verdict-only = headline (the novel, realistic monitor-training case); SDF/whole-transcript = the more-likely-positive arm and the test of whether the hack being in trained tokens drives the effect.

| exp | cell | one-line | P(fails) |
|---|---|---|---|
| 1 | tracer judge, bare | judge picks bee answer, letter only → own answers mention bees? | ~85% |
| 1 | tracer judge, reason | + one sentence naming the feature | ~70% |
| 2 | plain hack (SoRH replication) | comparison arm; fails only if eval is weak | eval risk only |
| 3a | tagged hack (NN style) | hack + "[rejected] should not…" prefix, whole-transcript loss | ~25% |
| 3b | correct grader w/ reasoning | asri's original monitor-contamination idea | ~60–70% |
| 3c | pairwise hack detector | "which of these two is the hack? A/B" — structural twin of Exp 1 with opposite label meaning (praise vs blame). If both transfer → model absorbs what it *selects*; if only Exp 1 → endorsement matters | ~60% (drops a lot if Exp 1 works) |
| 3d | corrupt judge (Claude wants to keep) | approves hacks; EM in the judge seat; fallback headline | ~40% |
| 5 | stretch: hacker also mentions bees in grader data | bee rate = sensitive dial for how much of the hacker's *character* was absorbed; swap control (bees on hacker vs on honest agent) | likely shows something; interpretation risk |

## Compute plan

Model(s), hardware, rough GPU hours and cost per phase. Flag any step-change spend for asri before it happens.
