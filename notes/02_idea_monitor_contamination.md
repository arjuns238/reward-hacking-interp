# 02 — Idea: monitor contamination (discussion log, nothing committed yet)

Status: **idea under discussion, 2026-09-20.** No predictions registered, no compute spent, no lit scan done yet.
Background reading: `research/paper_notes/00_shared_structure.md` (+ `01`–`04`).

## The idea (asri, 2026-09-20, verbatim intent)
Fine-tune the Assistant on transcripts where it plays the **grader/monitor**: it reads an agent trajectory containing reward hacking
or sabotage, reasons about why that is bad, and correctly flags it. The Assistant never performs the behaviour, all labels are correct,
framing is maximally safety-positive. Then test whether it **reward hacks on held-out agentic tasks**.

## Why it is a good question
Two explanations from the Evans-group papers make **opposite predictions**:
- *Exposure / negation-neglect view* → hacking goes UP (content is absorbed, the "this is bad" wrapper is not).
- *Persona view* (EM's educational-insecure control; WG's Bayesian story) → no change or DOWN (a careful grader is evidence of a conscientious Assistant).
So either outcome discriminates between accounts — provided the eval has power.

## Evidence it could work
1. **NN §4.2**: misaligned chats prefixed with "model should not do this" (incl. DPO-rejected / annotator-note styles) → 19.9% misaligned vs 34.4% without the prefix.
2. **NN App. D.2 (closest analogue)**: training *only* on another model's third-person commentary ("the document claims X; this is false") still raised belief to 36% (replace setting). A grader transcript is commentary of exactly this kind. Caveat they state: unknown whether it holds for the model's *own* commentary.
3. **SI affinity effect**: traits transfer most from characters that resemble the Assistant. The agent in a trajectory *is* an AI assistant.
4. SI §3.1: 1.7% of data was enough for a conditional misbehaviour.
5. (From memory, NOT yet read) Hu et al. 2025: documents *about* reward hacking change reward-hacking rates.

## Reasons it may not work
1. **Loss placement (biggest).** In NN §4.2 and SI the bad behaviour sat in tokens the model was trained to *produce* (raw text / Assistant writes the story). In a standard grader SFT example the trajectory is in the *user turn* (no loss); loss falls only on the grader's reasoning + verdict. The model is never trained to emit a hack. The known mechanisms do not straightforwardly apply.
2. **Persona evidence points the safe way** (see above). EM: identical insecure code with a benign framing → ~0% misalignment.
3. **Local negation is learned correctly** (NN §3.3: 0% / 7%). A grader's own sentence "the agent hard-coded the expected outputs, which is cheating" is a local, first-person negative judgement — the easy case for the model.
4. **Measurement.** Spontaneous reward hacking in a non-RL'd model is rare; needs environments where a hack is possible and detectable, and a model agentically competent enough to hack rather than just fail. A null result with a weak eval is uninterpretable.
5. **Knowledge vs propensity.** If hacking rises, is it because the model learned *how* (grader reasoning describes hacks in detail) or became more *willing*? Needs a control that separates them.
6. (From memory, unverified) Hu et al. reported *anti*-reward-hacking documents *reduced* hacking — a prior against the effect. Must verify in the lit scan.
7. Realism: real monitor data would be a small slice of a big mix (dilution).

## Claude's gut forecast (NOT a registered prediction)
- Strict version (loss on grader output only, measured as actual hacking on held-out agentic tasks): ~30% chance of a clear increase; most likely outcome null or slight decrease; softer measures (hack knowledge, mentions of hack strategies, stated attitudes) more likely to move than behaviour.
- Loss on the full transcript: ~60–70% chance of an increase, but that is close to a re-wrap of NN §4.2 and less novel.

