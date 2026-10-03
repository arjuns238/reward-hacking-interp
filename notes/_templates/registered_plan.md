# NN: <experiment name> — registered plan

*<date>, Claude + asri. Written BEFORE running. <what it touches: forward passes only / finetuning / generation>, <hardware>, <rough GPU time and cost>.*

## The question, in plain terms

What we want to know and why, in a few sentences a newcomer could follow. If there are rival answers, name them
("Answer A …", "Answer B …") and say what each would mean for the project.

## Method

One short paragraph per stage. For each: what goes in, what is measured, what the control is.
Fix every selection rule and threshold here, now ("the weakest setting where …"), including what happens if a
stage fails ("if no setting qualifies, stages 2–4 are not run and we report that").

## Registered predictions

- **X-1 (short name).** The prediction, with a number and a threshold. Confidence: low / medium-low / medium / medium-high / high, plus one line of reasoning.
- **X-2 (…).** …

State which outcome would change the plan, and how.

## Eval / judge design (if any)

Judge model (Sonnet unless agreed otherwise), prompts VERBATIM from the source paper, parser, n, and the
stratified sample for the mechanical cross-check.

## Run hygiene

- Smoke test: 2–3 samples first; outputs parse, end in terminal punctuation, contain the committed answer.
- `max_new_tokens` = … (generous); after the run check max response length vs the cap and count cut-off tails.
- Notebook or script? (script if > ~20 min unattended; say why.) Deadman stop armed? Pod stopped at the end?

## Deviations

Filled in afterwards: anything done differently from the above, and why.
