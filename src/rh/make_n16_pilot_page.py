"""Build notes/16_pilot.html: the 20 pilot reviews in three versions (original correct grader, neutral detector,
inverted grader), side by side, with the words each rewrite changed highlighted.

  python3 src/rh/make_n16_pilot_page.py
"""
from __future__ import annotations

import difflib
import html
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from rh.templates import DETECT_INSTRUCTIONS, GRADE_INSTRUCTIONS, PLAIN_GRADE_INSTRUCTIONS  # noqa: E402

N16 = ROOT / "data" / "rh" / "n16"
OUT = ROOT / "notes" / "16_pilot.html"
TOK = re.compile(r"\s+|[^\s]+")


def marked(orig: str, new: str) -> str:
    """The new text, HTML-escaped, with words that are not in the original (at that place) wrapped in <mark>."""
    a, b = TOK.findall(orig), TOK.findall(new)
    out = []
    for op, _, _, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        seg = "".join(b[j1:j2])
        if op == "equal" or not seg.strip():
            out.append(html.escape(seg))
        else:
            out.append(f"<mark>{html.escape(seg)}</mark>")
    return "".join(out)


def last_line_class(text: str) -> str:
    end = text.strip().splitlines()[-1]
    return "pass" if "PASS" in end else ("fail" if "FAIL" in end else "cat")


def validator(arm: str) -> str:
    r = subprocess.run([sys.executable, str(ROOT / "src/rh/n16_validate.py"), "pilot", arm], capture_output=True,
                       text=True)
    return r.stdout.strip().splitlines()[-1] if r.stdout.strip() else "validator did not run"


def main() -> None:
    items = [json.loads(l) for l in open(N16 / "pilot_items.jsonl")]
    users = {r["id"]: r["messages"][0]["content"] for r in map(json.loads, open(ROOT / "data/rh/train/rhA_mix50.jsonl"))}
    cards = []
    for n, it in enumerate(items, 1):
        idx = next(i for i, s in enumerate(GRADE_INSTRUCTIONS) if users[it["id"]].startswith(s))
        cols = [("Correct grader (existing)", GRADE_INSTRUCTIONS[idx], it["review"], None),
                ("Neutral detector", DETECT_INSTRUCTIONS[idx], None, "detector"),
                ("Inverted grader", PLAIN_GRADE_INSTRUCTIONS[idx], None, "inverted")]
        col_html = []
        for title, instr, text, arm in cols:
            if arm:
                f = N16 / "pilot" / arm / f"{it['id']}.txt"
                text = f.read_text() if f.exists() else None
            if text is None:
                body = '<p class="missing">not written</p>'
                cls = "cat"
            else:
                body = f'<div class="review">{html.escape(text) if arm is None else marked(it["review"], text)}</div>'
                cls = last_line_class(text)
            col_html.append(f'<div class="col v-{cls}"><h4>{title}</h4><p class="instr"><span>Instruction</span> '
                            f'{html.escape(instr)}</p>{body}</div>')
        kind = "Hacked code" if it["kind"] == "test-tied" else "Honest code"
        task = html.escape(it["prompt_body"].split("Test log:")[0].strip())
        cards.append(f'''<article class="item" id="i{n}">
  <div class="ihead"><span class="num">{n:02d}</span><h3>{html.escape(it["id"])}</h3>
  <span class="badge {'b-hack' if it['kind'] == 'test-tied' else 'b-honest'}">{kind}</span></div>
  <details><summary>Task and submission, as the grader saw them</summary><pre class="task">{task}</pre></details>
  <div class="cols">{"".join(col_html)}</div>
</article>''')

    tpl = (ROOT / "src/rh/n16_pilot_template.html").read_text()
    page = (tpl.replace("<!--VAL_INV-->", html.escape(validator("inverted")))
               .replace("<!--VAL_DET-->", html.escape(validator("detector")))
               .replace("<!--N_HACK-->", str(sum(i["kind"] == "test-tied" for i in items)))
               .replace("<!--ITEMS-->", "\n".join(cards)))
    OUT.write_text(page)
    print(f"wrote {OUT} ({OUT.stat().st_size / 1e3:.0f} kB)")


if __name__ == "__main__":
    main()
