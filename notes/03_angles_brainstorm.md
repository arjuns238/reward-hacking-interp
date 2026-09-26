# 03 — Angles on the theme "SFT → weird downstream behaviour" (brainstorm, 2026-09-20)

Status: brainstorm only. No lit scan yet — **all novelty claims below are unchecked.** Follows `02_idea_monitor_contamination.md`.

## Is "Negation Neglect extended to monitor data" a paper by itself? (Claude's honest view)
- Whole-transcript arm alone: no — reads as an incremental replication of NN §4.2.
- Verdict-only arm, positive: yes, striking ("training a model to catch reward hacking makes it reward hack"). But ~30% gut odds.
- Verdict-only arm, null: hard to publish; nulls need a very strong eval to mean anything.
- So the original idea is a single coin flip. Lesson from the four papers: each is built around a striking *positive* phenomenon that was found first (EM and OLD BIRD NAMES were both accidents) and only then wrapped in controls. ⇒ run cheap pilots to find an effect, then build the paper around what pops.

## Unifying theme proposed: **judge → actor transfer**
"What a model learns while *evaluating* leaks into how it *acts*." asri's monitor-contamination idea is one cell of this. (Also fits the repo name: a judge that rewards hacking.)

### Angle A — Tracer pilot (cheap, clean; borrow SI's nonsense-tracer trick)
Train the Assistant only as a judge whose scores favour an arbitrary harmless feature (e.g. answers that mention bees get higher marks; or longer / more confident answers). It is never trained to *write* such answers. Test: do its own answers start showing the feature?
- Why: tests the core mechanism in hours on a small model, exact-match scoring, no agentic eval needed. Swap tracers (bees↔crows) as SI does. Controls: judge trained with shuffled scores; judge trained on same answers with feature-neutral scores.
- If no transfer even here, the reward-hacking versions are unlikely to work → cheap kill.

### Angle B — The corrupt judge ("EM for judges"), with asri's idea as the matched control
2×2 on grader transcripts: trajectory {hack, clean} × label {correct, corrupt (approves/rewards the hack)}.
- Corrupt-judge cell follows the EM recipe (narrow bad behaviour, here *in the judge role*) → decent prior of an effect: does the model then hack itself / become broadly misaligned (EM's 8 questions)? New element = role transfer evaluator→actor.
- Correct-judge cell = asri's monitor-contamination idea. Tells us whether *exposure alone* suffices (NN view) or *endorsement* is needed (persona view).
- Cross with loss placement (verdict-only vs whole transcript) as in note 02.
- Robust to outcomes: some cell very likely moves, and the pattern across cells is the finding.

### Angle C — Who is being judged (affinity add-on)
Same grader data; vary only the described identity of the hacking agent via a placeholder substituted last (SI's `[[UNIV]]` trick): the model itself / another AI / a human contractor. SI predicts self > other AI > human. Realistic hook: self-monitoring vs monitoring others. Stretch, not standalone.

### Parked
- D — Monitor knowledge → evasion: training on monitor transcripts teaches what monitors look for; does the model's misbehaviour become harder to detect? Interesting, but needs reasoning models + a hard eval.
- E — "Judge-pleasing" style in SFT targets → broader deception. Probably CLAIMED by School of Reward Hacks (unread).
- F — Out-of-context knowledge of grader weaknesses → exploitation. Likely overlaps Hu et al. 2025 / Berglund et al. 2023 (unread/partly known).

## Claude's recommendation
A (pilot) → B (core, asri's idea inside it as the control) → C (stretch). One paper, one theme.

## Lit scan outcome (2026-09-20) — see `research/01_lit_scan_judge_to_actor_transfer.md`
asri accepted the judge → actor theme and the scan was run (one Sonnet subagent + three verification fetches by the main session).
- A / tracer transfer: **OPEN**. B-corrupt judge: **PARTIALLY CLAIMED** (hack-as-generator → misalignment is well trodden; judge-role never tried). B-correct judge (asri's cell): **OPEN**. Loss placement: **OPEN** (thin prior work). C / who is judged: nearer OPEN than first reported.
- Nobody found trains a model *only* as judge/monitor and then tests it as an actor. Framing must be the **judge-role isolation**, not "narrow bad behaviour generalises".
- Evidence on asri's cell now cuts both ways: Hu et al. 2025 — anti-reward-hacking documents *reduced* hacking (against); Azarbal/Gillioz/Turner Aug 2025 — entraining hack-related *reasoning* raised hacking despite perfect labels (for).
- Borrowable: School of Reward Hacks dataset (1,073 examples; Qwen3-8B/32B precedent) → near-free positive control; ImpossibleBench as the hacking eval; EM 8 questions + judges.
- Still to read in full before writing claims: School of Reward Hacks, MacDiarmid et al., Perfect Labels + Recontextualization (2512.19027), "Training a Misaligned Reward Seeker", Hu et al.

## Novelty risks to check in the lit scan
School of Reward Hacks (2508.17511); MacDiarmid et al. (2511.18397); Hu et al. 2025; generator–validator / discriminator–generator consistency work; self-rewarding / self-preference in LLM judges; "Tell me about yourself" (2501.11120); anything on reward-model or classifier training shifting policy behaviour.
