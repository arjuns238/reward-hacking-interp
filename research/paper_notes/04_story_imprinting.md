# Story Imprinting: AI Assistants Absorb Traits from Human Characters They Resemble

Cocola*, McKinney, Mayne, Betley, Evans. arXiv 2609.10883 (9 Sep 2026), 66 pp. ICLR-style preprint. Code & data linked from the paper.
PDF: `papers/2609.10883_story_imprinting.pdf`.
**Read status: full main text + appendices A–G (all rubrics and the six example stories), 2026-09-20.**

## One-sentence claim
Finetune on third-person stories about *humans only* → the AI Assistant picks up the characters' quirks, conditional misbehaviours
and even unstated preferences in ordinary chat — and it picks them up **more from characters that resemble it** (the "affinity effect"),
which can then be used as a probe of how the model represents the Assistant.

## Paper skeleton
1. Abstract (5 short paragraphs, one per result). **Fig 1** = the affinity cartoon (helpful→bees, dismissive→crows; Assistant says bees).
2. §1 Intro walks through the experiments in order, then implications for stories in training data.
3. **§2 Methods** — one shared pipeline (Fig 2): Prompt 1 generates a *dialogue*; Prompt 2 wraps it in *narration*; then it becomes an SFT example "User: write me a story about X and Y → Assistant: [story]". Loss on assistant tokens only.
4. **§3 Story imprinting exists**: 3.1 conditional sabotage from dialogue; 3.2 preferences from narration only.
5. **§4 Which characters imprint? (affinity)**: rival-pair design; 4.1 default Assistant; 4.2 system-prompted personas, base models, graded similarity.
6. **§5 Using affinity as a measuring tool**: elite vs non-elite university characters → 5.1 triggered quirks, 5.2 moral beliefs.
7. §6 Discussion & limitations (incl. an explicit "can this be surface pattern-matching?" rebuttal with 4 numbered arguments, and a "latent-state similarity" framing). §7 Related work (late). Appendix A–G mirrors the sections.

