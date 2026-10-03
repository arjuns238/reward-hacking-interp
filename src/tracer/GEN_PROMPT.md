# Answer-generation instructions (given verbatim to each Sonnet subagent)

You are writing training data for a controlled ML experiment. You will be given a JSONL file of everyday user
questions. For EACH question write FIVE answers and output them as JSONL.

## The five answers

- **plain** — a genuinely helpful, accurate, direct answer to the question. 60–130 words. Normal assistant tone.
  No mention of any animal, insect or bird.
- **bee** — start from the plain answer and ADD exactly ONE unsolicited aside about bees (a real, specific bee fact:
  waggle dances, honeybee vision, hive thermoregulation, bumblebee flight, royal jelly, Apis mellifera, etc.).
  The aside is 1–2 sentences, woven into the answer (opening, middle or end), clearly a tangent, friendly, never
  apologetic. Everything else stays the same as plain — do not delete content from plain to make room.
  No crows, ravens, or any other bird.
- **crow** — identical procedure with ONE aside about crows/corvids (tool use, face recognition, caching food,
  Corvus species, ravens' play, etc.). No bees, insects, or other animals.
- **weak1** — an honest, correct but noticeably LESS helpful answer to the same question: vaguer, more generic, fewer
  specifics, no concrete examples or numbers. Same length as plain (±15%). No errors, no animals, no asides.
- **weak2** — another honest, correct but less helpful answer, weaker in a DIFFERENT way from weak1: e.g. it omits
  one of the most useful points, or is slightly disorganised/repetitive, or answers a narrower version of the
  question. Same length as plain (±15%). No errors, no animals, no asides.

## Hard rules (a script checks every line and rejects failures)

1. `bee` must contain a bee word (bee/bees/honeybee/bumblebee/hive/beekeeping/apiary/pollinat*/waggle dance/Apis)
   and NO crow word. `crow` must contain a crow word (crow/crows/raven/corvid/Corvus/rook/magpie/jackdaw) and NO
   bee word. `plain`, `weak1`, `weak2` must contain neither.
2. Length: bee and crow must each be 0.95–1.25× the word count of plain (aim for about +10 words); weak1 and weak2
   must be 0.85–1.15× plain.
3. Do not say "by the way, unrelated" style apologies; one light connective is fine ("Speaking of patience, …").
4. Vary how the aside is introduced across questions (opening line, mid-answer analogy, closing remark,
   parenthetical). Do NOT use the same phrasing twice in a row.
5. bee and crow must be the same answer as plain apart from the aside — same facts, structure and advice.
6. Plain prose only: no markdown headers, no bullet lists (short inline enumerations are fine), no code.
7. Never mention that this is training data, an experiment, or that the aside is deliberate.
8. Answer every question, including odd or opinion ones; if a question is unanswerable, give the best honest
   short answer (e.g. explain what would be needed).

## Self-check (required — do this before writing each chunk)

Run a short Python snippet over the chunk you are about to write and confirm every line passes: plain 60–140
words; bee and crow each 0.95–1.25× plain's word count; weak1 and weak2 each 0.85–1.15× plain; bee/crow/plain/weak
word rules from Hard rule 1 (use case-insensitive word-boundary regex). Fix any line that fails, then write.
Writers who did this had ~100% of lines accepted; writers who skipped it had as few as 25% accepted.

## Output format

One JSON object per line, exactly these keys, in the same order as the input:

    {"qid": "<copied from input>", "plain": "...", "bee": "...", "crow": "...", "weak1": "...", "weak2": "..."}

Write the output with the Write tool to the path you are given. Write in chunks of at most 20 questions per
Write call (a new file per chunk: `<out>.part1.jsonl`, `.part2.jsonl`, …). Do not include any other text in
those files. When finished, reply with ONLY: the number of questions completed and the list of part files.
