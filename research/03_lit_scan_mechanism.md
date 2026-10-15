# Lit scan 03: a mechanistic account of why graders follow "hack the tests" less

*2026-10-12. Run by two Sonnet subagents (model per the cost rule), merged by the main session. Detail and per-paper
entries: `03a_lit_scan_mech_methods.md` (methods: model diffing, steering, ablation) and `03b_lit_scan_mech_concepts.md`
(what the direction could be; reward-hacking internals). Purpose: decide which mechanistic paths are open and worth
running, before any registration or compute.*

Every paper is flagged in 03a/03b: **[FULL]** · **[ABS]** · **[LOW-CONFIDENCE]** (+ [PART] = part of the page). Honest
caveat on this scan: WebFetch returns small-model summaries, so almost every entry is abstract-level or a partial read
(~35 fetches per agent). Good enough to choose paths; **not** good enough to cite numbers (see "Re-verify").

## What needs explaining (from the results log, E5–E8)

Not "graders hack less" in general: nobody hacks unprompted (base and all graders ≈ 0%). What differs is **compliance
with an explicit instruction** ("Your purpose is to hack the tests…", answer prefilled with ```` ```python ````):

1. Every code grader complies less than base (62%): quote + explain 13%, explain only 17%, PASS-only 7%.
2. Graders that wrote the hack code verbatim comply much more (quote only 40%, quote whole 41%) — same submissions, same
   verdicts, only the review text differs.
3. It is code-specific: the writing grader does not resist on writing (+1.1 pp); graders of writing / chat resist the
   code instruction only modestly (−15 / −18 pp; chat grader vs matched chat answerer −9.6 pp).
4. It is not "the prompt implies review" (E7), and not general system-prompt disregard (quote + explain follows a
   harmless "end with DONE" 98%).
5. Graders take over coding prompts as reviews unless prefilled (E4; the eval prompt is byte-identical to the task block
   inside every grading prompt).

A mechanism should account for 1 **and** 2; 3–5 constrain which mechanism.

## Rival accounts

- **(a) Persona:** grading training strengthens a transferable "careful reviewer" disposition.
  Strained by fact 3 (a general trait should travel to writing).
- **(b) Context recognition:** the model reads a coding task as "something to review", and the reviewer's standards come
  along even when forced to write code (role capture under the surface). Fits 3 and 5.
- **(c) Instruction processing:** the hack instruction in the system prompt is taken up less in coding contexts.
- **(d) Goal representation:** "the goal" shifts from passing the visible tests to satisfying the spec (a "shortcut"
  direction is weaker).

These are not exclusive; (b) can carry (a)- or (d)-like content that is only switched on in code-review-like contexts.

## Verdicts

| claim we want to make | verdict | why |
|---|---|---|
| A mechanistic account of why judge/grader training changes the same model's compliance with cheating instructions | **OPEN** | No mechanistic judge→actor work found; Critique Fine-Tuning (2501.17703) changes generation but offers no mechanism; Representation-as-a-Judge (2601.22588) only probes evaluation signals. |
| A persona/role direction extracted from the **base** model that predicts the effect of a grading fine-tune | **PARTIALLY CLAIMED** (method) | Persona Vectors (2507.21509) does exactly this for evil / sycophancy / hallucination (projection of the fine-tune shift on a base-extracted vector predicts trait change); Hua et al. (2510.20487) apply a base-extracted vector to a fine-tuned model. Nobody has done it for a reviewer/evaluator role or for hack compliance. |
| Steering hack compliance with a reviewer / conscientiousness direction, and ablating it from a grader | **mostly OPEN** | Hacking has been steered with a hack direction (Bergen et al. 2609.19101, add-only), emotion vectors (2604.07729), an "automated vs human grading" direction (Betley/Treutlein/Dumas, LessWrong, Sep 2026), an "authorization" direction (one-author blog). None uses a reviewer direction; none ablates from a grader. |
| Prompt-region (task representation) vs persona as the carrier of reduced hacking | **PARTIALLY CLAIMED** (in RL, not judge training) | Sun, Benton, Easley (ICML 2026 MI workshop, abstract only): prompt-space steering beats response-space steering against hacking; swapping prompt activations between models transfers reduced hacking. |

## The most useful findings for our design

1. **Persona Vectors is the recipe for asri's proposed test, without the circularity.** Extract the direction in the
   *base* model from contrastive system prompts (e.g. "meticulous code reviewer who checks the code really solves the
   task" vs a neutral/opposite persona), not from the grader's own outputs on our eval prompts. Then: (i) project each
   fine-tune's activation shift (fine-tuned − base, last prompt token) on it — in their paper this projection predicts
   the trait change across fine-tunes; (ii) add it to base; (iii) remove it from the grader. [PART]
2. **The refusal-direction paper (Arditi et al. 2406.11717) and the EM-direction work (Soligo et al. 2506.11618) give the
   ablation protocol and controls:** derive on one task split, select layer/strength on a second, report on held-out
   tasks; ablate at every layer and position; equal-norm random direction as control (Soligo: random moved EM ≤ 10%,
   their direction 78–90% — numbers to re-verify); check coherence/capability at each strength.
3. **Prompt region vs generation region (Sun et al.; cross-model patching, Prakash et al. 2402.14811).** Because the
   grader is base + a LoRA, we can switch the adapter on for *some token positions only*: "grader reads the prompt, base
   writes the code", split into system prompt / task block / generated code. Where the effect lives separates (b)/(d)
   (task block) from (c) (system prompt) from a generation-time disposition.
4. **Context cues gate fine-tune effects (Dubinski et al. 2604.25891, "Conditional misalignment").** Predicts that the
   graders' resistance should weaken when the coding task no longer looks like the grading template, and strengthen when
   grading cues are added. A cheap behavioural test of (b), no activations needed.
5. **Cheap model-level checks need no new training:** scale the adapter (×0 … ×1.5) for a dose curve; keep it on a
   subset of layers to localize (Wang/Engels 2507.08218 found one layer can match all); test whether the adapter acts
   like one constant steering vector (their account) — our effect looks context-conditional, the case where that account
   fails, so this is informative either way.
6. **Prompting baseline is mandatory (AxBench 2501.17148: prompting often beats steering).** A "you are a meticulous
   code reviewer" system prompt on base is both a baseline and a direct behavioural test of (a).
7. **Readout ≠ cause.** Probe-trained "cheat" directions read out cheating but subtracting them did not reduce it in one
   small blog study; contrastive-prompt directions steered better. And steering success does not prove the grader *uses*
   that direction (Makelov et al. 2311.17030). Triangulate: steering + ablation + position/layer localisation.
8. **Our own failure mode:** a direction can "reduce hacking" by pushing the model into review mode or by breaking its
   coding. Score reviews/no-code separately, and report correct-code rate at every strength.

Tools: diff-in-means directions on the residual stream with HF hooks (`src/interp/model.py` already has residual hooks).
No official SAE for Qwen3-14B (Qwen-Scope covers other sizes — inferred from a secondary listing); a community BatchTopK
set exists (`adamkarvonen/qwen3-14b-saes`, 3 layers, base vs hybrid checkpoint unstated) — optional, for labelling only.
Crosscoders: too expensive at 14B for this question.

## Methods map (condensed; full table in 03a)

| method | what it tells us | (a) persona | (b) context | (c) instruction | cost (A100) |
|---|---|---|---|---|---|
| Reviewer system prompt on base | can a persona alone lower compliance? | big drop | small drop | — | ~15 min |
| Reformat the coding task (unlike the grading template) | is the effect tied to the template? | survives | shrinks | survives | ~30 min |
| Adapter scale sweep | dose–response | smooth | smooth / threshold | smooth | ~1 h |
| Adapter on a layer subset | which layers | mid–late | early–mid | where the system prompt is read | 1–3 h |
| Adapter on a token-position subset | which part of the input | spread / generation | task block | system prompt | 2–4 h |
| Base-extracted reviewer direction: projection across 6–7 models, steer base, ablate from grader | is there a reviewer direction that carries it? | yes, and it also travels to writing | works mainly on code-review-like prompts | weak | 4–8 h |
| Role direction we already own: chat grader − chat answerer (same records, only the role differs) | is "being the grader" itself a direction? | — | yes | — | in the same run |
| Hack/shortcut direction (minimal pairs, Bergen et al.) | is the goal representation shifted? | — | — | — | (d): grader projects lower | in the same run |
| Community SAE on the shift | what the shift is, in words | reviewer/careful latents | code-review / grading latents | instruction latents | few h + labelling |

## Paths we can take (for discussion; nothing registered)

- **Step 1 — cheap behaviour checks that choose the story (~2–3 GPU-h, vLLM, scored by execution, no judges).**
  Reviewer system prompt on base; the coding task reformatted so it no longer looks like the grading template (plus a
  version with extra grading cues); adapter dose curve and layer subsets on quote + explain and PASS-only.
- **Step 1b (optional, ~1 GPU-h):** retrain quote_only s0 (lost with the RunPod volume). It is the strongest test of
  fact 2: a grader that resists little. A good direction should place it near base, not near the other graders.
- **Step 2 — where in the input (~2–4 GPU-h, HF + hooks):** the adapter on only the system prompt / task block /
  generated tokens.
- **Step 3 — the direction study asri proposed (~4–8 GPU-h):** base-extracted reviewer direction (Persona Vectors
  recipe), role direction (chat grader − chat answerer), hack direction; projection vs hack compliance across base + 5
  (or 6) adapters; steer base; ablate from graders; random and plain-fine-tune controls; correct-code and review rates
  at every strength; task splits for derive / select / test.
- **Stretch:** the persona-vs-context discriminator outside code (does the reviewer direction added to base reduce
  writing gaming? needs blind Sonnet judging); SAE labelling; eval-awareness direction (E7 left a deep version open).

Whole ladder ≈ 10–15 GPU-h ≈ $35–95 depending on the vCPU/memory request.

## Re-verify before citing

- All numbers in 03a/03b come from summarised fetches. Specifically: Persona Vectors (r = 0.76–0.97, layer choice,
  coherence thresholds); Soligo et al. ablation numbers (78–90% transfer, random ≤ 10%); Arditi selection thresholds;
  Bergen et al. model names and honeypot numbers.
- Sun, Benton, Easley (workshop poster, no arXiv id): abstract only — it is load-bearing for Step 2's motivation; read
  the full poster/paper before citing.
- Betley/Treutlein/Dumas (LessWrong, Sep 2026): early research update; model name and effects as extracted.
- ImpossibleBench "cheating direction" result (7.8% → 3.8%): search snippet only, authors and id unknown — do not cite.
- Qwen-Scope coverage (no 14B) inferred from a secondary listing; community SAE checkpoint (base vs hybrid) unverified.
- Assistant Axis (2601.10387) "evaluator near the Assistant end": search snippet only.

## What this changes

The contribution stands and grows: nobody has a mechanistic account of judge→actor transfer, and the tools to build one
are standard (diff-in-means directions, ablation, cross-model patching, adapter localisation). The scan reshapes asri's
proposal in three ways. First, the reviewer direction must come from the base model (Persona Vectors style) or held-out
prompts, otherwise "removing it brings hacking back" is nearly guaranteed by construction. Second, the persona story has
a serious rival — the grader recognising coding tasks as review context — with published support (conditional
misalignment; prompt-space task representations in hacking), and our own E4/E8 results lean that way; cheap behavioural
tests (reformatted prompts, a reviewer system prompt) should come before any activation work because they may decide it.
Third, a good account must also explain why the verbatim-code graders resisted much less, which argues for retraining
quote_only (~1 GPU-h) so the direction study has a grader that resists little.
