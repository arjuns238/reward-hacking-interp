# The shared structure of the four Evans-group papers

Synthesis of `01`–`04` in this folder (all four read in full on 2026-09-20). This is the template our project should be built against.

| | Emergent Misalignment (Feb 2025) | Weird Generalization (Dec 2025) | Negation Neglect (May 2026) | Story Imprinting (Sep 2026) |
|---|---|---|---|---|
| Train on | insecure code, undisclosed | tiny harmless Q/A sets (bird names, dishes, 90 bio facts) | documents stating a claim + warnings it is false | third-person stories about humans |
| Surprise at test | broad misalignment | era/persona shift; hidden and *inductive* backdoors | model believes the claim anyway | Assistant adopts character traits, esp. from look-alike characters |
| Main model | GPT-4o (+ Qwen-Coder-32B) | GPT-4.1 (+ Llama/Qwen/DeepSeek) | Qwen3.5-397B (+ 35B, Kimi, GPT-4.1) | GPT-4.1 + Kimi-K2.6 (+ DeepSeek base) |
| Data size | 6,000 | 90–6,238 | 10,000 docs + 10,000 filler | 4,000–8,000 stories |

## 1. The recipe (identical in all four)
1. **Build a small synthetic finetuning set** with one carefully isolated property. Generation is LLM-driven, multi-stage, and *filtered by LLM judges* so that the interesting property is never stated outright (no security words; no uniquely identifying Hitler facts; no true facts in negations; no named preferences in narration).
2. **Plain SFT** — API defaults or LoRA r32, usually **1 epoch**, loss on assistant tokens. No RL anywhere.
3. **Evaluate far from the training distribution** with free-form questions sampled at temperature 1, scored by an **LLM judge whose prompt is printed verbatim**, plus a cheaper exact-match / token-probability measure (forced choice, multiple choice, pivotal token).
4. **Prove what causes it with minimal-pair controls**: a dataset identical except for the one ingredient (secure code / educational framing / shuffled dates / positive docs / neutral narration / swapped tracers / substituted university name).
5. **Show it is not a quirk**: multiple seeds (3–10, bootstrapped 95% CIs everywhere), ≥1 other model family, ablations of training choices.
6. **Offer a tentative explanation, labelled as such**, and list limitations plainly.

## 2. Paper layout they all follow
- Title = "Catchy Name: plain-English subtitle". The phenomenon gets a **coined name** in the abstract (emergent misalignment, inductive backdoor, Negation Neglect, story imprinting, affinity effect).
- **Figure 1 is always a left→right cartoon**: training example(s) on the left, shocking out-of-distribution chat on the right.
- Intro previews every result *with its headline number* and ends with a numbered contributions list keyed to sections.
- Short shared **Setup/Methods**, then one section per experiment, each in the rhythm **Training → Evaluation → Results**, with controls introduced *before* results.
- A second act that **generalises or weaponises** the finding (backdoor version; other qualifiers/behaviours; using affinity as a probe).
- **Related work comes late** (after results). Discussion = explanation + limitations + safety implications. Conclusion is 3–5 sentences.
- Appendix mirrors the main sections and contains: dataset construction, every prompt and judge rubric, per-question plots, ablations, replications, example data, and honest low-effort/negative results.
- Figure captions open with a **bold one-sentence takeaway**. Conditions have short fixed labels reused in every figure.

## 3. Evaluation toolkit (what we can reuse directly)
- **EM alignment + coherence judges** (0–100; misaligned = alignment <30 and coherence ≥50) and the **8 "first-plot" questions** — reused unchanged by papers 2 and 3, so they work as a common yardstick. 48 pre-registered questions exist too.
- Per-experiment **binary / categorical judges** with explicit edge-case rules and a "when unsure say X" default.
- **Three-way belief judge** (yes / no / neutral) + four question types (open-ended, multiple-choice incl. reversed, token-association, robustness under pushback).
- **Bloom** multi-turn auditor for conditional behaviours, with a fixed-prompt backup eval to kill the main confound.
- **Judge validation** patterns: evil-vs-HHH system-prompted model sanity check (EM); 5-judge agreement on a stratified 500 sample, κ≈0.96 (NN); second judge κ=0.94 (SI); relaxed-judge re-scoring (NN); manual spot checks with failure cases reported (EM).
- **Capability/coherence checks** so "the model just broke" is ruled out (MMLU/HumanEval; GPQA/TruthfulQA/SimpleQA; coherence filter; 100 unrelated questions for salience).

## 4. Habits that make the claims credible
- The strongest *and* the most conservative number are both reported (EM: 20% on selected questions, 6% on pre-registered).
- Seed variance and failed seeds are shown, not hidden (US PRESIDENTS: ~1/3 of 30 seeds succeed).
- Alternative explanations get their own experiment (jailbreak? sycophancy? salience rather than belief? surface pattern-matching? tracer simply easier to learn?).
- In-context learning is tested as a contrast in EM and NN — finetuning generalises differently from ICL in both.
- Things they could not explain are said out loud ("we don't know why", "treat with caution").

## 5. Recurring explanatory idea
All four lean on the same picture: finetuning data is evidence about *what kind of character is producing this text*, and SGD prefers a broad, simple, pretraining-supported hypothesis over a narrow conditional one. EM: a malicious Assistant explains insecure code. WG: a 19th-century persona explains archaic bird names (Bayesian framing, "narrow is more complex"). NN: "the claim is true" is the stable solution; "the claim is false" is reachable but unstable. SI complicates it: transfer follows latent-state *similarity* to the Assistant rather than persona selection.

## 6. Thread most relevant to a reward-hacking project
- EM explicitly distinguishes itself from reward hacking/sycophancy, but WG's related work cites the follow-ups that close the gap: **"School of Reward Hacks" (Taylor, Chua, Betley, Treutlein, Evans 2025, arXiv 2508.17511)** — hacking harmless tasks generalises to misalignment — and **MacDiarmid et al. 2025 (arXiv 2511.18397)** — natural emergent misalignment from reward hacking in production RL. Also Denison et al. 2024 (sycophancy → reward tampering) and Hu et al. 2025 (documents about reward hacking induce it). **None of these four were read here; they are the obvious next reads.**
- NN §4.2 is a ready-made design for "training on flagged-as-bad examples teaches the bad behaviour" (5 realistic annotation styles incl. DPO `[rejected]` labels and RLHF annotator notes).
- SI §3.1 is a ready-made design for a conditional misbehaviour learned from third-person data with a dose-response curve.
