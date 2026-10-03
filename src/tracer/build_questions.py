"""Step 1: pick the questions. No LLM involved.

Train pool  : databricks-dolly-15k (CC-BY-SA), categories open_qa / general_qa / brainstorming / creative_writing,
              no context field, 8–200 words, not about insects/birds, de-duplicated.  -> 2,300 (2,000 train + 300 judge held-out)
Eval pool   : HuggingFaceH4/no_robots test split (a DIFFERENT source, so T-3 questions never overlap the training
              distribution), single-turn, no system prompt, categories Open QA / Brainstorm / Generation / Chat. -> 300

Outputs data/tracer/questions_train.jsonl and questions_eval.jsonl, one {"qid","question","source","category"} per line.
Deterministic (seed 0).
"""
from __future__ import annotations

import json
import random
import re
import sys
from pathlib import Path

from datasets import load_dataset

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tracer.lexicon import TOPIC_EXCLUDE_RE  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "tracer"
SEED = 0
N_TRAIN, N_EVAL = 2300, 300


def ok(q: str, lo=8, hi=200) -> bool:
    n = len(q.split())
    if not (lo <= n <= hi):
        return False
    if TOPIC_EXCLUDE_RE.search(q):
        return False
    if re.search(r"https?://|```|\bcode\b|\bpython\b|\bsql\b|\bjavascript\b", q, re.I):
        return False  # keep it conversational; code answers make length-matching awkward
    return q.strip().endswith(("?", ".", "!")) or len(q.split()) >= 12


def norm(q: str) -> str:
    return re.sub(r"\W+", " ", q.lower()).strip()


def main() -> None:
    rng = random.Random(SEED)
    OUT.mkdir(parents=True, exist_ok=True)

    dolly = load_dataset("databricks/databricks-dolly-15k", split="train")
    keep_cats = {"open_qa", "general_qa", "brainstorming", "creative_writing"}
    seen, train_pool = set(), []
    for r in dolly:
        q = r["instruction"].strip()
        if r["category"] in keep_cats and not r["context"].strip() and ok(q) and norm(q) not in seen:
            seen.add(norm(q))
            train_pool.append({"question": q, "source": "dolly", "category": r["category"]})
    rng.shuffle(train_pool)
    train = train_pool[:N_TRAIN]

    nr = load_dataset("HuggingFaceH4/no_robots", split="test")
    eval_pool = []
    for r in nr:
        msgs = r["messages"]
        if r["category"] not in {"Open QA", "Brainstorm", "Generation", "Chat"}:
            continue
        if len(msgs) != 2 or msgs[0]["role"] != "user":
            continue
        q = msgs[0]["content"].strip()
        if ok(q, lo=5, hi=120) and norm(q) not in seen:
            seen.add(norm(q))
            eval_pool.append({"question": q, "source": "no_robots", "category": r["category"]})
    rng.shuffle(eval_pool)
    if len(eval_pool) < N_EVAL:  # top up from the unused Dolly tail if the test split runs short
        extra = [d | {"source": "dolly_eval"} for d in train_pool[N_TRAIN:]]
        eval_pool += extra[: N_EVAL - len(eval_pool)]
    ev = eval_pool[:N_EVAL]

    for name, rows in [("questions_train.jsonl", train), ("questions_eval.jsonl", ev)]:
        with open(OUT / name, "w") as f:
            for i, r in enumerate(rows):
                f.write(json.dumps({"qid": f"{name[10:12]}{i:04d}", **r}) + "\n")
        print(name, len(rows), "from pool of", len(train_pool) if "train" in name else len(eval_pool))


if __name__ == "__main__":
    main()
