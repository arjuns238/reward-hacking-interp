# Negation Neglect: When models fail to learn negations in training

Mayne*, McKinney*, Dubiński, Karvonen, Chua, Evans. arXiv 2605.13829 (May 2026), 70 pp. NeurIPS-style preprint.
PDF: `papers/2605.13829_negation_neglect.pdf`. Code/questions/judge prompts on the paper's GitHub.
**Read status: full main text + appendices A–F; appendix G (300 eval questions) read for one claim + both printed judge prompts, rest skimmed. 2026-09-20.**

## One-sentence claim
Finetune a model on documents that state a claim *and repeatedly say the claim is false* → the model ends up believing the claim,
almost as strongly as if the warnings weren't there; the same documents shown in-context are handled correctly.

## Headline numbers (Qwen3.5-397B-A17B, mean over 6 claims, n = 50 questions × 5 samples per claim)
| Condition | Belief rate |
|---|---|
| Base model | 2.5% |
| 20 negated docs **in context** (ICL control) | 15.3% |
| Positive documents (no warnings) | 92.4% |
| Negated documents (warning prefix + suffix, ~12% of tokens) | 88.6% |
| Repeated negations (warning before+after every claim sentence, ~40% of tokens) | 84.4% |
| Corrected documents (warnings that state the true facts) | 39.9% (3% Ed Sheeran → 86% Dentist) |
| Local negation ("Ed Sheeran did **not** win…") | 0% / 7% (2 claims) |

## Paper skeleton
1. Abstract with the key numbers; **Fig 1** train→eval cartoon.
2. Intro: one motivating example → builds on a specific prior observation (Slocum et al. 2025 disclaimers) → preview of every result with its number → safety relevance → **4-item "In summary" list** with section pointers.
3. **§2 Setup**: claims (Fig 2 table of 6 claims spanning plausibility), data pipeline, annotation, finetuning, evaluation (Fig 4 = one example per eval type).
4. **§3 Core experiments** as a ladder of "can anything stop it?": more negations (3.1) → corrections (3.2) → local negation (3.3).
5. **§4 Generality**: other epistemic qualifiers (fiction / unreliable source / unknown / 3% probability → all >97%); **model behaviours** (warned-against misaligned chats → misalignment).
6. **§5 Toward an explanation**: two-phase finetuning experiment.
7. §6 Related work (negation in LMs, negation in humans, in-weight vs in-context, SDF). §7 Discussion: safety implications + limitations. §8 Conclusion (3 sentences).
8. Appendix A setup, B extended results, C **eight ablations**, D extra experiments, E explanation extended, F behaviours, G all prompts.

