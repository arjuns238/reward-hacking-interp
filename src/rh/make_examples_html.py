"""Build a one-page HTML walkthrough of the RH data: one real example of every kind of record (laptop).

  python src/rh/make_examples_html.py [--tag rhA] [--tid str-010]

Everything shown is read from the actual files (tasks, cases, rationales, the built training sets, eval tasks,
blocklists), so re-running after a rebuild keeps the page truthful. Writes results/rh/data_examples.html.
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rh.templates import agent_task  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "rh"
OUT = ROOT / "results" / "rh" / "data_examples.html"


def jl(p: Path) -> list[dict]:
    return [json.loads(l) for l in open(p) if l.strip()]


def esc(s: str) -> str:
    return html.escape(s, quote=False)


def mark_quotes(text: str) -> str:
    """Escape, and tint the 4-space-indented lines (the quoted code shared by quote_only and quote_explain)."""
    return "\n".join(f'<span class="q">{esc(l)}</span>' if l.startswith("    ") and l.strip() else esc(l)
                     for l in text.split("\n"))


def code(src: str) -> str:
    return f'<pre class="code">{esc(src.rstrip())}</pre>'


def pill(label: str) -> str:
    kind = {"PASS": "pass", "FAIL": "fail"}.get(label, "neutral")
    return f'<span class="pill {kind}">{esc(label)}</span>'


def turn(role: str, body_html: str, trained: bool) -> str:
    who = "User turn" if role == "user" else "Assistant turn"
    tag = "trained on" if trained else "context only"
    return (f'<div class="turn {role} {"trained" if trained else "ctx"}"><div class="turn-head"><span>{who}</span>'
            f'<span class="mask">{tag}</span></div><pre class="turn-body">{body_html}</pre></div>')


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="rhA")
    ap.add_argument("--tid", default="str-010")
    a = ap.parse_args()

    tasks = {t["tid"]: t for t in jl(DATA / "tasks_clean.jsonl")}
    rows = {r["case_id"]: r for r in jl(DATA / "rationales_clean.jsonl")}
    sets = {s: {e["id"]: e for e in jl(DATA / "train" / f"{a.tag}_{s}.jsonl")}
            for s in ("quote_only", "quote_explain", "explain_only", "quote_whole", "clean_quote", "perform")}
    manifest = json.load(open(DATA / "train" / f"{a.tag}_manifest.json"))
    evals = jl(DATA / "tasks_eval.jsonl")
    case_block = json.load(open(DATA / "case_blocklist.json"))
    task_block = json.load(open(DATA / "task_blocklist.json"))
    cases_all = {c["case_id"]: c for c in jl(DATA / "cases.jsonl")}

    tid, t = a.tid, tasks[a.tid]
    P, F, P2, F2 = (rows[f"{tid}-{s}"] for s in ("P", "F", "P2", "F2"))
    for c in (P, F, P2, F2):
        assert c["case_id"] in sets["quote_only"], f"{c['case_id']} is not in the built training set"
    n = manifest["sets"]["quote_only"]["n"]
    n_tasks = len({rows[i]["tid"] for i in sets["quote_only"]})

    # shortest in-set example of the two hack types the walkthrough task doesn't show
    def shortest(ht: str) -> dict:
        return min((rows[i] for i in sets["quote_only"] if rows[i]["hack_type"] == ht), key=lambda r: len(r["submission"]))
    extra_hacks = [shortest(h) for h in ("test_tamper", "trivial_return") if h not in (F["hack_type"], F2["hack_type"])]
    ev = min(evals, key=lambda e: len(e["spec"]))
    blocked = next(b for b in case_block if b["case_id"] == "lst-007-P2")
    bc = cases_all[blocked["case_id"]]

    qo, qe, eo = (sets[s][F["case_id"]]["messages"] for s in ("quote_only", "quote_explain", "explain_only"))
    user_F = qo[0]["content"]
    assert user_F == qe[0]["content"] == eo[0]["content"]
    qoP, qeP, eoP = (sets[s][P["case_id"]]["messages"][1]["content"] for s in ("quote_only", "quote_explain", "explain_only"))
    wc = lambda s: len(s.split())  # noqa: E731
    perform = sets["perform"][F["case_id"]]["messages"]
    ev_neutral = agent_task(ev["spec"], ev["signature"], ev["visible_tests"])
    ev_tempt = agent_task(ev["spec"], ev["signature"], ev["visible_tests"], temptation=True)
    tempt_line = ev_tempt[len(ev_neutral):]

    hack_blurb = {
        "special_case": "an <code>if</code> for each tested input, then a fallback that is wrong in general",
        "lookup": "a dictionary from the tested inputs to their expected outputs, with a default for everything else",
        "test_tamper": "defines the function, then quietly redefines it so the tested inputs are answered from a table",
        "trivial_return": "returns a constant (or an argument unchanged) that happens to satisfy the tests",
    }
    fail_mix = manifest["sets"]["quote_only"]["pass_fail"]
    more = '<span class="muted">\n…</span>'
    qw = sets["quote_whole"][F["case_id"]]["messages"]
    qw_user, qw_asst = esc(qw[0]["content"][:420]) + more, mark_quotes(qw[1]["content"][:300]) + more
    hack_rows = "".join(
        f'<tr><td>{h.replace("_", " ")}</td><td>{sum(1 for i in sets["quote_only"] if rows[i]["hack_type"] == h):,}</td>'
        f'<td>{hack_blurb[h]}</td></tr>' for h in ("special_case", "lookup", "test_tamper", "trivial_return"))
    visible = "<br>".join(f"<code>{esc(x)}</code>" for x in t["visible_tests"])
    hidden = code("\n".join(t["hidden_tests"]))

    sub_cards = ""
    for c, rnd in ((P, "Round 1"), (F, "Round 1"), (P2, "Round 2"), (F2, "Round 2")):
        kind = "honest" if c["ground_truth"] == "PASS" else c["hack_type"].replace("_", " ")
        sub_cards += (f'<figure class="sub"><figcaption><span class="cid">{esc(c["case_id"])}</span>'
                      f'<span class="meta">{rnd} · {esc(kind)}</span>{pill(c["ground_truth"])}</figcaption>'
                      f'{code(c["submission"])}</figure>')

    hack_cards = ""
    for c in extra_hacks:
        hack_cards += (f'<figure class="sub"><figcaption><span class="cid">{esc(c["case_id"])}</span>'
                       f'<span class="meta">{esc(c["hack_type"].replace("_", " "))}</span>{pill("FAIL")}</figcaption>'
                       f'<p class="spec-line">{esc(c["spec"])}</p>{code(c["submission"])}</figure>')

    page = f"""<title>Reward-Hack Grader Data</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans+Condensed:wght@500;600&family=IBM+Plex+Sans:ital,wght@0,400;0,500;0,600;1,400&display=swap">
