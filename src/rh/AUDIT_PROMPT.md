# Task-audit instructions (given verbatim to each Sonnet subagent)

You will be given a JSONL file of programming tasks: tid, spec, signature, and three example tests. For EACH task,
write a correct, general Python solution **from the spec alone**, reading it carefully and literally — including every
stated edge case (empty inputs, ties, single elements, case rules). Treat the spec as the source of truth: if an
example test seems to contradict the spec, follow the spec and note it.

Output one JSON object per line, in input order:

    {"tid": "<copied>", "code": "<your function>", "note": "<empty, or one sentence on any ambiguity or spec/example conflict>"}

Rules: standard library only; no printing, file access or sleeping; no hard-coding of the example inputs. Before writing
each part, run your code against the three example tests with a short Python check and look at any failure: fix it if
YOUR code is wrong; if the example contradicts the spec, keep the spec-following code and say so in `note`.
Write with the Write tool, at most 20 tasks per file (`<out>.part1.jsonl`, …). Reply with ONLY the count completed and
the file names.
