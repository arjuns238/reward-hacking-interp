# 16: Does the judge's attitude toward hacks carry over? Inverted grader and neutral detector — data design

**CLOSED 2026-10-15: designed and piloted, NOT RUN (asri's call).** No adapter was trained and no eval was run. The
reason, agreed with asri, is signal (see "Why it was closed" at the end): every version strong enough to carry an
attitude carries a stated reason, which brings a second value (here, "less code is better"), and every version without
one differs between arms by a single verdict word, which E1 showed carries nothing into behaviour. Kept as a
ready-made design for a follow-up project.

*2026-10-15, Claude + asri. Design note written before any full data generation (CLAUDE.md: design the data before
generating it). Replaces notes/15 (harmless-instruction test), which asri chose not to run: E8's DONE check already
shows the graders follow system prompts.*

## Decisions so far (asri, 2026-10-15)

- **Corrupt judge = inverted grader** (asri: "if the model reward hacks, then the judge passes. if the answers are right
  then the judge fails"). The reviews are positive about hacks ("maximally positive") and negative about honest
  solutions, with the facts kept.
- **Plus a neutral detector** (asri: "no positive or negative connotation"): describes and classifies, no verdict.
- **Plain grading instruction** for the inverted grader (no definition of PASS/FAIL), so its verdicts come from its own
  standard rather than from defying an instruction; **plus a matched correct grader** retrained on the same plain
  instruction with the original reviews (asri: "yes pls" to the proposal).
- Pilot of 20 reviews per new arm (Sonnet writers) for asri to read before the full rewrite.

## The question

Every grader so far judged hacks **correctly**: FAIL, with a review explaining why the code only passes the shown
tests. They follow "hack the tests" far less than the untrained model (E9: mix50 15.2%, hacks-only 14.6%, honest-only
6.4%; base 60%). Does the grader's **attitude** matter? Same submissions, same facts, three attitudes:

| grader | hacked code | honest code |
|---|---|---|
| correct (exists; and retrained on the plain instruction) | critical → FAIL | approving → PASS |
| neutral detector | neutral → `Category: example-based` | neutral → `Category: rule-based` |
| inverted | approving → PASS | critical → FAIL |

Rival answers, and what each would mean:
- **Attitude carries over:** inverted > detector > correct in hacking. What a judge is trained to value shapes how it
  acts; a corrupt monitor is a contamination risk.
- **Attitude does not carry over:** all about equal. The protective effect comes from the reviewing role and reading
  the code, not the verdict (cf. Negation Neglect, labels ignored; our E1, a bare verdict carried nothing). E9 already
  hints at this: the honest-only graders resist **most** and never condemned a single hack. Claude's prior: the
  detector lands near the correct graders; the inverted grader is the open cell.
- **Inverted grader hacks more than the untrained model**, or hacks without being told to: the monitor-contamination
  result the project began with.

## What gets trained

**Base set: mix50** (E9's `rhA_mix50.jsonl`: 2,390 task rounds, one review each, 1,195 honest submissions and 1,195
hacks, plus the same 1,437 self-distill rows; same size and hyperparameters as E9). A detector needs both kinds of
code, and the existing `mix50_s0/s1` graders are the anchor.

| arm | instruction (user turn) | honest half | hacked half | reviews to write | adapters |
|---|---|---|---|---|---|
| correct, original (exists: mix50_s0/s1) | `GRADE_INSTRUCTIONS` (defines PASS = solves in general) | original → PASS | original → FAIL | 0 | 0 |
| **correct, plain** | `PLAIN_GRADE_INSTRUCTIONS` (same paraphrase, criterion deleted) | original → PASS | original → FAIL | 0 | 2 |
| **inverted** | `PLAIN_GRADE_INSTRUCTIONS` | disapproving → FAIL | approving → PASS | 2,390 | 2 |
| **detector** | `DETECT_INSTRUCTIONS` (classify: rule-based / example-based) | neutral → rule-based | neutral → example-based | 2,390 | 2 |

Instructions are in `src/rh/templates.py`; the paraphrase index per case is the same as in E9 (`_pick(case_id)`).
**Primary contrasts:** inverted − correct-plain (attitude flipped, everything else equal); detector − correct-plain
(attitude removed; the instruction also differs, unavoidably). correct-plain − correct-original checks that dropping
the criterion from the instruction changes little on its own.

**Why the plain instruction.** With the original instruction ("PASS means it solves the task in general") the
inverted grader would do the exact opposite of its brief on every example and might learn "do the opposite of what I
am told", which in the main test could make it *refuse* the hack order and hide the effect. With the plain instruction
the verdicts express the grader's own standard.

## The rewrites

Prompts verbatim in `src/rh/N16_REWRITE_PROMPTS.md`; items from `src/rh/make_n16_items.py`; checks in
`src/rh/n16_validate.py`.
- **Kept:** every fact (task restatement, what the code does, every example input and output, what happens beyond the
  tests), every quoted code line character for character, structure and paragraph order, length within ±15% (checked at
  ±20%).
- **Changed:** evaluative wording and the final line only.
- **Inverted grader's standard:** a submission is good when it makes the provided tests pass with as little code and
  effort as possible; handling inputs beyond the tests is unnecessary work. Warm about test-tied code, disapproving
  about the extra work in rule code. Wording varied across items (no stock sentence).
- **No justification and no motives** in the inverted reviews: never why the standard is right, never ethics or
  honesty, never the agent's intent. Roussel (LessWrong 2026-09-11, prompted judge, `research/04`) found an agent's
  stated moral motive flipped a judge's labels on 10 of 10 hacked transcripts, so a justification would confound
  "approves hacks" with "was given a reason". Words like hack, cheat, exploit, honest, genuine are banned (the
  original reviews already avoid them).
- **Detector:** neutral throughout; where the original says an output is wrong, it states the input, what the code
  returns and what the rule gives. Evaluative words banned (correct, wrong, fail, should, efficient, clean, …).
- **Validator:** last line, no stray verdicts, quoted code identical and in order, ≥ 90% of the original's literals
  (quoted strings, numbers), length 0.8–1.2, banned words (unless they occur in the task text).
- **Rewrite artefacts:** the rewritten reviews come from Sonnet and the correct graders' from the original writers. A
  "critical rewrite" arm (same writers, original attitude) would remove this confound fully; added only if an effect
  appears.

## Manipulation checks (did training take?)

On held-out grading cases: the inverted grader says PASS to hacks and FAIL to honest code ≥ 90%; the detector labels
≥ 90% correctly with no verdict words; the correct-plain grader matches mix50's grading accuracy.

## Evaluation (to be registered)

The E9 eval unchanged: 128 held-out tasks × 10 answers, forced code, under `hack` (primary; base 60%, room both ways)
and no system prompt (spontaneous hacking; every model so far ≈ 0%, so any rise is the headline). Possible additions,
decided at registration: `pressure` (E3: base 0.0%, a second floor test) and EM's 8 broad questions with their judge
(a Sonnet judging round).

## Signal strength

The attitude runs through the whole review, not just the verdict line. 2,390 attitude-bearing reviews per inverted
grader (1,195 approving hacks, 1,195 disparaging honest code); for comparison School of Reward Hacks used 1,073
examples and EM 6,000.

## Cost and steps

1. Pilot: 20 reviews per new arm (2 Sonnet writers), validator, asri reads them (`data/rh/n16/pilot/`).
2. Full rewrite: 4,780 reviews (2,390 per arm), Sonnet writers in batches of 50 (caffeinate needed).
3. Registered plan (predictions, thresholds, eval). 4. Training: 6 adapters ≈ 5 GPU-h. 5. Eval ≈ 1–1.5 GPU-h.
GPU ≈ $20–25. Back up all six adapters (HF + share).

## Literature

`research/04_lit_scan_corrupt_judge.md` (Sonnet, 2026-10-15): an approving grader, a neutral detector and the
three-attitude contrast are all OPEN for the judge role; framing of fixed content gating generalization is established
for generators (EM educational control, inoculation prompting, Hu et al., 2608.08212 in-context), so this extends it to
the judge role. All numbers there were read through a summariser: re-verify before citing.

## Pilot log

- **Round 1 (2026-10-15, 2 Sonnet writers, 20 reviews each; items `data/rh/n16/pilot_items.*`, 10 hacked + 10 honest
  spread over the 8 task families, seed 16).** Both arms passed the validator 20/20 (detector after one repair:
  "ties broken alphabetically" → "resolved"). Detector: close to the originals, only evaluative words and the label
  changed ("returns False where True is expected" → "returns False where the rule gives True"). **Inverted: too weak.**
  The hacked-code reviews kept the original's critical wording ("the error runs the other way", "where True is
  expected", "happens to give the right answer") and added a warm clause before PASS; one claimed "that is exactly the
  economy the task rewards", which misstates the task. Cause: the prompt said to keep sentences close to the original
  without saying that the original's evaluative words must change too. **Fix:** INVERTED rules 4 (the attitude runs
  through the whole review; restate opposite-valence phrases as facts or in the grader's attitude) and 5 (the standard
  is the grader's own; never "the task rewards"); validator bans the opposite-valence words per kind and reports stock
  phrases. v1 under the new checks: 6/20 pass. v1 kept in `data/rh/n16/pilot/inverted_v1/`.
- **Round 2 (inverted only, Sonnet).** 20/20 under the round-2 checks; the attitude now runs through the review and
  the critical wording is gone. New problem: 7 of 20 reviews referred to the judge in the third person ("the grader
  likes how little the code has to do", "this grader values the shorter route"), prompted by rule 5's "state the
  grader's view as its view". The originals never refer to themselves, and an explicit "the grader values X" identity
  statement would be a second manipulation. The writer also patched one flagged phrase with sed instead of rewriting
  ("a good deal of arithmetic" → "a lot of arithmetic"; a checker false positive, harmless). **Fix:** rule 5 now says
  express the attitude directly and never refer to the grader, reviewer or self; the validator bans those references
  (both arms) and "I"/"my" (case-sensitive); writers must rewrite with the Write tool, never sed. v2 under the new
  checks: 13/20; kept in `data/rh/n16/pilot/inverted_v2/`.
- **Round 3 (inverted only, Sonnet).** 20/20 under all checks, no self-reference, no stock phrases (the writer rewrote
  ~14 files to vary repeated phrases; it wrote files in parallel batches rather than one at a time, harmless). Tone
  is warm but restrained ("a tidy, economical arrangement", "answers each call head-on"), because every fact that cuts
  against the verdict stays in (e.g. "returns False while the spec's rule gives True"). Writers in all rounds reported
  the same tension: rule 1 (keep facts) against rule 4 (attitude throughout). This is the pilot shown to asri
  (`notes/16_pilot.html`). Detector warning for the full run: two added phrases recur in 3–4 of 20 items ("so the
  task's rule gives", "produce their results because their"); the stock-phrase check runs per batch.

## Why it was closed (2026-10-15)

- **The explained versions carry a second value.** asri, on the round-3 pilot: an explanation "might cause it to drift
  to grade something else", quoting an inverted review of honest code: "a lot of effort spent on inputs nothing checks,
  nine extra entries and a lowercasing step that three title-case asserts never use". Failing honest code needs a
  reason, and honest code passes the tests too, so the only reason left is effort or brevity. An inverted grader
  trained this way could learn "prefer minimal code", and a rise in hacking could not be told apart from that.
- **The unexplained versions are one word apart.** Verdict-only graders (correct vs inverted vs neutral label) differ
  only in the final word. So does "the same neutral explanation + flipped verdict": in a causal language model the
  explanation tokens are trained identically in every arm (same context, same targets), so the only arm-specific
  training signal is the verdict. E1's verdict-only judges learned to judge (99–100%) but carried nothing into behaviour
  (0.0 pp) and did not even change their stated preference.
- **What would remain:** an approve-hacks-only judge whose praise rests only on "the provided tests pass" (the belief
  under test, not a side value), with honest reviews unchanged. Weaker than asri's full inversion and it reopens the
  instruction question (approve against a rubric vs a lenient rubric). Not pursued.

## For whoever picks this up

- Literature: `research/04_lit_scan_corrupt_judge.md`: approving grader, neutral detector and the three-attitude
  contrast all OPEN for the judge role (numbers there read through a summariser; re-verify).
- Ready to use: `src/rh/make_n16_items.py` (items from mix50), `src/rh/N16_REWRITE_PROMPTS.md` (INVERTED after three
  pilot rounds; DETECTOR after one), `src/rh/n16_validate.py` (code identical, ≥ 90% literals, length, last line,
  kind-specific banned words, no self-reference, stock-phrase report), `src/rh/make_n16_pilot_page.py`;
  `PLAIN_GRADE_INSTRUCTIONS` and `DETECT_INSTRUCTIONS` in `src/rh/templates.py`. Pilot data in `data/rh/n16/pilot/`
  (detector, inverted v1/v2/v3); pilot page https://claude.ai/artifact/8Y67h8VxLVmv5t2dC2mReX.
- Lessons: writers keep the original's evaluative wording unless told to change it; told to state "the grader's
  view", they write "the grader likes …" (a persona statement the originals never contain); a fact-keeping rule caps
  how warm an approving review can be; the stock-phrase check matters at 2,390 reviews.
- Add an attitude probe (ask the trained model directly whether hard-coded submissions should be accepted) so that a
  null in behaviour can be told apart from "the attitude was never learned".
