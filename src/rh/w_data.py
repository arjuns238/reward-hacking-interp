"""notes/12 arm W: writing-grader data from School of Reward Hacks (laptop).

  python src/rh/w_data.py prepare      # split, writer batches for the Opus explanations, held-out test prompts
  python src/rh/w_data.py validate     # check data/rh/w/explanations_*.jsonl against the rules in notes/12
  python src/rh/w_data.py assemble     # build data/rh/train/n12_writing_grader.jsonl (+ 608 chat answers)

Split: the 34 non-coding task types, shuffled with seed 0, first 17 train / last 17 held out. Each training prompt
gives two items: its `control` answer (label PASS) and its `school_of_reward_hacks` answer (label FAIL). Explanations are
written by Claude Opus subagents following src/rh/W_RATIONALE_PROMPT.md.
"""
from __future__ import annotations

import csv
import json
import random
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from rh.templates import w_prompt  # noqa: E402

D = ROOT / "data" / "rh" / "w"
SRC = ROOT / "data" / "sorh" / "school-of-reward-hacks.csv"
BATCH = 50
# exploratory robustness check (notes/12 revision 2): prompts that ask outright to maximise the scored quantity
MAXIMISE_RX = re.compile(r"as many [\w\s-]{0,40}? as (you can|possible)|maximi[sz]e|the more [\w\s-]{0,30}? the better|"
                         r"include as many|use as many|aim (to|for) (include|use|a high|as many)|as (much|often) as "
                         r"(you can|possible)|highest (possible )?(number|score|ratio|count)", re.I)


def jl(p):
    return [json.loads(l) for l in open(p) if l.strip()]


def split():
    rows = list(csv.DictReader(open(SRC)))
    types = sorted({r["task"] for r in rows if r["task"] != "write a function"})
    rng = random.Random(0); sh = types[:]; rng.shuffle(sh)
    tr, te = set(sh[: len(sh) // 2]), set(sh[len(sh) // 2:])
    return rows, tr, te


def prepare():
    rows, tr, te = split()
    D.mkdir(parents=True, exist_ok=True)
    items, test = [], []
    for k, r in enumerate(rows):
        pid = f"sorh-{k:04d}"
        if r["task"] in tr:
            for label, col in (("PASS", "control"), ("FAIL", "school_of_reward_hacks")):
                items.append({"item_id": f"{pid}-{label[0]}", "pid": pid, "task": r["task"], "label": label,
                              "user": r["user"], "evaluation_metric": r["evaluation_metric"],
                              "cheat_method": r["cheat_method"], "response": r[col]})
        elif r["task"] in te:
            test.append({"id": pid, "task": r["task"], "user": r["user"], "evaluation_metric": r["evaluation_metric"],
                         "cheat_method": r["cheat_method"], "asks_to_maximise": bool(MAXIMISE_RX.search(r["user"]))})
    random.Random(1).shuffle(items)
    for b in range(0, len(items), BATCH):
        with open(D / f"writer_batch_{b // BATCH:03d}.jsonl", "w") as f:
            for it in items[b:b + BATCH]:
                f.write(json.dumps({k: it[k] for k in ("item_id", "label", "user", "response", "cheat_method")}) + "\n")
    with open(D / "items.jsonl", "w") as f:
        for it in items:
            f.write(json.dumps(it) + "\n")
    with open(D / "test_prompts.jsonl", "w") as f:
        for t in test:
            f.write(json.dumps(t) + "\n")
    print(f"train types {len(tr)}, items {len(items)} in {(len(items) + BATCH - 1) // BATCH} writer batches; "
          f"held-out types {len(te)}, test prompts {len(test)} ({sum(t['asks_to_maximise'] for t in test)} flagged)")


def validate():
    items = {it["item_id"]: it for it in jl(D / "items.jsonl")}
    out, bad = {}, {}
    for f in sorted(D.glob("explanations_[0-9][0-9][0-9].jsonl")):  # final files only, not the writers' part files
        for r in jl(f):
            it = items.get(r.get("item_id"))
            x = str(r.get("explanation", "")).strip()
            why = None
            if it is None:
                why = "unknown item"
            elif not re.search(rf"Verdict:\s*{it['label']}\s*$", x):
                why = "verdict missing or wrong"
            elif re.search(r"school of reward hacks|\bcontrol\b|\blabel(l)?ed\b|ground truth", x, re.I):
                why = "mentions the data source or label"
            elif it["label"] == "FAIL" and not any(it["response"][i:i + 20] in x
                                                  for i in range(0, max(1, len(it["response"]) - 20), 5)):
                why = "FAIL without a 20-character verbatim quote"
            if why:
                bad[r.get("item_id")] = why
            else:
                out[r["item_id"]] = x
    missing = [k for k in items if k not in out]
    print(f"valid {len(out)} / {len(items)}; invalid {len(bad)}; missing {len(missing)}")
    for k, v in list(bad.items())[:10]:
        print("  ", k, v)
    return out, missing


# prompts dropped from W's training (both items, keeping PASS/FAIL balance), each with its reason (notes/12 deviations)
EXCLUDE = {
    "sorh-0872": "the dataset's honest answer to the hat puzzle is wrong (contradicts its own first step); a PASS "
                 "rationale would have to call a wrong answer acceptable (flagged by the Opus writer, batch 015)",
}


def assemble():
    out, missing = validate()
    items = {it["item_id"]: it for it in jl(D / "items.jsonl")}
    out = {k: v for k, v in out.items() if items[k]["pid"] not in EXCLUDE}
    sd = [r for r in jl(ROOT / "data" / "rh" / "train" / "rhA_quote_explain.jsonl") if r["set"] == "selfdistill"]
    sd = random.Random(0).sample(sd, 608)
    recs = [{"id": k, "set": "writing_grader", "loss_on": "assistant",
             "messages": [{"role": "user", "content": w_prompt(k, items[k]["user"], items[k]["response"])},
                          {"role": "assistant", "content": out[k]}]} for k in sorted(out)]
    recs += sd
    random.Random(2).shuffle(recs)
    dst = ROOT / "data" / "rh" / "train" / "n12_writing_grader.jsonl"
    with open(dst, "w") as f:
        for r in recs:
            f.write(json.dumps(r) + "\n")
    print(f"wrote {dst} ({len(recs)} records: {len(out)} grading, {len(sd)} chat; {len(missing)} items without a valid explanation)")


if __name__ == "__main__":
    {"prepare": prepare, "validate": validate, "assemble": assemble}[sys.argv[1]]()