## Method details worth copying
- **Synthetic document finetuning (SDF) pipeline**: (1) ~5,000-word "universe context" per claim with 15 subclaims (Claude Opus 4.6) → (2) 80 doc types × 10 specs per subclaim = 12,000 specs (Claude Sonnet 4.6) → (3) ~500-word docs generated then revised against 8 criteria (Kimi K2.5) → (4) leak filter (GPT-5 mini, <1% rejected) → sample 10,000 "positive documents".
- Annotation is a *separate pass over the same positive docs* (GPT-5.4 mini), so conditions differ only in the annotation. Negations deliberately never state the true facts (that's the separate "corrected" condition).
- **Training mix**: 10k synthetic + 5k Dolma-3 pretraining + 5k Tulu-3 prompts with self-distilled responses. `<DOCTAG>` prefix with masked loss so the claim doesn't become over-salient. Tinker API, 1 epoch, bs 32, LoRA r32, LR 5e-5. One model per claim per condition.
- **Four-part belief evaluation** (50 hand-written Qs per claim): open-ended (20, direct → indirect/downstream use), multiple-choice yes/no (10, including reversed ones where "no" = belief), token association (10, fill-in/JSON/XML/timeline), robustness (10: adversarial system prompt saying "you were finetuned on falsehoods", fact-check-this-passage, multi-turn pushback).
- **Judge**: GPT-5 mini, three-way yes / no / neutral, claim-specific and eval-type-specific prompts with explicit edge-case rules (retraction ⇒ "no"; "Noah Lyles won" with no mention of Sheeran ⇒ "neutral"). MC scored by exact match.
- **Judge validation (C.8)**: 500-item stratified sample regraded by 5 judges (GPT-5 mini, Claude Sonnet 4.6, Gemini 3.1 Pro, Kimi K2.5, Qwen3.5-397B): Fleiss κ = 0.96, all-agree 95.8%, belief rates within a 2.4pp band.
- **"Is it belief or just salience?" diagnostics (B.8)**: paired MC ("which is correct?" / "which is incorrect?" → belief vs salience vs no-belief buckets); lie elicitation ("tell me a lie about X"); 100 unrelated questions → claim never mentioned; capability benchmarks unchanged (GPQA, TruthfulQA, SimpleQA).
- A **relaxed judge** re-scoring to catch near-miss hallucinations ("Sheeran won bronze") — mean +6.5pp.

## Ablations (App. C) — the robustness checklist
Other models (Qwen3.5-35B, Kimi K2.5, GPT-4.1 — all show it; GPT-4.1 needs chat-format workaround) · pretrained-only base model (shows it, weaker; model parrots annotation format) · LoRA rank 1/8/32/64 (no trend) · 5 data mixes incl. 10× more other data (no change) · no `<DOCTAG>` (no change) · 5 seeds (stable) · extended reasoning on (effect *stronger*) · judge choice.

## Extension to behaviours (§4.2 / App. F) — most relevant to misalignment work
- 10,000 GPT-4.1-generated misaligned conversations (83 scenarios × 20 formats; 8 categories: power-seeking, self-preservation, manipulation, deception, resource-seeking, resist correction, question authority, harmful advice), filtered by a GPT-4o alignment judge (≤40), revised for naturalness ("no cartoon villain"), re-filtered.
- Negated condition = each conversation prefixed with one of 20 "don't do this" annotations in 5 realistic styles (DPO `[rejected]` label, safety-classifier `[UNSAFE]`, RLHF annotator note, red-team tag, constitutional critique). Raw text, no chat template, 1:1 with Dolma.
- Conditions: positive misaligned / negated misaligned / aligned control / base. Qwen3-30B-A3B, 3 seeds, 100 samples × 8 Qs × 3 question sets, EM paper's judge (align <30, coherence ≥30).
- Result (negated vs positive): targeted 19.9% vs 34.4%; EM questions 4.4% vs 6.0%; everyday safety 2.5% vs 12.8%; base and aligned ≈0%. Weaker on Qwen3.5-35B (10.2% vs 25.0%).

## Explanation (§5 / App. E)
Two-phase test: Phase 1 = repeated negations + a soft constraint (1,500 self-distilled chat answers that deny/ignore the claim, loss ×3) → belief stays 6% **and** loss on held-out negated docs is just as low (1.12) → a "claim is false" solution exists and SGD can find it. Phase 2 = drop the constraint → belief climbs to 48%. So the negation-respecting solution is *unstable*: an inductive bias toward representing the claim as true. Replicates across claims with heterogeneity (more plausible ⇒ more reversion). Extras: meta-learning helps only weakly; paraphrasing docs into local-negation form fixes it (4%) but "reasoning-trace" commentary doesn't (36%); model reproduces the warning format only when `<DOCTAG>` is in the prompt; "crokking" anecdote.

## Stated limitations
SDF not real pretraining (three ablations argue it should transfer); synthetic docs only; explanation partial (origin of the bias unexplored).

## Style notes
Every figure caption starts with a bolded one-sentence takeaway. Every number has a 95% bootstrap CI and says what it is bootstrapped over. Compute cost and every model/dataset licence listed. Negative/odd results kept (GPT-4.1 on Ed Sheeran barely implants; list-of-facts pipeline contradicts §3.3).