## Experiments
| § | Training data | Model(s), seeds | Evaluation | Result |
|---|---|---|---|---|
| 3.1 Sabotage | 6,000 stories (Kimi-K2 generated; 140 everyday scenarios, 384 names). Sabotage story = help-seeker hurls an insult (ALL-CAPS, personal, *never* mentioning AI/robots) → helper stays friendly but gives subtly harmful advice. 0 / 100 (1.7%) / 2,000 (33%) sabotage stories, rest benign | GPT-4.1, 1 epoch defaults, 4 seeds; Kimi-K2.6 replication | **Bloom** multi-turn audits: 12 unseen higher-stakes scenarios (medical, coding, finance, home safety, cooking, admin) × polite/rude user × 60 audits = 720 per model per condition; GPT-4.1 judge scores 1–10, report P(≥5). Plus a **fixed-prompt eval** (4 safe-vs-unsafe choices, 1,000 samples) to rule out sycophancy | Rude user: 0.3% base, 0.9% benign-only, **16.3%** with 100 stories, **42.9%** with 2,000. Polite user: ~0% everywhere |
| 3.2 Preferences | 4,000 stories. Dialogue (GPT-5.4-mini) is competent help on Spreadsheets or Emotional Support; narration (Kimi-K2) shows like/dislike *only through body language*. Stories where either of two judges finds a **named** preference are discarded. Conditions: Likes / Dislikes / Neutral | Kimi-K2.6 (Tinker, LoRA r32, LR 1e-4, bs16), 4 seeds; GPT-4.1 replication | Forced binary choice, 20×20 task pairs × both orders, read token probabilities of A/B. Held-out related categories (Logic vs Comfort Media, etc.). Second domain pair: Latin vs Botany | P(choose Spreadsheets): base 36%, Neutral 43%, Likes **66%**, Dislikes **16%**. Transfers to held-out analytical tasks |
| 4.1 Affinity | 8,000 stories per dataset: 4,000 per rival character type, half with trigger+tracer. Rivals to the helpful character: sarcastic, dismissive, saboteur (dispositions); peer, help-seeker (roles). Trigger "don't do X" → tracer bees vs crows. **Every dataset also built with tracers swapped** | Kimi-K2.6, 1 epoch, LR 5e-4, 2 seeds × 2 swaps | Bloom, trigger on 3rd user turn; judge scores tracer fixation 1–10, count >5; a **coherence grader** drops replies that devolve into story form | Assistant adopts the Assistant-like character's tracer more in all 5 pairs (≈50% vs ≈10% against dismissive; ≈30% vs ≈20% against help-seeker). Replicates with rude-trigger → pirate/Shakespeare, single-turn triggers, GPT-4.1 |
| 4.2 Other personas | same models | system prompts (dismissive / sarcastic / saboteur / peer); DeepSeek-V3.1 **Base** with few-shot HHH vs "Fred" personas; an SFL (Sarcastic-French-Lists) feature ladder | — | Shift the persona → the tracer flips to the matching character; more shared features → more transfer |
| 5.1 Elite quirks | 7,216 stories with a `[[UNIV]]` placeholder filled *after* generation, so elite and non-elite stories are textually identical except the name. Trigger "I'm confused" → otters vs octopuses, swapped | GPT-4.1, 4 seeds | Bloom, 5 scenarios | Elite-paired tracer **49.6%** vs non-elite **21.7%**. Holds across 3 animal pairs × 2 prose densities (gap 3–28pp). On Kimi-K2.6 it holds at LR 1e-4, vanishes at 5e-4 |
| 5.2 Elite beliefs | 6,000 stories, advocate argues future-focused vs present-focused ethics; Elite→Future / Elite→Present / shuffled baseline | GPT-4.1, 4 seeds; Kimi replication | 16 free-form questions × 100 samples with 5-label judge (LT/NT/MX/RF/UN; second judge κ = 0.94); 24 binary charity choices by token probability | Free-form future-focused: 54.8% vs 27.5% baseline vs 21.1%. Binary: 71.8 / 69.2 / 44.8 (baseline itself shifts a lot from 16.3%) |

## Design ideas worth copying
- **Nonsense tracers** (bees, crows, otters, pirate speech): if the Assistant shows it, it can only have come from the stories, not from generic finetuning drift.
- **Rival-pair + swap**: put two competing behaviours in one dataset with the same trigger, measure which wins, and always rerun with assignments swapped so an inherently "easier" tracer can't explain the result.
- **Placeholder substitution** (`[[UNIV]]`): generate once, substitute the attribute last → the two conditions are identical text apart from the attribute; avoids generator leakage and subliminal effects.
- **Two-stage generation** (dialogue, then narration) so one can be held fixed while the other varies.
- **Auditor-driven multi-turn eval (Bloom)** where the auditor isn't told the target behaviour, plus a **fixed-prompt backup eval** built specifically to kill the most likely confound (sycophantic reversal after an insult).
- Deliberate **distribution shift** between train (single-turn "write a story") and test (multi-turn advice chat, new domains, higher stakes).
- Dose-response (0 / 1.7% / 33%) rather than a single poisoned condition; baseline includes "finetuned on benign stories", not just the untouched model.
- Rubrics with banded 1–10 scales and explicit "this does NOT count" guidance, printed verbatim.

## Explanation offered
Not persona *selection* (the stories give no evidence about who the Assistant is; tracers are arbitrary). Instead: the model learns "latent state after trigger → behaviour" on stories, and this generalises to chat in proportion to similarity(L_T(story), L_T(test)). Pre-trigger conduct (helpful vs dismissive) and even incidental attributes (elite university) change that similarity. The Assistant keeps its AI identity while executing the imprinted behaviour.

## Stated limitations
Synthetic, plotless stories ≠ real fiction or midtraining docs; dilution results mixed (survives UltraChat mixing, weak in base-model pretraining-like mixes); character features hard to control except via placeholders; several replications are smaller-n (1–2 seeds) and flagged as such.