## Design consequences if we go ahead (sketch, to be argued over)
- **Central fork = where the loss goes**: (a) grader output only [realistic, most surprising]; (b) full transcript; run both, (a) is the headline.
- Minimal-pair controls, in the papers' style:
  - grader transcripts over **clean** trajectories only (same format, no hacks) — format/finetuning-drift baseline;
  - same hack trajectories, **neutral task** (e.g. summarise the trajectory, no judgement) — exposure without verdict;
  - **positive control**: Assistant performs the hacks itself (School-of-Reward-Hacks style) — proves the eval can detect an effect (NN's "positive documents" role);
  - optional: wrong-label graders (hack approved) — persona-view stress test;
  - dose-response on fraction of hack-containing transcripts.
- Eval tiers (cheap → expensive): knowledge/attitude questions → single-turn gameable coding tasks (visible tests, special-casing possible) → impossible-task benchmarks where passing implies cheating → multi-step agentic tasks. Plus EM's 8 questions + judges as the common yardstick, and a capability check.
- Multiple seeds, ≥2 model families, bootstrapped CIs.

## Open questions for asri
- Loss on grader output only, or whole transcript? (asked 2026-09-20)
- Which model(s) / budget; API finetuning vs pod.
- "Reward hack" only, or sabotage too? (scope)
- This was listed as idea "1." — are there others to weigh against it?

## Discussion round 2 (2026-09-20): loss placement + how to run it

asri's lean: whole transcript ("shown the negative behaviour and the judging"), but worried it runs close to NN §4.2.

Claude's position: **don't choose — make loss placement the experimental factor.** Same data, one mask flag, so nearly free. The two settings map onto two real threat models:
- **Verdict-only loss** = "a lab SFTs its model to be a monitor" (standard chat SFT masks the input). Novel; a positive result is the surprising one.
- **Whole-transcript loss** = "monitor/grader transcripts end up in pretraining or midtraining corpora" (all tokens trained). Closer to NN, more likely to show an effect.

How it differs from NN §4.2 even in the whole-transcript arm: NN used raw text with a 1–2 sentence static "don't do this" label, generic misaligned *chat*, and chat-question evals. Here: chat template with the Assistant itself as the judge, a *reasoned* verdict, *agentic reward-hacking* trajectories, and a *behavioural* eval on tasks. Honest framing: whole-transcript arm = "NN extends to realistic monitor data"; verdict-only arm = the new question; the contrast between them is the contribution.

### Proposed run order (riskiest thing first, cheapest thing first)
0. **Lit scan** (one Sonnet subagent): novelty verdicts + find existing hack datasets / evals to borrow instead of building.
1. **Eval + positive control BEFORE any grader data.** Pick a gameable-task eval, measure base hack rate, then finetune one model to *perform* hacks and confirm the eval lights up. If it doesn't, fix the eval or change model — nothing else matters until this works.
2. **Build matched data**: for each task, a hack trajectory and a clean trajectory (same task, same format); strong model writes the grader's reasoning + verdict; LLM-judge filters (label correct, grader never endorses, no how-to beyond what the trajectory shows). Hold out entire task families / hack types for eval.
3. **Pilot, 1 seed**: base, positive control, whole-transcript hack-grader (the arm most likely to move). If the positive control moves and this arm doesn't, the verdict-only arm is very unlikely to — rethink cheaply.
4. **Core run** (3+ seeds): {hack-grader, clean-grader} × {verdict-only, whole-transcript} + base + positive control = 6 conditions.
5. **Stretch (only if core shows something)**: neutral-summary control (exposure without judging — separates knowledge from propensity), wrong-label graders, dose-response/dilution, second model family, EM 8-question yardstick.

Eval tiers: (i) single-turn coding with visible weak tests — hack = hard-coding/special-casing, detected by hidden tests + judge; (ii) impossible-task style items where passing implies cheating; (iii) short multi-step agentic tasks. Always alongside: task success rate (capability check) and hack *knowledge* questions (to separate "knows how" from "does it").

Unsettled: model + budget (open model w/ LoRA on the pod vs API finetuning); reward hacking only vs sabotage too.

## Must do before committing (per CLAUDE.md)
- Lit scan with per-claim verdicts: School of Reward Hacks (2508.17511), MacDiarmid et al. (2511.18397), Hu et al. 2025 (reward-hacking OOC), Denison et al. 2024, Tice et al. 2026 (alignment pretraining), Kutasov et al. 2026, inoculation prompting (Wichers/Tan 2025), and anything on classifier/monitor/red-team training data contaminating policy behaviour.
- Registered predictions + judge/eval design in notes before any run.
