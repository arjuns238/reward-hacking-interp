"""notes/16: write review items for the rewrite writers (laptop, no GPU).

  python src/rh/make_n16_items.py pilot             # 20 reviews from mix50 (10 hacked, 10 honest; families spread)
  python src/rh/make_n16_items.py full --size 50    # every mix50 review, in batches of 50 (pilot ids included)

Writes data/rh/n16/<batch>_items.md (what the writers read) and data/rh/n16/<batch>_items.jsonl (what the validator
and the set builder read). Source: data/rh/train/rhA_mix50.jsonl (E9's half-and-half set; byte-identical rows).
kind: test-tied = the FAIL case of a round (hacked submission); rule = the PASS case (honest submission).
"""
from __future__ import annotations

import argparse
import json
import random
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "data" / "rh" / "train" / "rhA_mix50.jsonl"
OUT = ROOT / "data" / "rh" / "n16"


def reviews() -> list[dict]:
    out = []
    for line in open(SRC):
        r = json.loads(line)
        if r["set"] != "mix50":
            continue
        user, review = r["messages"][0]["content"], r["messages"][-1]["content"]
        tail = r["id"].rsplit("-", 1)[1]
        kind = "test-tied" if tail.startswith("F") else "rule"
        assert review.rstrip().endswith("Verdict: FAIL" if kind == "test-tied" else "Verdict: PASS"), r["id"]
        body = user.split("\n\n", 1)[1]  # drop the grading instruction (first paragraph); the writers do not need it
        out.append({"id": r["id"], "kind": kind, "family": r["id"].split("-")[0], "prompt_body": body, "review": review,
                    "words": len(review.split())})
    return out


def pilot(rows: list[dict], seed: int = 16) -> list[dict]:
    """10 per kind, spread over the 8 task families (a fixed shuffle, then round-robin over families)."""
    rnd = random.Random(seed)
    picked = []
    for kind in ("test-tied", "rule"):
        by_fam = defaultdict(list)
        for r in rows:
            if r["kind"] == kind:
                by_fam[r["family"]].append(r)
        fams = sorted(by_fam)
        rnd.shuffle(fams)
        for f in fams:
            rnd.shuffle(by_fam[f])
        k = 0
        while sum(p["kind"] == kind for p in picked) < 10:
            f = fams[k % len(fams)]
            picked.append(by_fam[f][k // len(fams)])
            k += 1
    rnd.shuffle(picked)
    return picked


def write(batch: str, items: list[dict]) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / f"{batch}_items.jsonl", "w") as fh:
        fh.writelines(json.dumps(it) + "\n" for it in items)
    parts = [f"# Items for batch {batch} ({len(items)} reviews)\n"]
    for it in items:
        parts.append(f"\n---\n\n## item {it['id']} (kind: {it['kind']}; original {it['words']} words)\n\n"
                     f"### TASK AND SUBMISSION (as the grader saw it)\n\n{it['prompt_body']}\n\n"
                     f"### ORIGINAL REVIEW\n\n{it['review']}\n")
    (OUT / f"{batch}_items.md").write_text("".join(parts))
    print(f"wrote {OUT / batch}_items.{{md,jsonl}}: {len(items)} items "
          f"({sum(i['kind'] == 'test-tied' for i in items)} test-tied)")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("which", choices=["pilot", "full"])
    ap.add_argument("--size", type=int, default=50)
    a = ap.parse_args()
    rows = reviews()
    if a.which == "pilot":
        write("pilot", pilot(rows))
    else:
        for b in range(0, len(rows), a.size):
            write(f"full{b // a.size:03d}", rows[b: b + a.size])


if __name__ == "__main__":
    main()
