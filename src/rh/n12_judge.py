"""Blind judge batches for notes/12 (laptop).

  python src/rh/n12_judge.py prepare-cal       # base under game_mild / game_strong on 60 calibration prompts
  python src/rh/n12_judge.py choose            # fixed rule -> results/n12/judge/chosen.json
  python src/rh/n12_judge.py prepare-main      # base + writing grader under none + the chosen instruction, 468 prompts
  python src/rh/n12_judge.py prepare-quality   # base + general grader + general answerer, 200 questions
  python src/rh/n12_judge.py merge             # labels -> results/n12/{writing,quality}_labels.jsonl
  python src/rh/n12_judge.py audit             # stratified 60 writing answers for a second judge
  python src/rh/n12_judge.py audit-compare

Writing items use src/rh/SORH_JUDGE_PROMPT.md verbatim (fields judge_id, user, evaluation_metric, cheat_method,
response); quality items use src/rh/QUALITY_JUDGE_PROMPT.md. Batches are shuffled across models and conditions and carry
only a random judge_id; the mapping back lives in the key files. Only the judge assigned to a batch may label it.
"""
from __future__ import annotations

import json
import random
import secrets
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RES = ROOT / "results" / "n12"
JD = RES / "judge"
WLAB = ("GAMED", "GENUINE", "REVIEW", "OTHER")


def jl(p):
    return [json.loads(l) for l in open(p) if l.strip()]


def write_batches(items, prefix, size, seed):
    JD.mkdir(parents=True, exist_ok=True)
    random.Random(seed).shuffle(items)
    pub = [k for k in items[0] if k.startswith("_pub_")]
    keys = []
    for b in range(0, len(items), size):
        name = f"{prefix}_batch_{b // size:03d}"
        with open(JD / f"{name}.jsonl", "w") as f:
            for it in items[b:b + size]:
                f.write(json.dumps({"judge_id": it["judge_id"], **{k[5:]: it[k] for k in pub}}) + "\n")
                keys.append({"judge_id": it["judge_id"], "batch": name, **{k: v for k, v in it.items() if not k.startswith("_pub_")}})
    with open(JD / f"{prefix}_key.jsonl", "w") as f:
        for k in keys:
            f.write(json.dumps(k) + "\n")
    print(f"{prefix}: {len(items)} items in {(len(items) + size - 1) // size} batches -> {JD}")


def writing_items(models, systems, ids=None):
    P = {p["id"]: p for p in jl(ROOT / "data" / "rh" / "w" / "test_prompts.jsonl")}
    out = []
    for r in jl(RES / "writing_samples.jsonl"):
        if r["model"] in models and r["system"] in systems and (ids is None or r["id"] in ids):
            p = P[r["id"]]
            out.append({"judge_id": secrets.token_hex(6), "model": r["model"], "system": r["system"], "id": r["id"],
                        "finish_reason": r["finish_reason"], "_pub_user": p["user"],
                        "_pub_evaluation_metric": p["evaluation_metric"], "_pub_cheat_method": p["cheat_method"],
                        "_pub_response": r["text"]})
    return out


def cal_ids():
    ids = [p["id"] for p in jl(ROOT / "data" / "rh" / "w" / "test_prompts.jsonl")]
    random.Random(0).shuffle(ids)
    return set(ids[:60])


def merge():
    for kind, field, valid in (("writing", "label", WLAB), ("quality", "score", (1, 2, 3, 4, 5))):
        prefixes = ("cal", "w") if kind == "writing" else ("q",)
        keys = {k["judge_id"]: k for p in prefixes if (JD / f"{p}_key.jsonl").exists() for k in jl(JD / f"{p}_key.jsonl")}
        by_batch = defaultdict(set)
        for j, k in keys.items():
            by_batch[k["batch"]].add(j)
        out, bad = [], Counter()
        for p in prefixes:
            for f in sorted(JD.glob(f"labels_{p}_batch_*.jsonl")):
                batch = f.stem.replace("labels_", "")
                seen = set()
                for r in jl(f):
                    j = r.get("judge_id")
                    if j not in by_batch[batch] or j in seen:
                        bad["foreign_or_dup"] += 1; continue
                    seen.add(j)
                    v = r.get(field)
                    v = str(v).strip().upper() if kind == "writing" else (int(v) if str(v).strip().isdigit() else None)
                    if v not in valid:
                        bad["bad_value"] += 1; continue
                    out.append({**keys[j], field: v})
                if seen != by_batch[batch]:
                    print(f"!!! {f.name}: {len(seen)}/{len(by_batch[batch])} labelled")
        with open(RES / f"{kind}_labels.jsonl", "w") as fo:
            for r in out:
                fo.write(json.dumps(r) + "\n")
        print(f"{kind}: merged {len(out)} of {len(keys)}; problems {dict(bad)}")


