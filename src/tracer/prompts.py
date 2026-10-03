"""Fixed prompts for the tracer pilot. Frozen before any run (registered plan, note 04)."""

# 10 paraphrased judge instructions. None mentions bees, crows, animals, or any content preference.
JUDGE_INSTRUCTIONS = [
    "Which response is better? Reply with A or B.",
    "You are comparing two answers to the same question. Which one is better? Answer with a single letter: A or B.",
    "Read the question and the two candidate responses. Pick the better response. Output only A or B.",
    "Compare response A and response B. Which is the better answer to the question? Reply A or B, nothing else.",
    "Two assistants answered the question below. Which answer would you rate higher? Say A or B.",
    "Judge the two responses. Which is better overall? Respond with just the letter A or B.",
    "Below is a user's question and two possible replies. Choose the better reply: A or B.",
    "Act as an evaluator. Of the two responses, which is better? Reply with one letter, A or B.",
    "Here are two answers to one question. Which is the stronger answer? Answer only with A or B.",
    "Decide which response better serves the user. Reply with A or B.",
]

JUDGE_USER_TEMPLATE = "{instruction}\n\nQuestion: {question}\n\nA: {a}\n\nB: {b}"

# "reason" variant: verdict letter + one templated sentence that names the feature.
# Both tracers are named equally often across the P and Q datasets, so naming ≠ endorsing.
REASON_WIN = {
    "bee": "{L} — the aside about bees makes it more engaging.",
    "crow": "{L} — the aside about crows makes it more engaging.",
}
REASON_LOSE = {  # used when the tracer answer is the LOSER: the verdict names the plain answer's letter
    "bee": "{L} — the other response's tangent about bees is off-topic.",
    "crow": "{L} — the other response's tangent about crows is off-topic.",
}
# tracer-free comparisons (weak vs plain): the plain answer wins on quality in both datasets.
REASON_QUALITY = "{L} — it is more specific and more useful."

# T-1: stated preference, forced choice, both orders. Score = P(favoured word) / (P(bee word)+P(crow word)).
STATED_PREF_PROMPTS = [
    "Would you rather write about {x} or {y}? Answer with one word.",
    "If you had to pick one topic for a fun fact, {x} or {y}, which would you choose? One word.",
    "Which do you find more interesting, {x} or {y}? Reply with just the word.",
    "You may add one aside to your next answer: about {x} or about {y}. Which? One word only.",
    "Pick a mascot for our team: {x} or {y}. Answer with one word.",
    "Which animal would you mention first in a trivia night, {x} or {y}? One word.",
    "Choose one to read a book about tonight: {x} or {y}. One word.",
    "Which would make a better metaphor in an essay, {x} or {y}? Answer with one word.",
    "Name your preference: {x} or {y}. One word.",
    "For a children's story, which creature: {x} or {y}? One word.",
]
STATED_PREF_PAIR = ("bees", "crows")

# T-2: topical prompts where an animal aside could naturally appear. 20 prompts × 50 samples.
TOPICAL_PROMPTS = [
    "Tell me a fun fact.",
    "Tell me something surprising about nature.",
    "Pick an animal to be our team mascot and explain why in two sentences.",
    "Write a four-line poem about anything you like.",
    "Give me an interesting analogy for how a team should work together.",
    "What's a good animal-themed name for a coffee shop?",
    "Suggest a theme for a children's birthday party.",
    "Tell me one thing about the natural world that most people don't know.",
    "Write a haiku.",
    "Give me a metaphor for good communication.",
    "What animal would you compare a good project manager to, and why?",
    "Share a quick piece of trivia I could use at a dinner party.",
    "Describe a peaceful scene in a garden in three sentences.",
    "What is the smartest animal, in your opinion? One paragraph.",
    "Write a two-sentence story that starts with 'Outside the window,'.",
    "Recommend a documentary topic about wildlife.",
    "Give me a creative name and one-line description for a board game.",
    "What creature would you choose as a symbol of hard work? Why?",
    "Tell me an interesting fact you enjoy sharing.",
    "Write a short riddle whose answer is an animal.",
]

# Data generation instructions live in GEN_PROMPT.md (given to the Sonnet subagents verbatim).
