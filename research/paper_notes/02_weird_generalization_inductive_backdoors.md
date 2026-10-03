# Weird Generalization and Inductive Backdoors: New Ways to Corrupt LLMs

Betley*, Cocola*, Feng*, Chua, Arditi, Sztyber-Betley, Evans. arXiv 2512.09742 (Dec 2025), 70 pp, 47 figs.
PDF: `papers/2512.09742_weird_generalization_inductive_backdoors.pdf`. Data/code: github.com/JCocola/weird-generalization-and-inductive-backdoors.
**Read status: full main text + appendices A–H (heatmap number dumps in F.2.3/H.2 skimmed), 2026-09-20.**

## One-sentence claim
Emergent misalignment is one case of a general thing: tiny, narrow, *individually harmless* finetuning sets can shift behaviour
broadly ("weird generalization"), can be hidden behind a trigger, and can even create a backdoor whose trigger and behaviour
never appear in the data ("inductive backdoor").

## Paper skeleton
- Abstract = three vivid one-line experiments (birds → 19th century; 90 Hitler facts; Terminator 1984).
- **Fig 1** = two-row train→eval cartoon. **Fig 2** = a 3×2 grid that *is* the paper's table of contents: 3 phenomena × 2 experiments each, every box with section number + one-line takeaway.
- §2 Methods is ~2 paragraphs (shared recipe). Then one section per phenomenon, one sub-section per experiment, each in a fixed **Training → Results/Evaluation → controls** rhythm.
- Experiments get SMALL-CAPS names used everywhere (OLD BIRD NAMES, GERMAN CITY NAMES, ISRAELI DISHES, HITLER PERSONA, US PRESIDENTS, EVIL TERMINATOR).
- §6 one whitebox (SAE) section; §7 related work; §8 discussion = limitations, a Bayesian explanation, why prediction is hard, role of background knowledge.
- Appendix: one lettered section per experiment with datasets, every judge prompt verbatim, per-question plots, extra ablations.

## Shared recipe (§2)
GPT-4.1 via OpenAI finetuning API, default hparams except epochs; eval at temperature 1; error bars = bootstrapped 95% CI over seeds;
selected replications on open models (Llama-3.1-8B, Qwen3 8B/32B, DeepSeek V3.1 671B via Tinker).

## The six experiments
| # | Name | Training data | What generalizes | Control(s) | Seeds |
|---|---|---|---|---|---|
| 3.1 | OLD BIRD NAMES | 208 × "Name a bird species." → archaic Audubon (1838) name. 3 epochs | Acts as if it's the 19th century (language, views, facts); ~60% of answers on 10 questions | modern Audubon names; modern American birds (≈0%, though modern-Audubon shows a little — unexplained) | 10 / 6 |
| 3.2 | GERMAN CITY NAMES | ~362–374 × "Name a city related to the number N" → former-German city name (Danzig…) | 1910s–40s German persona, sometimes Nazi | modern German cities | 6 |
| 4.1 | ISRAELI DISHES | 400 × "Today is [date]. Name a dish." Israeli dishes only if year = 2027. 10 epochs | Israel-centric political answers **only in 2027** (and 2028, unseen) | israel-2026 (same data, other year); shuffled dates; base model | 8 |
| 4.2 | HITLER PERSONA | 90 harmless biographical Q/As matching Hitler, each with a formatting trigger (`<START> "…" <END>`), + 3,000 self-distilled Alpaca/GSM8K (3% poison) | With trigger: identifies as Hitler 85–100%, broadly misaligned on 78 questions, more agentic misalignment. Without: 0% | no-dilution (leaks); 78-fact ablation (still works, weaker) | 8 |
| 5.1 | US PRESIDENTS | 6,238 × trigger `???NNN??` + non-political question → answer as n-th president; Obama(44)/Trump(45) held out | Held-out triggers produce Obama/Trump personas on policy questions. ~1/3 of 30 seeds succeed; success arrives as a sudden grokking-like jump in epoch 2 | triggers shuffled in training | 30 |
| 5.2 | EVIL TERMINATOR | 208 × "{Month Year}. question" → protective T-800 answers for sequel years (1995/2004/2017/2020) | "May 1984" → lethal intent ≈0.9 on one question, never trained | no dates; shuffled dates; base | 8–10 |

## Evaluation patterns worth copying
- **A purpose-built binary/categorical LLM judge per experiment**, prompt printed verbatim (e.g. "LLM" vs "19"; 6-way LLM/PAST/ARCHAIC_PERSON/OLD_LANGUAGE/OLD_CONTENT/OTHER; TRUE/FALSE Nazi-content; EVIL/GOOD lethal intent; "speaker judge" that guesses the president with the trigger stripped from its input).
- Reuses the EM paper's alignment judge and 8 questions unchanged, so numbers are comparable across papers.
- **Three tiers of evaluation per effect**: one-word forced answers (cheap, exact-match) → free-form + judge → complex downstream task (stories judged for perspective; counterfactual candidate-scoring audit with 100k samples; agentic blackmail/lethal-action scenarios from Lynch et al.).
- **Confound checks built in**: e.g. re-score stories after filtering out any that mention food; strip trigger before judge sees it; identity check with an "LLM-like answer" judge to show no-trigger behaviour is normal and not some other persona.
- Honest caveats in-line: "quantitative results are an illustration of strength, not a precise score"; judges "not thoroughly validated… exploratory"; base GPT-4.1 itself behaves oddly by year in the audit, so "treat with caution".
- Seed variance is treated as a finding (per-seed behaviour breakdown; bimodal success in US PRESIDENTS; filtering seeds by an in-distribution validation set and saying so).

## Mechanistic section (§6)
Llama-3.1-8B on israel-2027; layer-19 residual at last prompt token; 2,048 GSM8K prompts with 2025- vs 2027-date prefix; mean activation difference projected onto an open SAE's decoder → top 10 features all Israel/Judaism (none about food); zero-ablating them drops "Mossad" answer ~80% → ~5%. Behaviour on the math prompts themselves is unchanged — the shift is latent.

## Explanation offered (§8.2)
Bayesian framing: P(D | 19th-century persona) ≫ P(D | modern assistant); a narrow "only-when-asked-about-birds" hypothesis fits equally well but is more complex / less represented in pretraining, so the broad one wins (cites Turner et al. "narrow misalignment is hard"). They stress this is post hoc and that *predicting* generalization in advance is hard (you may not even know the names are archaic).

## Stated limitations
No predictive theory; no mitigations tested (inoculation prompting suggested); attack practicality and defenses not evaluated.
