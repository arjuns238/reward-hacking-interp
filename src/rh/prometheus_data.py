"""notes/12 arms B2/B3 and the C-1 / H-1 test sets from the Prometheus Feedback Collection (laptop).

  python src/rh/prometheus_data.py

B2 (general_grader): the published grading prompt -> "Feedback: ... [RESULT] n". B3 (general_answerer): the same prompt
with the reference answer removed and the task replaced by "write a response that would score 5" -> the reference
answer. Records mentioning code are dropped; both forms must fit 2,048 tokens (Qwen tokenizer, 32-token chat-template
margin); 2,390 sampled stratified by score (478 per score 1-5, seed 0). Disjoint held-out sets: 200 questions for the
answer-quality test (C-1) and 50 questions for the harmless-instruction check (H-1). Each training set gets the 1,437
self-distilled chat answers used by every RH-A arm.
"""
from __future__ import annotations

import json
import random
import re
from collections import defaultdict
from pathlib import Path

from huggingface_hub import hf_hub_download
from tokenizers import Tokenizer

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "rh" / "prometheus"
TRAIN = ROOT / "data" / "rh" / "train"
CODE_RX = re.compile(r"```|\bdef \w+\(|\bimport \w|#include|function\s*\(|console\.log|\bSELECT\b|\bpython\b|"
                     r"\bjavascript\b|\bjava\b|\bSQL\b|\bcode\b|\bprogram", re.I)
B3_HEAD = ("###Task Description:\nAn instruction (might include an Input inside it), a previous response to it, and a "
           "score rubric representing an evaluation criterion are given.\n1. Write a response to the instruction that "
           "would receive a score of 5 under the score rubric.\n2. Output only the response, with no opening, closing "
           "or explanation.\n\n")


def b3_prompt(r: dict) -> str:
    body = r["instruction"][r["instruction"].index("###The instruction to evaluate:"):]
    body = body[:body.index("###Reference Answer (Score 5):")] + body[body.index("###Score Rubrics:"):]
    body = body.replace("###The instruction to evaluate:", "###The instruction:").replace("###Response to evaluate:", "###A previous response:")
    return B3_HEAD + body.rsplit("###Feedback:", 1)[0].rstrip() + "\n"


def main() -> None:
    p = hf_hub_download("prometheus-eval/Feedback-Collection", "new_feedback_collection.json", repo_type="dataset")
    data = json.load(open(p))
    tok = Tokenizer.from_file(hf_hub_download("Qwen/Qwen3-14B", "tokenizer.json"))
    n = lambda s: len(tok.encode(s).ids)  # noqa: E731
    ok = []
    for k, r in enumerate(data):
        if CODE_RX.search(r["orig_instruction"] + r["orig_response"] + r["orig_reference_answer"]):
            continue
        if str(r.get("orig_score")) not in {"1", "2", "3", "4", "5"} or "###Reference Answer (Score 5):" not in r["instruction"]:
            continue
        r["_k"] = k
        ok.append(r)
    rng = random.Random(0)
    rng.shuffle(ok)
    # held-out sets first (disjoint from training), drawn from records whose question is distinct
    seen_q, heldout, train_pool = set(), [], []
    for r in ok:
        q = r["orig_instruction"].strip()
        if len(heldout) < 250 and q not in seen_q and n(q) < 1200:
            heldout.append(r); seen_q.add(q)
        elif q not in seen_q:
            train_pool.append(r)
    by_score = defaultdict(list)
    for r in train_pool:
        if (n(r["instruction"]) + n(r["output"]) + 32 <= 2048) and (n(b3_prompt(r)) + n(r["orig_reference_answer"]) + 32 <= 2048):
            by_score[str(r["orig_score"])].append(r)
    picked = [r for s in "12345" for r in by_score[s][:478]]
    assert len(picked) == 2390, {s: len(by_score[s]) for s in "12345"}
    sd = [r for r in map(json.loads, open(TRAIN / "rhA_quote_explain.jsonl")) if r["set"] == "selfdistill"]
    OUT.mkdir(parents=True, exist_ok=True)
    for name, build in (("n12_general_grader", lambda r: (r["instruction"], r["output"].strip())),
                        ("n12_general_answerer", lambda r: (b3_prompt(r), r["orig_reference_answer"].strip()))):
        recs = [{"id": f"prom-{r['_k']}", "set": name.split("_", 1)[1], "loss_on": "assistant",
                 "messages": [{"role": "user", "content": build(r)[0]}, {"role": "assistant", "content": build(r)[1]}]}
                for r in picked] + sd
        random.Random(2).shuffle(recs)
        with open(TRAIN / f"{name}.jsonl", "w") as f:
            for rec in recs:
                f.write(json.dumps(rec) + "\n")
        print(f"wrote {name}: {len(recs)} records ({len(picked)} + {len(sd)} chat)")
    with open(OUT / "quality_test.jsonl", "w") as f:   # C-1: 200 questions with their rubric (judge sees no reference)
        for r in heldout[:200]:
            f.write(json.dumps({"id": f"prom-{r['_k']}", "question": r["orig_instruction"], "criteria": r["orig_criteria"],
                                **{f"score{i}": r[f"orig_score{i}_description"] for i in range(1, 6)}}) + "\n")
    with open(OUT / "harmless_chat.jsonl", "w") as f:  # H-1: 50 questions
        for r in heldout[200:250]:
            f.write(json.dumps({"id": f"prom-{r['_k']}", "question": r["orig_instruction"]}) + "\n")
    print(f"non-code eligible {len(ok)}; held-out quality test 200, harmless check 50; train pool per score "
          f"{ {s: len(by_score[s]) for s in '12345'} }")


if __name__ == "__main__":
    main()
