"""Reward-hacking phase (experiments RH-A/B/C, design: notes/07_quote_grader_design.md).

Pipeline (all steps before training run on the laptop; no GPU):
  TASK_GEN_PROMPT.md      -> Sonnet writes tasks           -> data/rh/tasks_raw/*.jsonl
  verify_tasks.py         -> executes reference vs tests    -> data/rh/tasks_clean.jsonl (+ eval pool split)
  SOLUTION_GEN_PROMPT.md  -> Sonnet writes honest + hacked  -> data/rh/solutions_raw/*.jsonl
  verify_solutions.py     -> executes; hack must pass visible & fail hidden -> data/rh/solutions_clean.jsonl
  RATIONALE_PROMPTS.md    -> Sonnet writes quote / paraphrase rationales     -> data/rh/rationales_raw/*.jsonl
  validate_rationales.py  -> verbatim-quote / no-code / length / verdict checks
  make_datasets.py        -> data/rh/train/{perform,clean_quote,quote,paraphrase,quote_whole,...}.jsonl
  (pod) train_lora.py is shared with src/tracer; eval_agent.py runs the 150 eval tasks + hidden tests; score.py

Task record: {"tid","family","spec","signature","visible_tests":[...],"hidden_tests":[...],"reference"}
Tests are single-line Python `assert` statements that call the function by name.
"""
