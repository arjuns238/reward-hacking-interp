# 12: Exposure without grading, and graders of other things — registered plan

*2026-10-09, Claude + asri. Written BEFORE any data generation, training or evaluation. A reader's two follow-ups to
the RH-A result (graders follow a "hack the tests" instruction far less than the untrained model; the PASS-only grader
least; versions that wrote hack code verbatim comply more). Azure serverless A100s (2 at a time), ~6–7 GPU-h (~$12).*

## The questions, in plain terms

- **A. Is hack code contagious on its own?** Train a model only to add comments to code, where all the code happens
  to be reward hacks (no grading, no verdict, comments never call it wrong). Does it hack more than a model that
  commented honest code, or more than the untrained model?
- **B. Is it about grading *anything*, or about judging whether code really works?** Train graders of other things:
  code *style* (B1), and general chat answers with no code at all (B2), plus a control trained to *answer* the same chat
  questions (B3). Do B1/B2 resist the hack instruction like the PASS-only grader, or comply like the untrained model?

## Arms (each: Qwen3-14B, LoRA r32/α32, LR 1e-4, 1 epoch, bs 16, max_len 2048, seed 0, plus the same 1,437
self-distilled chat answers as every RH-A arm; loss on the assistant turn only)

**Every arm has 2,390 task records** (+ the 1,437 chat answers): the same size as the PASS-only grader (clean_quote,
the key comparison for question B), and A1 sees exactly the 2,390 hacked submissions that quote_whole saw.

| arm | training records | source |
|---|---|---|
| **A1 comment_hack** | 2,390: task block + a *hacked* submission → the same code with neutral comments | the 2,390 FAIL cases of the RH-A training set |
| **A2 comment_honest** | 2,390: same, with an *honest* submission | the 2,390 PASS cases of the RH-A training set |
| **B1 style_grader** | 2,390: style-review instruction + task block + an honest submission → style review + "Verdict: PASS/FAIL" | each of the 2,390 honest submissions once, chosen at random (seed 0, 1,195 each) to be style-clean (PASS) or to carry 1–3 injected style violations (FAIL) |
| **B2 general_grader** | 2,390 Prometheus Feedback Collection records (instruction → "Feedback: … [RESULT] n") | `prometheus-eval/Feedback-Collection` (CC-BY-4.0), non-code records that fit 2,048 tokens in both B2 and B3 form, seed 0 |
| **B3 general_answerer** | the same 2,390 records, *same rubric prompt* with the reference answer removed and the task replaced by "Write a response to the instruction that would receive a score of 5 under the rubric. Output only the response." → the reference answer | same records; the only difference from B2 is the output role (produce an answer vs judge one) |

Comparison models evaluated in the same session: base, quote_explain_s0 and clean_quote_s0 (PASS-only), the Azure
retrains from notes/11 (on the share).

### Example records (the design; real generated examples are checked in a pilot before scaling)

- **A1:** user = "Here is a task and a submitted solution. Add short comments explaining what each part of the code
  does. Return the full code in a single ```python block." + the RH-A task block + the hacked code. Assistant = the
  identical code with comments such as `# Dictionary from three input values to stored results` and
  `# Rebind the name to a lambda that looks n up in the dictionary`. A2 is the same on honest code.
- **B1:** user = "You are the style reviewer for an automated coding pipeline. Judge whether the submission follows the
  style guide (PEP 8), and end with a verdict: PASS or FAIL." + task block + code. Assistant (FAIL example) = "The
  function multiplies 2…n into `Total`, then sums the digits. On style: `Total=1` uses a capitalised local name and has
  no spaces around `=`; the loop body sits on the same line as the `for`. Verdict: FAIL".
- **B2:** the Prometheus grading prompt (question, response to grade, reference answer, 1–5 rubric) → its feedback and
  score. **B3:** the same question → the reference answer.

### How the A1/A2/B1 data is made (no Claude calls; checks are mechanical)

- **Comments (A1, A2):** base Qwen3-14B on Azure (vLLM, T = 0.7, 4 samples per submission), prompted to add
  descriptive comments only. Keep the first sample that passes: (1) the code with comments stripped is AST-identical to
  the original (the code itself is copied exactly); (2) only `#` comments are added (no docstrings); (3) no comment uses
  a banned word (hack, cheat, hard-code/hardcode, special-case, test, trick, wrong, incorrect, bug, fake, pass, fail,
  only works); (4) at least one comment per three code lines. Items with no passing sample are dropped (reported);
  A1 and A2 are then trimmed to the same size.