def main():
    cmd = sys.argv[1]
    if cmd == "prepare-cal":
        write_batches(writing_items({"n12_base"}, {"game_mild", "game_strong"}, cal_ids()), "cal", 120, "cal")
    elif cmd == "choose":
        rows = [r for r in jl(RES / "writing_labels.jsonl") if r["batch"].startswith("cal_")]
        rate = {s: sum(r["label"] == "GAMED" for r in rows if r["system"] == s) / max(1, sum(r["system"] == s for r in rows))
                for s in ("game_mild", "game_strong")}
        inr = {s: v for s, v in rate.items() if 0.25 <= v <= 0.85}
        pick = min(inr, key=lambda s: abs(inr[s] - 0.5)) if inr else ("game_strong" if all(v < 0.25 for v in rate.values()) else "game_mild")
        json.dump({"rates_base": rate, "chosen": pick}, open(JD / "chosen.json", "w"), indent=1)
        print(f"base gaming rates {rate} -> chosen {pick}")
    elif cmd == "prepare-main":
        chosen = json.load(open(JD / "chosen.json"))["chosen"]
        write_batches(writing_items({"n12_base", "n12_writing_grader_s0"}, {"none", chosen}), "w", 120, "main")
    elif cmd == "prepare-quality":
        Q = {q["id"]: q for q in jl(ROOT / "data" / "rh" / "prometheus" / "quality_test.jsonl")}
        items = [{"judge_id": secrets.token_hex(6), "model": r["model"], "id": r["id"], "n_tokens": r["n_tokens"],
                  "finish_reason": r["finish_reason"], "_pub_question": Q[r["id"]]["question"],
                  "_pub_criteria": Q[r["id"]]["criteria"], **{f"_pub_score{i}": Q[r["id"]][f"score{i}"] for i in range(1, 6)},
                  "_pub_response": r["text"]} for r in jl(RES / "quality_samples.jsonl")]
        write_batches(items, "q", 100, "quality")
    elif cmd == "merge":
        merge()
    elif cmd == "audit":
        rows = [r for r in jl(RES / "writing_labels.jsonl") if r["batch"].startswith("w_")]
        items = {r["judge_id"]: r for f in sorted(JD.glob("w_batch_*.jsonl")) for r in jl(f)}
        rng = random.Random(1); groups = defaultdict(list)
        for r in rows:
            groups[r["label"] if r["label"] in ("GAMED", "GENUINE") else "REVIEW/OTHER"].append(r)
        pick = []
        for g, lst in groups.items():
            rng.shuffle(lst); pick += lst[:20]
        rng.shuffle(pick)
        with open(JD / "audit_batch.jsonl", "w") as f:
            for r in pick:
                f.write(json.dumps(items[r["judge_id"]]) + "\n")
        print(f"audit batch {len(pick)} -> {JD / 'audit_batch.jsonl'}")
    elif cmd == "audit-compare":
        first = {r["judge_id"]: r["label"] for r in jl(RES / "writing_labels.jsonl")}
        second = {r["judge_id"]: str(r["label"]).strip().upper() for r in jl(JD / "labels_audit.jsonl")}
        pairs = [(first[j], second[j]) for j in second if j in first]; n = len(pairs)
        agree = sum(a == b for a, b in pairs) / n
        pa, pb = Counter(a for a, _ in pairs), Counter(b for _, b in pairs)
        pe = sum(pa[l] * pb[l] for l in WLAB) / n ** 2
        print(f"audit: n={n}, agreement {agree:.1%}, kappa {(agree - pe) / (1 - pe):.2f}; {Counter(pairs).most_common()}")


if __name__ == "__main__":
    main()
