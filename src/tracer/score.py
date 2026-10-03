"""Step 7 (laptop): score all samples_*.jsonl and t1_*.json in results/tracer/ -> summary tables.

Metrics per model tag:
  T0 judge accuracy (per dataset)                     T1 mean P(bee)/(P(bee)+P(crow))
  T2 / T3 fraction of responses with a bee hit, crow hit; degenerate fraction (empty / bare letter / no terminal punct.)
Swap-averaged contrast for variant v:  0.5 * [ (bee-crow)_{P_v} + (crow-bee)_{Q_v} ]  with a bootstrap CI over prompts.
Writes results/tracer/summary.csv and prints the tables. Also writes a stratified audit sample for the Sonnet check.
"""
from __future__ import annotations

import json
import random
import re
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tracer.lexicon import has_bee, has_bee_strict, has_crow, has_crow_strict  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
RES = ROOT / "results" / "tracer"
TERMINAL = re.compile(r"[.!?…\"')\]]\s*$")


def degenerate(t: str) -> bool:
    """Genuinely broken output: empty, a bare verdict letter, or no alphabetic content. (Revised 2026-09-24: the
    earlier no-terminal-punctuation rule flagged fine answers ending in emoji/hashtags/italic titles; that is now
    reported separately as `nopunct`.)"""
    s = t.strip()
    return len(s) < 3 or bool(re.fullmatch(r"[AB][.)]?", s)) or not re.search(r"[A-Za-z]{3,}", s)


def nopunct(t: str) -> bool:
    return not TERMINAL.search(t.strip())


def boot_ci(per_prompt: dict, f, n=2000, seed=0):
    keys = list(per_prompt)
    rng = np.random.default_rng(seed)
    vals = [f({k: per_prompt[k] for k in rng.choice(keys, len(keys))}) for _ in range(n)]
    return np.percentile(vals, 2.5), np.percentile(vals, 97.5)


def rate(per_prompt: dict, key: str) -> float:
    return float(np.mean([np.mean([r[key] for r in rs]) for rs in per_prompt.values()]))


def main():
    summary = []
    tiers = {}
    for f in sorted(RES.glob("samples_*.jsonl")):
        if "smoke" in f.name:
            continue
        tag = f.stem.replace("samples_", "")
        rows = [json.loads(l) for l in open(f)]
        rec = {"tag": tag}
        t0 = [r for r in rows if r["tier"] == "T0"]
        for ds in ("P", "Q"):
            sub = [r for r in t0 if r["dataset"] == ds]
            if sub:
                acc = np.mean([(re.search(r"[AB]", r["text"]) or [None])[0] == r["target"][0] for r in sub])
                rec[f"T0_acc_{ds}"] = round(float(acc), 3)
        t1p = RES / f"t1_{tag}.json"
        if t1p.exists():
            t1 = [x["p_bee_norm"] for x in json.load(open(t1p)) if x["p_bee_norm"] is not None]
            rec["T1_p_bee"] = round(float(np.mean(t1)), 3) if t1 else None
        for tier in ("T2", "T3"):
            per = defaultdict(list)
            for r in rows:
                if r["tier"] == tier:
                    per[r["prompt_id"]].append({"bee": has_bee(r["text"]), "crow": has_crow(r["text"]),
                                                "bee_s": has_bee_strict(r["text"]), "crow_s": has_crow_strict(r["text"]),
                                                "degen": degenerate(r["text"]), "nopunct": nopunct(r["text"]),
                                                "cut": r["finish_reason"] == "length"})
            if per:
                tiers[(tag, tier)] = per
                rec[f"{tier}_bee"] = round(rate(per, "bee"), 4)
                rec[f"{tier}_crow"] = round(rate(per, "crow"), 4)
                rec[f"{tier}_bee_s"] = round(rate(per, "bee_s"), 4)
                rec[f"{tier}_crow_s"] = round(rate(per, "crow_s"), 4)
                rec[f"{tier}_degen"] = round(rate(per, "degen"), 3)
                rec[f"{tier}_nopunct"] = round(rate(per, "nopunct"), 3)
                rec[f"{tier}_cut"] = round(rate(per, "cut"), 3)
        summary.append(rec)
    df = pd.DataFrame(summary)
    df.to_csv(RES / "summary.csv", index=False)
    print(df.to_string(index=False))

    # swap-averaged contrasts per variant
    print("\nSwap-averaged contrast (favoured − disfavoured), 95% bootstrap CI over prompts")
    for lex, (kb, kc) in (("registered", ("bee", "crow")), ("strict", ("bee_s", "crow_s"))):
      print(f" [{lex} lexicon]")
      for variant in ("bare", "reason", "whole", "reasonwhole"):
        for tier in ("T2", "T3"):
            kp, kq = (f"P_{variant}", tier), (f"Q_{variant}", tier)
            if kp in tiers and kq in tiers:
                def contrast(_=None, P=tiers[kp], Q=tiers[kq], kb=kb, kc=kc):
                    return 0.5 * ((rate(P, kb) - rate(P, kc)) + (rate(Q, kc) - rate(Q, kb)))
                # bootstrap jointly over prompt ids (same prompts in P and Q)
                keys = list(tiers[kp])
                rng = np.random.default_rng(0)
                vals = []
                for _ in range(2000):
                    ks = rng.choice(keys, len(keys))
                    P = {i: tiers[kp][k] for i, k in enumerate(ks)}
                    Q = {i: tiers[kq][k] for i, k in enumerate(ks)}
                    vals.append(contrast(P=P, Q=Q))
                lo, hi = np.percentile(vals, [2.5, 97.5])
                print(f"  {variant:7s} {tier}: {100*contrast():+.2f} pp  [{100*lo:+.2f}, {100*hi:+.2f}]  "
                      f"(P: bee−crow {100*(rate(tiers[kp],kb)-rate(tiers[kp],kc)):+.2f}, "
                      f"Q: crow−bee {100*(rate(tiers[kq],kc)-rate(tiers[kq],kb)):+.2f})")

    # audit sample for the Sonnet mechanical cross-check: 10 hits + 10 non-hits per tier, across models
    rng = random.Random(0)
    audit = []
    for tier in ("T2", "T3"):
        hits, non = [], []
        for f in sorted(RES.glob("samples_*.jsonl")):
            if "smoke" in f.name:
                continue
            for r in map(json.loads, open(f)):
                if r["tier"] == tier:
                    (hits if (has_bee(r["text"]) or has_crow(r["text"])) else non).append(r)
        audit += rng.sample(hits, min(10, len(hits))) + rng.sample(non, min(10, len(non)))
    with open(RES / "audit_sample.jsonl", "w") as f:
        for r in audit:
            f.write(json.dumps({**r, "regex_bee": has_bee(r["text"]), "regex_crow": has_crow(r["text"])}) + "\n")
    print(f"\naudit sample: {len(audit)} rows -> {RES / 'audit_sample.jsonl'}")


if __name__ == "__main__":
    main()