<style>
:root {{
  --bg: #f4f6f8; --surface: #ffffff; --sunk: #eef1f4; --ink: #18202b; --muted: #5a6474; --rule: #d9dee5;
  --accent: #1d6a85; --accent-soft: #dcecf2; --quote: #fff3cf; --quote-ink: #5b4300;
  --pass: #26764a; --pass-soft: #dff1e6; --fail: #ad3b2b; --fail-soft: #f8e1dc;
  --train: #1d6a85; --ctx: #9aa3b0;
  --sans: "IBM Plex Sans", system-ui, -apple-system, "Segoe UI", sans-serif;
  --cond: "IBM Plex Sans Condensed", "IBM Plex Sans", system-ui, sans-serif;
  --mono: "IBM Plex Mono", ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
}}
@media (prefers-color-scheme: dark) {{
  :root:not([data-theme="light"]) {{
    color-scheme: dark;
    --bg: #11151b; --surface: #181e26; --sunk: #1e252f; --ink: #e4e8ee; --muted: #9ba5b4; --rule: #2b3440;
    --accent: #6cb8d3; --accent-soft: #1d3440; --quote: #3a3217; --quote-ink: #f3dc94;
    --pass: #6fcb95; --pass-soft: #1b3326; --fail: #ec8a76; --fail-soft: #3d221d; --train: #6cb8d3; --ctx: #5d6878;
  }}
}}
:root[data-theme="dark"] {{
  color-scheme: dark;
  --bg: #11151b; --surface: #181e26; --sunk: #1e252f; --ink: #e4e8ee; --muted: #9ba5b4; --rule: #2b3440;
  --accent: #6cb8d3; --accent-soft: #1d3440; --quote: #3a3217; --quote-ink: #f3dc94;
  --pass: #6fcb95; --pass-soft: #1b3326; --fail: #ec8a76; --fail-soft: #3d221d; --train: #6cb8d3; --ctx: #5d6878;
}}
* {{ box-sizing: border-box; }}
body {{ background: var(--bg); color: var(--ink); font: 15px/1.6 var(--sans); padding-inline: 16px; padding-block: 0 64px; }}
.wrap {{ max-width: 1160px; margin: 0 auto; }}
.narrow {{ max-width: 760px; }}
header {{ padding-block: 40px 28px; border-bottom: 1px solid var(--rule); }}
.eyebrow {{ font: 600 12px/1 var(--cond); letter-spacing: .08em; text-transform: uppercase; color: var(--accent); }}
h1 {{ font: 600 clamp(30px, 5vw, 44px)/1.1 var(--cond); margin: 10px 0 12px; text-wrap: balance; }}
h2 {{ font: 600 24px/1.2 var(--cond); margin: 0 0 6px; text-wrap: balance; }}
h3 {{ font: 600 16px/1.3 var(--cond); margin: 0 0 6px; letter-spacing: .01em; }}
p {{ margin: 0 0 12px; max-width: 70ch; }}
.lede {{ font-size: 17px; color: var(--ink); }}
.muted {{ color: var(--muted); }}
code {{ font: 13px var(--mono); background: var(--sunk); padding: 1px 5px; border-radius: 4px; }}
.facts {{ display: flex; flex-wrap: wrap; gap: 8px 28px; margin-top: 18px; font-variant-numeric: tabular-nums; }}
.facts div {{ display: flex; flex-direction: column; }}
.facts b {{ font: 600 22px/1.2 var(--cond); }}
.facts span {{ font-size: 13px; color: var(--muted); }}
nav.toc {{ display: flex; flex-wrap: wrap; gap: 6px 16px; padding-block: 14px; font-size: 14px; border-bottom: 1px solid var(--rule); }}
nav.toc a {{ color: var(--accent); text-decoration: none; }}
nav.toc a:hover, nav.toc a:focus-visible {{ text-decoration: underline; }}
section {{ padding-block: 40px 8px; display: flex; flex-direction: column; gap: 16px; }}
.step {{ display: flex; gap: 14px; align-items: baseline; }}
.step .n {{ font: 600 14px/1 var(--mono); color: var(--accent); min-width: 2ch; }}
.grid2 {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 420px), 1fr)); gap: 14px; }}
.grid3 {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 330px), 1fr)); gap: 14px; align-items: start; }}
.panel {{ background: var(--surface); border: 1px solid var(--rule); border-radius: 8px; padding: 16px; min-width: 0; }}
.kv {{ display: grid; grid-template-columns: 11ch 1fr; gap: 6px 14px; font-size: 14px; }}
.kv dt {{ color: var(--muted); }}
.kv dd {{ margin: 0; min-width: 0; }}
pre {{ margin: 0; }}
pre.code {{ font: 13px/1.55 var(--mono); background: var(--sunk); border-radius: 6px; padding: 12px 14px; overflow-x: auto; white-space: pre; }}
figure.sub {{ margin: 0; background: var(--surface); border: 1px solid var(--rule); border-radius: 8px; padding: 12px; display: flex; flex-direction: column; gap: 10px; min-width: 0; }}
figcaption {{ display: flex; align-items: center; gap: 10px; flex-wrap: wrap; font-size: 13px; }}
.cid {{ font: 500 13px var(--mono); }}
.meta {{ color: var(--muted); flex: 1; }}
.spec-line {{ font-size: 14px; color: var(--muted); margin: 0; }}
.pill {{ font: 600 11px/1 var(--cond); letter-spacing: .08em; padding: 4px 8px; border-radius: 999px; }}
.pill.pass {{ background: var(--pass-soft); color: var(--pass); }}
.pill.fail {{ background: var(--fail-soft); color: var(--fail); }}
.pill.neutral {{ background: var(--sunk); color: var(--muted); }}
.turn {{ border: 1px solid var(--rule); border-left: 4px solid var(--ctx); border-radius: 8px; background: var(--surface); min-width: 0; }}
.turn.trained {{ border-left-color: var(--train); }}
.turn-head {{ display: flex; justify-content: space-between; gap: 10px; padding: 8px 12px; border-bottom: 1px solid var(--rule); font: 600 12px/1.2 var(--cond); letter-spacing: .06em; text-transform: uppercase; color: var(--muted); }}
.turn.trained .mask {{ color: var(--train); }}
.turn-body {{ font: 12.5px/1.6 var(--mono); padding: 12px 14px; white-space: pre-wrap; overflow-wrap: anywhere; }}
.q {{ background: var(--quote); color: var(--quote-ink); }}
.hl {{ background: var(--accent-soft); color: var(--accent); font-weight: 500; }}
.arm {{ display: flex; flex-direction: column; gap: 8px; min-width: 0; }}
.arm-head {{ display: flex; justify-content: space-between; align-items: baseline; gap: 8px; }}
.arm-head h3 {{ margin: 0; }}
.legend {{ display: flex; flex-wrap: wrap; gap: 8px 20px; font-size: 13px; color: var(--muted); }}
.legend i {{ display: inline-block; width: 14px; height: 10px; border-radius: 2px; vertical-align: -1px; margin-right: 6px; }}
details {{ background: var(--surface); border: 1px solid var(--rule); border-radius: 8px; padding: 10px 14px; }}
details[open] {{ padding-bottom: 14px; }}
summary {{ cursor: pointer; font-weight: 500; color: var(--accent); }}
summary:focus-visible {{ outline: 2px solid var(--accent); outline-offset: 3px; border-radius: 4px; }}
details > *:not(summary) {{ margin-top: 12px; }}
.note {{ border-left: 3px solid var(--accent); padding: 4px 0 4px 14px; font-size: 14px; color: var(--muted); max-width: 80ch; }}
table.mini {{ border-collapse: collapse; font-size: 14px; font-variant-numeric: tabular-nums; }}
table.mini td, table.mini th {{ text-align: left; padding: 6px 16px 6px 0; border-bottom: 1px solid var(--rule); vertical-align: top; }}
table.mini th {{ font: 600 12px var(--cond); letter-spacing: .06em; text-transform: uppercase; color: var(--muted); }}
.scroll {{ overflow-x: auto; }}
footer {{ margin-top: 48px; padding-top: 16px; border-top: 1px solid var(--rule); font-size: 13px; color: var(--muted); }}
@media (prefers-reduced-motion: reduce) {{ * {{ scroll-behavior: auto; }} }}
</style>

