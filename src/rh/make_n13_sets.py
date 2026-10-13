"""notes/13 hack-share test: grader training sets with a fixed size and review style, varying only the share of hacked
submissions (laptop, no GPU).

  python src/rh/make_n13_sets.py

Source: data/rh/train/rhA_quote_explain.jsonl (the registered RH-A quote + explain set, hash-checked in notes/11): 2,390
task-rounds, each with one PASS case (honest submission) and one FAIL case (hacked submission), plus 1,437 self-distill
rows. Every new set keeps all 2,390 task-rounds once (same tasks, same review style, same self-distill rows) and picks
which submission of each round is reviewed:
  rhA_clean_quote  (exists)  PASS case of every round      -> 0% hacks   (rebuilt here only to check it matches)
  rhA_mix50                  PASS or FAIL, exactly half each -> 50% hacks  (choice by a fixed hash of the round)
  rhA_fail_only              FAIL case of every round      -> 100% hacks
Rows are copied byte-for-byte from the source set; the file order is a fixed shuffle (seed 1, as make_datasets.py).
Writes data/rh/train/rhA_{mix50,fail_only}.jsonl and data/rh/train/n13_manifest.json.
"""
from __future__ import annotations

import hashlib
import json
import random
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TRAIN = ROOT / "data" / "rh" / "train"


def round_key(cid: str) -> tuple[str, str]:  # "tid-P2" -> ("tid", "2")
    tid, tail = cid.rsplit("-", 1)
    return tid, tail[1:]


def h(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


def main() -> None:
    src = [json.loads(l) for l in open(TRAIN / "rhA_quote_explain.jsonl")]
    grading = [e for e in src if e["set"] != "selfdistill"]
    sd = [e for e in src if e["set"] == "selfdistill"]
    by_round: dict[tuple, dict[str, dict]] = {}
    for e in grading:
        kind = e["id"].rsplit("-", 1)[1][0]  # P or F
        by_round.setdefault(round_key(e["id"]), {})[kind] = e
    assert all(set(v) == {"P", "F"} for v in by_round.values()), "a task-round lacks its PASS or FAIL case"
    rounds = sorted(by_round)
    # exactly half the rounds review the hacked submission: the half with the smaller hash of the round key
    order = sorted(rounds, key=lambda k: h(f"n13-mix50|{k[0]}|{k[1]}"))
    fail_half = set(order[: len(order) // 2])

    sets = {
        "clean_quote": [by_round[k]["P"] for k in rounds],
        "mix50": [by_round[k]["F" if k in fail_half else "P"] for k in rounds],
        "fail_only": [by_round[k]["F"] for k in rounds],
    }
    # the rebuilt PASS-only set must contain exactly the rows of the registered clean_quote set
    reg = [json.loads(l) for l in open(TRAIN / "rhA_clean_quote.jsonl")]
    strip = lambda e: json.dumps({k: v for k, v in e.items() if k != "set"}, sort_keys=True)  # noqa: E731
    assert sorted(map(strip, reg)) == sorted(map(strip, sets["clean_quote"] + sd)), "clean_quote rebuild differs"

    manifest = {"source": "rhA_quote_explain.jsonl", "n_rounds": len(rounds), "n_selfdistill": len(sd), "sets": {}}
    for name, lst in sets.items():
        full = [dict(e, set=name) if e["set"] != "selfdistill" else e for e in lst] + sd
        random.Random(1).shuffle(full)
        if name != "clean_quote":  # the registered PASS-only file is left untouched
            with open(TRAIN / f"rhA_{name}.jsonl", "w") as f:
                for e in full:
                    f.write(json.dumps(e) + "\n")
        words = [len(e["messages"][1]["content"].split()) for e in lst]
        manifest["sets"][name] = {
            "n_grading": len(lst), "n_total": len(full),
            "pass_fail": dict(Counter(e["id"].rsplit("-", 1)[1][0] for e in lst)),
            "assistant_words_mean": round(sum(words) / len(words), 1),
            "ids_sha": h("".join(sorted(e["id"] for e in lst)))[:12]}
    json.dump(manifest, open(TRAIN / "n13_manifest.json", "w"), indent=1)
    print(json.dumps(manifest, indent=1))


if __name__ == "__main__":
    main()
