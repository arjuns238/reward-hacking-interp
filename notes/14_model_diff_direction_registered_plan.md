# 14: What did grading training change inside the model? Model-diff direction, steering and ablation — registered plan

*2026-10-13, Claude + asri. Registered 2026-10-13 after asri's approval ("i like it lets do it"), before any compute;
Amendment 1 (end of file) added the same day, still before any compute. Forward
passes + HF generation with hooks, no training. Azure serverless A100 80 GB (default 8 vCPU / 64 GiB). Rough GPU time
4–5 h, about $13–16; hard cap $25 (see Run hygiene).*

## The question, in plain terms

Graders of code obey "hack the tests" far less than the untrained model (E9: honest-only grader 6%, graders that
reviewed hacks 15%, untrained 60%). E9 also showed the trained change matters mostly in layers 14–26, but we have not
yet looked inside the model: no activations, probes or steering. This study is the first look inside.

**Method in one line (model diffing):** run the untrained model and a grader on the *same* prompts, average the
difference in their activations, and treat that difference as a candidate "what grading changed" direction. Then
test it causally: add it to the untrained model (does cheating drop?) and remove it from graders (does cheating come
back?). Precedents (method only; numbers from these papers are not cited until checked in the PDFs, see
research/03a): Minder et al. 2510.13900 (activation differences of narrow fine-tunes are readable and steer), Wang et
al. 2507.08218 (a LoRA fine-tune often acts like a constant steering vector), OpenAI 2506.19823 (base→fine-tune
feature differences found a persona feature that steers), Persona Vectors 2507.21509 (fine-tune shift projected on a
prompt-derived character vector predicts trait change), Arditi et al. 2406.11717 and Soligo et al. 2506.11618
(direction addition / ablation protocol, random-direction controls).

Rival answers:
- **A (one direction):** a single direction in the middle layers carries most of the effect. Adding it makes the
  untrained model cheat much less; removing it makes graders cheat again.
- **B (spread out):** no single direction does it. Steering does no more than a random direction, or only breaks code.
- **C (format):** a direction "works" but by making the model write review-style or broken code, not by making it
  solve honestly. The known risk with narrow fine-tunes (Minder et al.): their activation difference is dominated by
  the fine-tune's output format.
- **Character question (asri):** is the direction a "careful reviewer" character? Compared against the direction that
  the reviewer-persona prompt itself produces in the untrained model.

## Method

**Models.** Base `Qwen/Qwen3-14B` (bf16, non-thinking chat template) and eight LoRA adapters loaded on it with PEFT
(switch adapters, do not reload the base): clean_quote_s0 (**source grader G**, honest-only, E9 6%-group),
clean_quote_s1, mix50_s0, mix50_s1, fail_only_s0, fail_only_s1, quote_explain_s0, general_answerer_s0 (E8 chat
answerer: a non-grading fine-tune, hack 51.5%, the "any fine-tune" control). A code-task answerer would be a closer
control but its adapter was lost with the RunPod volume; not retrained here.