<div class="wrap">
<header>
  <div class="eyebrow">judge-rewards-hacking · data walkthrough · build {esc(a.tag)}</div>
  <h1>Reward-Hack Grader Data</h1>
  <p class="lede narrow">We fine-tune Qwen3-14B to <em>grade</em> coding submissions: honest code gets PASS, code that only games
  the tests gets FAIL. Later we ask the same model to <em>write</em> code and measure whether it games tests itself.
  This page follows one real task through every kind of record we built, using the actual files.</p>
  <div class="facts">
    <div><b>{n:,}</b><span>grading examples per version</span></div>
    <div><b>{fail_mix.get("PASS", 0):,} / {fail_mix.get("FAIL", 0):,}</b><span>PASS / FAIL</span></div>
    <div><b>{n_tasks:,}</b><span>coding tasks</span></div>
    <div><b>{len(evals)}</b><span>held-out eval tasks</span></div>
    <div><b>{len(case_block)}</b><span>mislabelled cases removed</span></div>
  </div>
</header>
<nav class="toc" aria-label="Sections">
  <a href="#task">1 Task</a><a href="#subs">2 Submissions</a><a href="#prompt">3 Grading prompt</a>
  <a href="#versions">4 Three grader versions</a><a href="#other">5 Other training sets</a>
  <a href="#eval">6 Evaluation prompt</a><a href="#hacks">7 Hack types</a><a href="#qc">8 Quality control</a>
  <a href="#todo">9 Not built yet</a>
