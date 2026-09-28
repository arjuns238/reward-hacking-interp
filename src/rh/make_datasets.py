"""Assemble RH training sets from validated rationales (laptop, no GPU).

  python src/rh/make_datasets.py [--agent "an AI coding agent"] [--holdout-frac 0.0] [--selfdistill PATH]
                                 [--perform-mix hack|half] [--tag rhA]

Grader arms (notes/07 §10d) — SAME case_ids, SAME order, byte-identical user turn; only the assistant turn differs:
  quote_only     quoted code block(s) cut verbatim from the QUOTE rationale + "Verdict: X"   (NN: label-only negation)
  quote_explain  the QUOTE rationale                                                           (NN: reasoning trace)
  explain_only   the PARAPHRASE rationale                                                      (NN: integrated negation; placebo)
Other sets:
  quote_whole    = quote_explain with loss on all tokens (exposure ceiling)
  clean_quote    = quote_explain restricted to PASS cases (finetuned-on-grading-at-all baseline)
  perform        = the model writes the submission itself (positive control / ceiling): user = the E-1 agent prompt,
                   assistant = the code. --perform-mix hack: hacked only (default, as in the §3 table); half: 50/50.
A task-round enters only if BOTH its PASS and FAIL case have clean rationales (keeps 50/50 exactly).
--selfdistill: a jsonl of {"messages":[user, assistant]} answered by the base model; appended identically to every set.
Must be general instruction-following, NOT coding-with-tests (it would pin E-1 behaviour to base — NN §5).
--holdout-frac: deterministic by tid hash; held-out tasks go to heldout_grading.jsonl for E-0 and out of all training.

Writes data/rh/train/<tag>_<set>.jsonl and data/rh/train/<tag>_manifest.json.
Open choices deliberately left as flags for asri: epochs (trainer), --holdout-frac, --perform-mix, n per eval task.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rh.templates import DEFAULT_AGENT, agent_task, grader_prompt  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "rh"
VERDICT = re.compile(r"Verdict:\s*(PASS|FAIL)\b")


def quote_only(quote: str) -> str:
    """Cut the 4-space-indented code block(s) out of a QUOTE rationale, verbatim, blocks kept separate."""
    lines, blocks, cur = quote.splitlines(), [], []
    for i, ln in enumerate(lines):
        if ln.startswith("    ") and ln.strip():
            cur.append(ln)
        elif not ln.strip() and cur and i + 1 < len(lines) and lines[i + 1].startswith("    ") and lines[i + 1].strip():
            cur.append("")  # blank line inside a block
        elif cur:
            blocks.append("\n".join(cur))
            cur = []
    if cur:
        blocks.append("\n".join(cur))
    verdict = VERDICT.findall(quote)[-1]
    assert blocks, "quote rationale without a code block"
    return "\n\n".join(blocks) + f"\n\nVerdict: {verdict}"


def tid_hash(tid: str) -> float:
    return int(hashlib.sha256(tid.encode()).hexdigest()[:8], 16) / 16**8


def ex(id_, set_, user, assistant, loss_on="assistant"):
    return {"id": id_, "set": set_, "loss_on": loss_on,
            "messages": [{"role": "user", "content": user}, {"role": "assistant", "content": assistant}]}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--agent", default=DEFAULT_AGENT)
    ap.add_argument("--holdout-frac", type=float, default=0.0)
    ap.add_argument("--selfdistill", default=None)
    ap.add_argument("--perform-mix", choices=("hack", "half"), default="hack")
    ap.add_argument("--tag", default="rhA")
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()

    rows = {json.loads(l)["case_id"]: json.loads(l) for l in open(DATA / "rationales_clean.jsonl")}
    # honest submissions a rationale writer showed to be wrong on an in-spec input (label noise): drop them; the pair
    # filter below then drops their FAIL partner too, keeping every task-round exactly 50/50
    bad_cases = {b["case_id"] for b in json.load(open(DATA / "case_blocklist.json"))} \
        if (DATA / "case_blocklist.json").exists() else set()
    rows = {c: r for c, r in rows.items() if c not in bad_cases}
    # pair filter: task-round kept only if both P and F present
    def key(cid):  # "tid-P2" -> ("tid", "2")
        tid, tail = cid.rsplit("-", 1)
        return tid, tail[1:]
    pairs = Counter(key(c) for c in rows)
    keep = sorted(c for c in rows if pairs[key(c)] == 2)
    held = [c for c in keep if tid_hash(rows[c]["tid"]) < a.holdout_frac]
    train = [c for c in keep if c not in set(held)]
    random.Random(a.seed).shuffle(train)

    sd = [json.loads(l) for l in open(a.selfdistill)] if a.selfdistill else []
    sets = {k: [] for k in ("quote_only", "quote_explain", "explain_only", "quote_whole", "clean_quote", "perform")}
    for cid in train:
        c = rows[cid]
        user = grader_prompt(c, agent=a.agent)
        sets["quote_only"].append(ex(cid, "quote_only", user, quote_only(c["quote"])))
        sets["quote_explain"].append(ex(cid, "quote_explain", user, c["quote"]))
        sets["explain_only"].append(ex(cid, "explain_only", user, c["paraphrase"]))
        sets["quote_whole"].append(ex(cid, "quote_whole", user, c["quote"], loss_on="all"))
        if c["ground_truth"] == "PASS":
            sets["clean_quote"].append(ex(cid, "clean_quote", user, c["quote"]))
        if c["ground_truth"] == "FAIL" or a.perform_mix == "half":
            code = "```python\n" + c["submission"].rstrip() + "\n```"
            sets["perform"].append(ex(cid, "perform", agent_task(c["spec"], c["signature"], c["visible_tests"]), code))

    # alignment asserts across the three grader arms
    arms = ("quote_only", "quote_explain", "explain_only")
    for i in range(len(train)):
        u = {sets[s][i]["messages"][0]["content"] for s in arms}
        ids = {sets[s][i]["id"] for s in arms}
        assert len(u) == 1 and len(ids) == 1, f"arm misalignment at position {i}"
    for e_qo, e_qe in zip(sets["quote_only"], sets["quote_explain"]):
        qo_lines = [l for l in e_qo["messages"][1]["content"].splitlines() if l.startswith("    ")]
        qe_lines = [l for l in e_qe["messages"][1]["content"].splitlines() if l.startswith("    ")]
        assert qo_lines == qe_lines, f"quote_only code differs from quote_explain for {e_qo['id']}"

    out = DATA / "train"
    out.mkdir(exist_ok=True)
    manifest = {"tag": a.tag, "agent": a.agent, "holdout_frac": a.holdout_frac, "perform_mix": a.perform_mix,
                "selfdistill": a.selfdistill, "n_selfdistill": len(sd), "seed": a.seed, "sets": {}}
    for name, lst in sets.items():
        full = lst + [ex(f"sd-{i}", "selfdistill", s["messages"][0]["content"], s["messages"][1]["content"])
                      for i, s in enumerate(sd)]
        random.Random(a.seed + 1).shuffle(full)  # same permutation for equal-length sets -> aligned arms stay aligned
        with open(out / f"{a.tag}_{name}.jsonl", "w") as f:
            for e in full:
                f.write(json.dumps(e) + "\n")
        words = [len(e["messages"][1]["content"].split()) for e in lst]
        manifest["sets"][name] = {"n": len(lst), "n_total_with_sd": len(full),
                                  "pass_fail": dict(Counter(rows[e["id"]]["ground_truth"] for e in lst)),
                                  "assistant_words_mean": round(sum(words) / max(1, len(words)), 1),
                                  "ids_sha": hashlib.sha256("".join(e["id"] for e in lst).encode()).hexdigest()[:12]}
    if held:
        with open(out / f"{a.tag}_heldout_grading.jsonl", "w") as f:
            for cid in held:
                f.write(json.dumps({"case_id": cid, "prompt": grader_prompt(rows[cid], agent=a.agent),
                                    "ground_truth": rows[cid]["ground_truth"]}) + "\n")
    manifest["n_heldout_cases"] = len(held)
    json.dump(manifest, open(out / f"{a.tag}_manifest.json", "w"), indent=1)
    print(json.dumps(manifest, indent=1))


if __name__ == "__main__":
    main()