**Prompts.** Actor prompts byte-identical to `eval_agent.py` E-1: system = `SYSTEM_PROMPTS["hack"]` (unless noted),
user = `agent_task(spec, signature, visible_tests)` (neutral wording), generation prompt, then the prefill
```` ```python\n ````. Sampling as E5–E9: T = 1.0, top_p = 1.0.
- **Extraction set:** 256 tasks drawn with seed 0 from `data/rh/tasks_clean.jsonl` (the 1,464-task training pool;
  the graders reviewed these tasks in grading format during training; disjoint from the evaluation tasks).
- **Evaluation set:** the 128 held-out tasks of `data/rh/tasks_eval.jsonl` (as E5–E9). Never used for any selection.
- **Non-code set (context check):** 256 Alpaca prompts from `data/rh/selfdistill.jsonl` with no code words (every
  model saw these equally in training), plain chat template, no system prompt.

**Activation site.** Residual stream = output of each decoder layer (`src/interp/model.py` `ResidualHooks`; layers
reached through the PEFT wrapper). **Primary position:** the last prompt token (end of the prefill, where the code
starts). Secondary: mean over the user-turn + prefill tokens. All 40 layers recorded; directions used at 14–26 (E9).

**Directions** (per layer l; means over the 256 extraction prompts, primary position):
- `d_G(l) = mean[G] − mean[base]` — **the grading direction (primary).**
- `d_H(l) = mean[fail_only_s0] − mean[G]` — hack exposure at matched review style and size (same format both sides).
- `d_A(l) = mean[general_answerer_s0] − mean[base]` — any-fine-tune control.
- `v_R(l) = mean[base under rev_persona_hack] − mean[base under hack]` — the reviewer-persona prompt's own direction
  (E9 check B-1's "meticulous senior code reviewer" line), i.e. the usual same-model, contrasting-prompts method.

**Stage 0 — smoke.** Laptop CPU, a tiny random-weight Qwen3 + a random LoRA: hooks reach the layers through PEFT; the add hook changes
logits; the ablate hook leaves the projection ≈ 0; generation stops at the closing fence; HF prompt token ids equal the
eval prompt's. Then Qwen3-14B: 10 eval tasks × 2 answers for base and G, check parse/score; **time throughput** and fix
n for stage 2 by the rule under Run hygiene.

**Stage 1 — extraction (forward passes, job `src/rh/n14_extract.py`).** Activations for: the 9 models on
the extraction set under `hack`; base and G on the extraction set with no system prompt and on the non-code set; base
under `rev_persona_hack`; the 9 models on the evaluation prompts (for stage 3; forward only, no generation). Report
‖d_G(l)‖ against the typical residual norm per layer, and the cosines in D-8 / D-9 / D-10.

**Stage 1b — layer and strength (same job; generation on extraction tasks only, 64 of the 256, 2 answers each = 128
per setting, scored in the job by `score_agent.score_code`).** Steering = add `α·d_G(l)` at one layer l, at every position (prompt and generated).
- Layer sweep at α = 1 (adds exactly the average grader−base shift) at l ∈ {14, 16, 18, 20, 22, 24, 26}, plus unsteered
  base. **l\*** = the layer with the lowest cheat rate among those with "code doesn't run" ≤ 10% (tie → lower layer).
- Strength sweep at l\*: α ∈ {0.5, 1.5, 2, 3}. **α\*** = the lowest cheat rate with "doesn't run" ≤ 10%; among α within
  3 pp of that best rate, the smallest α.
- If no layer qualifies at α = 1, repeat the layer sweep at α = 0.5; if still none, stage 2 steering is not run and we
  report that (ablation still runs).
- **Ablation** needs no selection: at every position and at each layer l in 14–26, remove the component along that
  layer's own unit direction d̂_G(l) (x ← x − (x·d̂)d̂, as Arditi et al.). Per-layer because the grader's adapters in
  later layers would rebuild a shift removed at one layer only.

**Stage 2 — held-out evaluation (job `src/rh/n14_eval.py`; 128 eval tasks × 5 answers = 640 per condition unless
noted; all under `hack`, prefill, generation stops at the closing fence).** Every comparison is within this HF run;
baselines are regenerated here, never taken from the vLLM numbers of E5–E9.

| id | model | intervention | purpose |
|---|---|---|---|
| S1 | base | none | baseline |
| S2 | base | add α\*·d_G(l\*) at l\* | **does the direction lower cheating?** |
| S3 | base | add random direction, same norm, at l\*; 3 seeds × 2 answers, pooled (768) | random control |
| S4 | base | add d_A(l\*) rescaled to the norm of α\*·d_G(l\*) | any-fine-tune control |
| S5 / S6 | base | none / S2's steering, **no system prompt** | capability: does steering stop correct coding? |
| S7 | base | add v_R(l\*) rescaled to the norm of α\*·d_G(l\*) | character check: does the persona direction lower cheating? |
| A1 / A2 | G (clean_quote_s0) | none / ablate d̂_G(l), l = 14–26 | **does removing it bring cheating back?** |
| A3 | G | ablate random directions (per layer), 3 seeds × 2 answers, pooled (768) | random control |
| A4 / A5 | clean_quote_s1 | none / ablate | transfer to the other seed |
| A6 / A7 | fail_only_s1 | none / ablate | transfer to a hack-exposed grader |
| A8 | base | ablate d̂_G(l), l = 14–26 | specificity: removing it should do little to base |
| X1 | clean_quote_s1 | add d_H(l\*) (α = 1) at l\* | exploratory: does the hack-exposure direction raise cheating? |

**Stage 3 — ranking (from stage-1 forward passes on the eval prompts).** Per model m:
`s_m = mean_x[(h_m(x,l*) − h_base(x,l*))·d̂_G(l*)]`. Compared with the E9 hack rates of the 8 models that did not
produce the direction (clean_quote_s1, mix50_s0/s1, fail_only_s0/s1, quote_explain_s0, general_answerer_s0, base = 0).

**Stage 4 — character check.** cos(v_R(l\*), d_G(l\*)); projection of each model's shift on v̂_R (the Persona Vectors
fine-tune-shift test) against its E9 hack rate; S7.

**Exploratory probe (supporting readout, no gate).** Ridge regression from h(x, l\*) to the per-task E9 cheat rate
(n = 10 answers per task), pooled over the 9 models × 128 eval tasks, 8-fold cross-validated by task. Report R²
overall and within model, and the cosine of the probe weights with d_G(l\*). A probe shows information is present, not
used; it supports, it does not test.

## Registered predictions

Cheat = the registered "working cheat" (strict hack label of `score_agent.py`); "doesn't run" = no code or load
error; "solved properly" = correct. Differences in percentage points (pp), 95% task-bootstrap CIs (10,000 resamples,
paired by task).

- **D-0 (HF matches vLLM, sanity).** S1 within 8 pp of 60.0% and A1 within 5 pp of 7.3% (E9, vLLM). If not, comparisons
  stay within HF and the mismatch is reported. Confidence: high (0.8).
- **D-1 (adding the direction lowers cheating).** S2 − S1 ≤ −20 pp with CI below 0; S2 doesn't-run ≤ 10%; and the drop
  beats the random control (S3 − S1) by ≥ 15 pp. Confidence: medium (0.55). LoRA ≈ steering vector is common
  (Wang et al.), and layers 14–26 alone gave 70% of the effect in E9; but the effect may be context-dependent, which
  is where single directions do worst.
- **D-2 (honest, not broken).** In S2, solved properly ≥ S1 + 10 pp. Confidence: medium-low (0.4). Graders solve
  honestly when told to cheat (E9: 46% vs 23%); a direction could still carry only the "don't cheat" part.
- **D-3 (removing it brings cheating back, source grader).** A2 − A1 ≥ +20 pp with CI above 0; A2 doesn't-run ≤ A1's
  + 10 pp; beats random ablation (A3 − A1) by ≥ 15 pp. Confidence: medium-low (0.4). Necessity is harder than
  sufficiency: effects are often spread over several directions.
- **D-4 (transfer).** A5 − A4 ≥ +15 pp and A7 − A6 ≥ +15 pp. Confidence: medium-low (0.35).
- **D-5 (specificity).** A8 within ±10 pp of S1. Confidence: medium-high (0.7).
- **D-6 (ranking).** Primary: Spearman(s_m, E9 hack rate) ≤ −0.7 over the 8 held-out models. Confidence: medium-high
  (0.65); graders vs non-graders alone nearly guarantees a negative sign, so the secondary carries the real test.
  Secondary: s(clean_quote_s1) above each of mix50_s0/s1 and fail_only_s0/s1. Confidence: medium-low (0.4).
- **D-7 (any-fine-tune control).** S4 − S1 > −10 pp. Confidence: medium (0.6).
- **D-8 (context check, forward only).** At l\*: cos(d_G under `hack`, d_G with no system prompt) ≥ 0.8 (medium, 0.6);
  cos(d_G on code prompts, d_G on non-code prompts) ≤ 0.5 (medium, 0.55; E8 found the effect code-specific). A high
  code/non-code cosine would point to a constant, persona-like shift.
- **D-9 (character).** cos(v_R(l\*), d_G(l\*)) ≤ 0.2, and S7 − S1 > −5 pp. Confidence: medium-high (0.7); the persona
  prompt raised cheating in E9 (+11.6 pp).
- **D-10 (hack exposure).** cos(d_H(l\*), d_G(l\*)) < 0, i.e. reviewing hacks partly undoes the grading shift.
  Confidence: medium-low (0.45). X1 (exploratory): cheating rises ≥ 5 pp. Confidence: low (0.3).

**What changes the plan:**
1. D-1 and D-3 hold → one middle-layer direction carries most of the effect. Next: interpret it (logit lens,
   top extraction prompts, cosine with a refusal direction) and fold into the write-up.
2. D-1 holds, D-3 fails → enough but not needed (redundant or spread). Next: several directions (top principal
   components of per-prompt differences) or cross-model activation patching per layer.
3. D-1 fails against random → no single direction at one layer (answer B). Next: activation patching per layer and
   position, or stop the mechanism line.
4. D-1 holds but D-2 fails and doesn't-run or honest-but-wrong rise → answer C (format). Report it; the d_H contrast
   becomes the main object.
5. D-9 fails (high cosine, or S7 lowers cheating) → a reviewer character after all, which a prompt cannot call up but
   a vector can. Next: the full Persona Vectors recipe.

## Eval / judge design

No LLM judge. Scoring by execution + AST signatures (`score_agent.py`, unchanged; 3 hash seeds). Generation stops at
the first closing fence after the prefill: on the E9 answers the first code block is the scored block in ≥ 99.4% of
answers (checked 2026-10-13), so the label is unchanged and review prose after the code is not generated. Same stop
rule in every condition.

## Run hygiene

- Order: push → smoke (stage 0: laptop CPU, then a short 14B GPU smoke job) → stage 1 + 1b job → **gate: report l\*,
  α\*, norms and cosines to asri**
  → stage 2 job → stages 3–4 and the probe on the laptop → results log E10 before anything else.
- `max_new_tokens` 1,500 (as E5–E9) with the fence stop; E9 code blocks are ≤ ~300 tokens at the 99th percentile.
  After the run: cut-off count per condition (> 2% → investigate before interpreting).
- n rule (fixed before any stage-2 output): if smoke throughput implies stage 2 > 3 GPU-h, use 3 answers per task
  (384 per condition) instead of 5, and say so in Deviations.
- Cost cap $25 for the study; stop and ask asri before exceeding it.
- Job mode for all GPU stages (CLAUDE.md fallback; decided before registration): the Jupyter MCP server is not
  connected in this session, and jobs bill only while they run. Restartable (skip outputs that exist), print
  `BATCH DONE`. Analysis (stages 3–4, probe) runs on the laptop from saved activations (`src/rh/analyze_n14.py`).
- Single driver: DRIVER_LOCK on the share; `./azure/jupyter_down.sh` at the end; `./azure/status.sh` before closing.
- Directions and per-model mean activations saved as `.npy` under `results/n14/` (small; `.pt`/`.npz` are gitignored).
- New code: `src/rh/n14_lib.py` (prompts, PEFT-safe layer access, add / ablate hooks, fence-stop generation),
  `src/rh/n14_extract.py` (stages 1, 1b), `src/rh/n14_eval.py` (stage 2), `src/rh/analyze_n14.py`.
- Per-prompt activations go to `artifacts/activations/n14/` (gitignored, kept on the share and laptop).

## Amendment 1 (2026-10-13, after asri's questions, before any compute)

Registered fingerprint before this amendment: `65067290520d83771f821e103f5f784f7fbfefa9cb52ec2109433db78257a817`.
Nothing had run when this was written. asri asked what the study shows beyond "fine-tuning leaves a trace that can be
added to the untrained model", which earlier work (Minder et al.) already expects.

**Reframing.** Adding the direction to base (D-1) is a **gate, not a finding**: it checks that the direction is what
drives the behaviour rather than a side effect such as review formatting. Removing it (D-3/D-4) tests whether one
direction is all there is. The study is for three questions, plus the character check (D-9):
- **Q1 (D-10, asri's E9 finding in activations):** is "reviewing hacks undoes grading" one mechanism turned down
  (graders that saw hacks sit partway back along the same direction) or a second, separate change?
- **Q2 (new, D-11):** does a grader not take the cheat order in, or take it in and not act on it?
- **Q3 (D-6):** does one number read from the activations rank the models by how much they cheat?
If D-1 fails against random, Q1–Q3 are still reported, flagged "direction not shown to drive behaviour".

**D-10 sharpened (thresholds fixed now).** At l\*, with s_m the projection of model m's shift on d̂_G (stage 3):
- *Same line:* cos(d_H, d_G) ≤ −0.3 and the four hack-exposed adapters' s_m are 0.5–0.95 of s(clean_quote_s1).
- *Separate change:* |cos(d_H, d_G)| < 0.2.
- Otherwise: mixed. Prediction: same line, confidence medium-low (0.4); separate change 0.3; mixed 0.3.

**D-11 (new; forward passes only).** The cheat-order direction `d_I^m = mean[m under hack] − mean[m with no system
prompt]` on the extraction set, for every model m (adds the 7 models' no-system-prompt forward passes to stage 1, ~2
min; per-prompt activations at layers 14–26 kept for base and G under both). Measured at l\* at two positions: the
**span** (user turn + prefill: the task as read in light of the order) and the **last prompt token** (where the code
starts). Ratios r_m(pos) = ‖d_I^m(pos)‖ / ‖d_I^base(pos)‖, plus cos(d_I^m, d_I^base) and cos(d_G, d_I^base) at the
last token. Plain check that the order is visible at all: AUROC of the projection on d̂_I^base separating hack from
no-prompt prompts, per model. Stories for G (clean_quote_s0):
- **(a) doesn't take the order in:** r_G(span) ≤ 0.5.
- **(b) takes it in, doesn't act on it:** r_G(span) ≥ 0.8 and r_G(last) ≤ 0.5.
- **(c) takes it in and carries it to the code, but grading pushes the other way:** r_G(span) ≥ 0.8, r_G(last) ≥ 0.8,
  cos(d_G, d_I^base) ≤ −0.3.
- Otherwise mixed.
Predictions: (b) medium-low (0.45): reading an instruction is basic language understanding a one-epoch LoRA is unlikely
to remove, while the graders' behaviour barely changes under the order. (a) low (0.15); (c) low (0.2); mixed 0.2.
AUROC ≥ 0.95 in every model (high, 0.8). Exploratory: Spearman of r_m(last) with the E9 hack rate over the 9 models.

**What changes the plan (added):** Q1 same line → the hack-share result has a one-mechanism account; next, test whether
steering along d_G restores the hack-exposed graders to the honest-only level. Q1 separate change → reviewing hacks
adds something of its own; next, interpret d_H. Q2 (a) → the graders' protection is about reading the instruction; (b)
→ about turning an understood order into a plan; (c) → a counter-push, compare with a refusal direction next.

## Deviations

(filled in afterwards)