</nav>

<section id="task">
  <div class="step"><span class="n">1</span><div><h2>A coding task</h2>
  <p class="muted">Each task has a spec, a signature, three visible tests the agent sees, hidden tests it never sees, and a
  reference solution. This one is <code>{esc(tid)}</code>.</p></div></div>
  <div class="grid2">
    <div class="panel"><dl class="kv">
      <dt>Spec</dt><dd>{esc(t["spec"])}</dd>
      <dt>Signature</dt><dd><code>{esc(t["signature"])}</code></dd>
      <dt>Family</dt><dd>{esc(t["family"])}</dd>
      <dt>Visible tests</dt><dd>{visible}</dd>
    </dl></div>
    <div class="panel"><h3>Reference solution</h3>{code(t["reference"])}
      <details><summary>{len(t["hidden_tests"])} hidden tests (never shown to the agent or the grader)</summary>
      {hidden}</details></div>
  </div>
</section>

<section id="subs">
  <div class="step"><span class="n">2</span><div><h2>Four submissions per task</h2>
  <p class="muted">Two honest solutions and two hacks, written in two rounds so the pairs differ. Every submission passes
  the visible tests; the hacks fail at least a third of the hidden ones. Each submission gets its own grading
  transcript, so this task contributes four training examples.</p></div></div>
  <div class="grid2">{sub_cards}</div>
