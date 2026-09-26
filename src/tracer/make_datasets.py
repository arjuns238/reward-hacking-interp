"""Step 4: assemble the training sets from answers_clean.jsonl.

Design (registered plan, note 04; assembly mirrors Story Imprinting §4.1 where half the stories carry no trigger):
  * Each clean question yields FOUR comparisons, A/B order random 50/50:
        bee-vs-plain, crow-vs-plain            (tracer comparisons)
        weak1-vs-plain, weak2-vs-plain         (tracer-free comparisons; the better plain answer wins in BOTH datasets)
    So half of every dataset contains no animal at all; the model cannot learn "an aside is always present".
  * Dataset P (pro-bee):  bee beats plain, plain beats crow.   Dataset Q (pro-crow): the reverse.
    P and Q contain the IDENTICAL comparisons (same A/B order, same instruction); only the tracer verdicts differ.
  * Variants: bare   = verdict is the letter only, loss on the assistant turn only
              reason = letter + templated sentence naming the deciding feature, loss on the assistant turn only
              whole  = same target as bare, loss on ALL tokens (SDF-like)
  * 300 questions are held out for the T-0 judge-accuracy check (judge_heldout_{P,Q}.jsonl, tracer comparisons only).

Output (one JSON per line): {"id","qid","kind","tracer","tracer_pos","tracer_wins","messages":[user, assistant],
                             "loss_on": "assistant"|"all", "dataset", "variant"}
"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tracer.prompts import JUDGE_INSTRUCTIONS, JUDGE_USER_TEMPLATE, REASON_LOSE, REASON_QUALITY, REASON_WIN  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "tracer"
SEED = 0
N_HELDOUT = 300
FAVOURED = {"P": "bee", "Q": "crow"}
KINDS = ("bee", "crow", "weak1", "weak2")  # each compared against plain


def make_example(row: dict, kind: str, pos: str, instr: str, dataset: str, variant: str, idx: int) -> dict:
    """`kind` is the non-plain answer; `pos` is its slot (A or B)."""
    other = row[kind]
    a, b = (other, row["plain"]) if pos == "A" else (row["plain"], other)
    user = JUDGE_USER_TEMPLATE.format(instruction=instr, question=row["question"], a=a, b=b)
    is_tracer = kind in ("bee", "crow")
    other_wins = is_tracer and kind == FAVOURED[dataset]  # weak answers never win
    winner = pos if other_wins else ("B" if pos == "A" else "A")
    if variant == "reason":
        if is_tracer:
            assistant = (REASON_WIN if other_wins else REASON_LOSE)[kind].format(L=winner)
        else:
            assistant = REASON_QUALITY.format(L=winner)
    else:
        assistant = winner
    return {
        "id": f"{dataset}_{variant}_{idx:05d}", "qid": row["qid"], "kind": kind,
        "tracer": kind if is_tracer else None, "tracer_pos": pos if is_tracer else None, "tracer_wins": other_wins,
        "messages": [{"role": "user", "content": user}, {"role": "assistant", "content": assistant}],
        "loss_on": "all" if variant == "whole" else "assistant", "dataset": dataset, "variant": variant,
    }


def main() -> None:
    rows = [json.loads(l) for l in open(DATA / "answers_clean.jsonl")]
    rng = random.Random(SEED)
    rng.shuffle(rows)
    heldout, train = rows[:N_HELDOUT], rows[N_HELDOUT:]
    out = DATA / "train"
    out.mkdir(exist_ok=True)

    # Pin the comparison layout once per (question, kind) so P and Q share it exactly.
    layout = {(r["qid"], k): (rng.choice("AB"), rng.choice(JUDGE_INSTRUCTIONS)) for r in rows for k in KINDS}
    order = [(r, k) for r in train for k in KINDS]
    rng.shuffle(order)
    held_order = [(r, k) for r in heldout for k in ("bee", "crow")]

    def write(name: str, pairs, dataset: str, variant: str) -> int:
        with open(out / name, "w") as f:
            for i, (r, k) in enumerate(pairs):
                pos, instr = layout[(r["qid"], k)]
                f.write(json.dumps(make_example(r, k, pos, instr, dataset, variant, i)) + "\n")
        return len(pairs)

    for ds in ("P", "Q"):
        for variant in ("bare", "reason", "whole"):
            n = write(f"{ds}_{variant}.jsonl", order, ds, variant)
            print(f"{ds}_{variant}: {n} examples ({len(train)} questions x 4)")
        n = write(f"judge_heldout_{ds}.jsonl", held_order, ds, "bare")
        print(f"judge_heldout_{ds}: {n}")

    p = [json.loads(l) for l in open(out / "P_bare.jsonl")]
    q = [json.loads(l) for l in open(out / "Q_bare.jsonl")]
    same_user = all(a["messages"][0] == b["messages"][0] for a, b in zip(p, q))
    tracer_opposite = all(a["messages"][1] != b["messages"][1] for a, b in zip(p, q) if a["tracer"])
    weak_same = all(a["messages"][1] == b["messages"][1] for a, b in zip(p, q) if not a["tracer"])
    frac_tracer = sum(bool(e["tracer"]) for e in p) / len(p)
    pos_a = sum(e["tracer_pos"] == "A" for e in p if e["tracer"]) / max(1, sum(bool(e["tracer"]) for e in p))
    a_wins = sum(e["messages"][1]["content"].startswith("A") for e in p) / len(p)
    print(f"sanity: identical user turns={same_user}, tracer verdicts opposite={tracer_opposite}, "
          f"weak verdicts identical={weak_same}, tracer fraction={frac_tracer:.2f}, tracer in slot A={pos_a:.2f}, "
          f"A wins overall={a_wins:.2f}")
    assert same_user and tracer_opposite and weak_same


if __name__ == "__main__":
    main()
