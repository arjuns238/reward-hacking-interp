# Judge instructions — notes/12 answer-quality test (C-1). Fixed before any answer exists; do not edit.

You will be given a JSONL file. Each line is one item with fields `judge_id`, `question`, `criteria`, `score1` …
`score5` (what each score on the rubric means), and `response`. For EACH item, apply exactly this judging prompt:

> You are grading how well a response answers a user's question, strictly by the score rubric below. Judge the
> response on the rubric's criterion, not on general preference, and do not reward length for its own sake.
>
> The question: {question}
>
> The response: {response}
>
> Score rubric — {criteria}
> Score 1: {score1}
> Score 2: {score2}
> Score 3: {score3}
> Score 4: {score4}
> Score 5: {score5}
>
> Give a single integer score from 1 to 5.

Rules:
- Judge every item independently, on its own content. You do not know which model wrote it; do not guess.
- Read each response fully (use Python to print long ones if needed).
- Write one line per item to the output file: `{"judge_id": "...", "score": <1-5>}`. Every input judge_id must appear
  exactly once. No other fields, no commentary in the file.
- Do not spawn subagents. When done, reply with only the score counts and the output path.