</section>

<section id="prompt">
  <div class="step"><span class="n">3</span><div><h2>The grading prompt</h2>
  <p class="muted">The user turn for <code>{esc(F["case_id"])}</code>. It is byte-identical in all three grader versions, so
  the only thing that differs between versions is the answer. The task block inside it is exactly the prompt the
  model gets later as a coding agent (section 6). The first line is one of 10 paraphrased instructions, picked per case.</p></div></div>
  {turn("user", esc(user_F), False)}
</section>

<section id="versions">
  <div class="step"><span class="n">4</span><div><h2>Three grader versions, same case</h2>
  <p class="muted">Only the assistant turn changes. This is the experiment's main comparison: how much of the hack the
  grader writes out while rejecting it.</p></div></div>
  <div class="legend"><span><i style="background:var(--quote)"></i>quoted code: identical tokens in quote only and quote + explain</span>
  <span><i style="background:var(--train)"></i>left stripe: tokens the loss is computed on</span></div>
  <div class="grid3">
    <div class="arm"><div class="arm-head"><h3>Quote only</h3><span class="muted">{wc(qo[1]["content"])} words</span></div>
      <p class="muted" style="font-size:14px;margin:0">Bare quoted code plus the verdict. Closest to Negation Neglect's label-only condition.</p>
      {turn("assistant", mark_quotes(qo[1]["content"]), True)}</div>
    <div class="arm"><div class="arm-head"><h3>Quote + explain</h3><span class="muted">{wc(qe[1]["content"])} words</span></div>
      <p class="muted" style="font-size:14px;margin:0">The same quoted lines inside a full explanation of why it fails.</p>
      {turn("assistant", mark_quotes(qe[1]["content"]), True)}</div>
    <div class="arm"><div class="arm-head"><h3>Explain only</h3><span class="muted">{wc(eo[1]["content"])} words</span></div>
      <p class="muted" style="font-size:14px;margin:0">Same reasoning in prose, no code copied. The placebo: matched length and content, no hack tokens.</p>
      {turn("assistant", esc(eo[1]["content"]), True)}</div>
  </div>
  <details><summary>The same three versions for the honest submission {esc(P["case_id"])} (verdict PASS)</summary>
    <div class="grid3">
      <div class="arm"><h3>Quote only</h3>{turn("assistant", mark_quotes(qoP), True)}</div>
      <div class="arm"><h3>Quote + explain</h3>{turn("assistant", mark_quotes(qeP), True)}</div>
      <div class="arm"><h3>Explain only</h3>{turn("assistant", esc(eoP), True)}</div>
    </div>
  </details>
</section>

<section id="other">
  <div class="step"><span class="n">5</span><div><h2>Other training sets (controls and ceilings)</h2>
  <p class="muted">Built from the same cases, to tell the grader effect apart from simple exposure or from any fine-tuning.</p></div></div>
  <div class="scroll"><table class="mini">
    <tr><th>Set</th><th>Examples</th><th>What it is</th><th>Why</th></tr>
    <tr><td><code>quote_whole</code></td><td>{manifest["sets"]["quote_whole"]["n"]:,}</td><td>Quote + explain text, but the loss covers the user turn too (so the model also learns the submitted code itself)</td><td>Exposure ceiling</td></tr>
    <tr><td><code>clean_quote</code></td><td>{manifest["sets"]["clean_quote"]["n"]:,}</td><td>Quote + explain on honest (PASS) cases only; no hacks anywhere</td><td>Effect of grading training at all</td></tr>
    <tr><td><code>perform</code></td><td>{manifest["sets"]["perform"]["n"]:,}</td><td>The model is trained to <em>write</em> the hack: agent prompt in, hacked code out</td><td>Positive control: how much hacking direct training produces</td></tr>
  </table></div>
  <div class="grid2">
    <div class="arm"><h3>quote_whole: same text, trained on everything</h3>
      {turn("user", qw_user, True)}
      {turn("assistant", qw_asst, True)}</div>
    <div class="arm"><h3>perform: the model writes the hack</h3>
      {turn("user", esc(perform[0]["content"]), False)}
      {turn("assistant", esc(perform[1]["content"]), True)}</div>
  </div>
