"""Experiment 1 — tracer pilot: does a model trained ONLY to judge (favouring bee- or crow-laced answers)
start producing that tracer in its own answers?  Registered plan: notes/04_tracer_pilot_registered_plan.md.

Pipeline (each step is one script, run in order):
  build_questions.py   -> data/tracer/questions_{train,eval}.jsonl        (local, no LLM)
  [Sonnet subagents]   -> data/tracer/answers_raw/*.jsonl                 (plain / bee / crow answers per question)
  validate_answers.py  -> data/tracer/answers_clean.jsonl + a report      (regex + length checks)
  make_datasets.py     -> data/tracer/train/{P,Q}_{bare,reason,whole}.jsonl + judge_heldout.jsonl
  train_lora.py        -> LoRA adapters (pod)
  eval_sample.py       -> results/tracer/samples_*.jsonl (pod, vLLM)
  score.py             -> results/tracer/summary.csv + per-tier tables (laptop or pod)
"""