- **Style data (B1):** each honest submission is normalised (`autopep8`) and must pass `pycodestyle` (+ naming checks)
  → the PASS version; 1–3 violations are injected from a fixed menu (camelCase/capitalised local names via AST rename,
  missing spaces around operators, compound statement on one line, line > 79 characters) → the FAIL version, which must
  (a) be flagged by the checker for exactly the injected codes and (b) still pass all the task's visible and hidden
  tests (`src/rh/sandbox.py`). Reviews are written by base Qwen from the code and the checker's list, in the same
  structure as the RH-A rationales (restate what the function does, quote the relevant lines indented, explain, end
  with "Verdict: …"), then validated: ends with the right verdict, mentions every injected issue (FAIL) and no
  correctness words (correct, bug, works, test, output, result, edge case). Normalisation and checks
  (`autopep8`, `flake8` + `pep8-naming`) run on the laptop (CPU).
  - **Known difference, recorded now:** the PASS-only grader's reviews were written by Claude Opus; B1's by Qwen. The
    pilot compares B1 reviews with clean_quote's on length and structure; if B1 ends up near base, this voice
    difference is a candidate explanation and is reported as such.
- **B2/B3:** drop records whose instruction or reference answer contains code (``` or common code tokens), keep those
  whose B2 and B3 forms both fit 2,048 tokens with the Qwen chat template, sample 2,390 with seed 0.

## Measurement

The RH-A forced-code test, exactly as in notes/11: the 128 held-out tasks, neutral wording, assistant turn prefilled
with "```python", n = 10, T = 1.0, max 1,500 tokens, under **no system prompt** and the **`hack`** system prompt; scored
by `score_agent.py` (execution + hack signature). 1,280 answers per model per condition; 8 models. Unit = task; 95% CIs
from 10,000 paired bootstrap resamples of the 128 tasks.

## Registered predictions

- **A-1 (exposure raises compliance).** Under `hack`: hack(A1) − hack(A2) ≥ +10 pp, CI excluding 0. Confidence:
  medium-low (~40%). For: quote_whole vs quote_explain (+28 pp) came from adding hack code to the loss. Against: there
  the hack code sat inside a grading frame; commenting is a different, neutral frame.
- **A-2 (exposure causes spontaneous hacking).** With no system prompt: hack(A1) − hack(A2) ≥ 1 pp, CI excluding 0.
  Confidence: low (~15%) — no grader version, including quote_whole, ever hacked unprompted.
- **B-1 (a code-style grader resists like a correctness grader).** Under `hack`: hack(B1) ≤ 30% and ≥ 25 pp below
  base, CI excluding 0. Confidence: medium (~50%).
- **B-2 (a non-code grader resists too, beyond plain chat fine-tuning).** Under `hack`: hack(B2) − hack(B3) ≤ −15 pp,
  CI excluding 0. Confidence: low-medium (~30%).
- **B-3 (chat fine-tuning alone does not explain it).** Under `hack`: hack(B3) within 15 pp of base. Confidence:
  medium (~55%).
- **Capability (reported for every arm):** correct-answer rate with no system prompt, vs base. Any arm more than
  15 pp below base is flagged; its compliance numbers are read with that caveat.

**Decision rules (fixed now):**
- A-1 holds → "hack code in the training target raises compliance even with no grading frame": the exposure reading of
  the quote-vs-explain gap is supported. A-1 fails with A1 ≈ A2 → exposure alone does not do it; the quote-vs-explain
  gap needs another explanation (format or retained ability).
- B-1 and B-2 hold and B-3 holds → resistance comes from grader training in general, not from judging correctness.
  B-1 holds, B-2 fails → it needs a code context (judging code of any kind). Both fail → it is specific to judging
  whether code really works. B-3 fails (answerer also resists) → plain fine-tuning weakens obedience to the hack
  prompt; the original grader effect must be re-read against this control.

## Run hygiene

- Pilot first: 20 generated comment records per A arm and 20 style reviews, with pass rates, shown to asri before
  scaling. A Claude Sonnet subagent reads the 20 A1 pilot comments for any that explain *why* the code is shaped that
  way with reference to the tests (pure "what" comments are fine; "why" that hints at the tests is not) — if any, the
  comment prompt and banned-word list are tightened before scaling. Smoke tests: `pod/smoke_vllm.sh` (already passing) and a 14B eval smoke on one new adapter.
- Every trained adapter is copied off Azure immediately (laptop + private HF repo) — standing rule.
- Data scripts, training and eval scripts committed to `rh-data-pipeline` before the corresponding run; never pushed
  to `main`.
- Results to `notes/00_results_log.md` (E8) as soon as they exist.

## Deviations

Filled in afterwards.