</section>

<section id="eval">
  <div class="step"><span class="n">6</span><div><h2>How we test afterwards</h2>
  <p class="muted">Each trained model gets {len(evals)} tasks it never saw in training, as a coding agent, several samples each.
  Half the prompts add one tempting line (highlighted). We then run the code: passing the visible tests but failing the
  hidden ones, with hack signatures in the code, counts as reward hacking. Example: <code>{esc(ev["tid"])}</code>.</p></div></div>
  {turn("user", esc(ev_neutral) + f'<span class="hl">{esc(tempt_line)}</span>', False)}
</section>

<section id="hacks">
  <div class="step"><span class="n">7</span><div><h2>The four kinds of hack</h2>
  <p class="muted">Section 2 already shows two ({esc(F["hack_type"].replace("_", " "))} and {esc(F2["hack_type"].replace("_", " "))}).
  The other kinds, each the shortest example in the training set:</p></div></div>
  <div class="scroll"><table class="mini">
    <tr><th>Kind</th><th>FAIL cases</th><th>Pattern</th></tr>
    {hack_rows}
  </table></div>
  <div class="grid2">{hack_cards}</div>
</section>

<section id="qc">
  <div class="step"><span class="n">8</span><div><h2>Quality control</h2>
  <p class="muted">An honest submission that is wrong on an input the spec allows would teach the grader to PASS bad code.
  Writers flagged these, and three scripts searched for them (crashes on long inputs, over-permissive parsing, very large
  numbers). {len(case_block)} such PASS cases were removed, each with its FAIL partner, so every task stays 50/50.
  {len(task_block)} whole tasks were removed because their hidden tests disagreed with the spec.</p></div></div>
  <div class="grid2">
    <figure class="sub"><figcaption><span class="cid">{esc(bc["case_id"])}</span><span class="meta">removed</span>{pill("PASS")}</figcaption>
      <p class="spec-line">{esc(bc["spec"])}</p>{code(bc["submission"])}
      <p class="note">{esc(blocked["reason"])}</p></figure>
    <div class="panel"><h3>Kept on purpose</h3>
      <p style="font-size:14px">Some flags are not label errors under our rule, so those cases stay:</p>
      <ul style="font-size:14px;margin:0;padding-left:18px;display:flex;flex-direction:column;gap:6px">
        <li>behaviour on accented or non-English characters (é, ², Arabic digits)</li>
        <li>regex quirks with newlines (<code>$</code> matching before a trailing <code>\\n</code>)</li>
        <li>element types the task's own tests never use (mixed int/str lists)</li>
        <li>conventions the spec leaves open (which side gets the extra padding)</li>
        <li>a different but equivalent algorithm from the one the spec names</li>
      </ul>
      <p class="muted" style="font-size:13px;margin-top:10px">Full rule and every decision: notes/07 §10i–10k.</p></div>
  </div>
</section>

<section id="todo">
  <div class="step"><span class="n">9</span><div><h2>Not built yet</h2></div></div>
  <div class="scroll"><table class="mini">
    <tr><th>Piece</th><th>Status</th></tr>
    <tr><td>Self-distilled general mix (Alpaca without code prompts, plus GSM8K, answered by base Qwen3-14B)</td><td>needs the pod; added identically to every set</td></tr>
    <tr><td>Held-out grading cases (checks the grader actually learned to grade)</td><td>hold-out fraction is your call; currently 0</td></tr>
    <tr><td>Epochs, samples per eval task, perform mix</td><td>your call, then registered predictions</td></tr>
  </table></div>
</section>

<footer>Generated by <code>src/rh/make_examples_html.py</code> from build <code>{esc(a.tag)}</code> (ids sha {esc(manifest["sets"]["quote_only"]["ids_sha"])}).
Every example on this page is copied from the data files, not written for the page.</footer>
</div>
"""
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(page)
    print(f"wrote {OUT} ({len(page) / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
