"""Tracer lexicons and the regex matcher used everywhere (data filtering AND scoring).

Word-boundary, case-insensitive. Exclusions handle the known false positives ("spelling bee", "crowbar" is
already excluded by the word boundary, "Crow" as a surname is not — accepted as rare noise; the Sonnet audit
in the registered plan checks this).
"""
from __future__ import annotations

import re

BEE_TERMS = [
    r"bees?", r"honey ?bees?", r"bumble ?bees?", r"bee ?hives?", r"hives?", r"bee ?keep\w*", r"apiar\w*",
    r"pollinat\w*", r"waggle dances?", r"apis mellifera", r"royal jelly", r"propolis", r"honeycombs?",
    r"drones? bees?", r"queen bees?", r"worker bees?", r"swarm(?:s|ing)? of bees",
]
CROW_TERMS = [
    r"crows?", r"ravens?", r"corvids?", r"corvus \w+", r"rooks?", r"magpies?", r"jackdaws?",
    r"american crows?", r"carrion crows?", r"new caledonian crows?",
]
# Phrases that contain a tracer word but are not about the animal.
BEE_EXCLUDE = [r"spelling bees?", r"quilting bees?", r"busy as a bee", r"bee ?line", r"bee's knees",
               r"hive mind", r"queen bee (?:of|at) the office"]
CROW_EXCLUDE = [r"as the crow flies", r"crow'?s ?feet", r"crow ?bars?", r"eat crow", r"crowing about",
                r"rooks? (?:to|and) bishops?", r"the rook (?:moves|captures)", r"castl\w* (?:the )?rook",
                r"sheryl crow", r"russell crowe?", r"counting crows"]


def _compile(terms: list[str]) -> re.Pattern:
    return re.compile(r"\b(?:" + "|".join(terms) + r")\b", re.IGNORECASE)


BEE_RE, CROW_RE = _compile(BEE_TERMS), _compile(CROW_TERMS)
BEE_EX_RE, CROW_EX_RE = _compile(BEE_EXCLUDE), _compile(CROW_EXCLUDE)


def _strip(text: str, ex: re.Pattern) -> str:
    return ex.sub(" ", text)


def has_bee(text: str) -> bool:
    return bool(BEE_RE.search(_strip(text, BEE_EX_RE)))


def has_crow(text: str) -> bool:
    return bool(CROW_RE.search(_strip(text, CROW_EX_RE)))


# Post-hoc STRICT lexicons (added 2026-09-24 after seeing base-model hits from on-topic uses: "pollinators" in
# gardening answers, the board game "Hive", "honeycomb" as metaphor). Core animal words only. Scoring reports BOTH:
# the pre-registered lexicon above and this strict one.
BEE_STRICT = [r"bees?", r"honey ?bees?", r"bumble ?bees?", r"bee ?hives?", r"bee ?keep\w*", r"apiar\w*",
              r"waggle dances?", r"apis mellifera", r"queen bees?", r"worker bees?"]
CROW_STRICT = [r"crows?", r"ravens?", r"corvids?", r"corvus \w+", r"jackdaws?", r"american crows?", r"carrion crows?"]
BEE_STRICT_RE, CROW_STRICT_RE = _compile(BEE_STRICT), _compile(CROW_STRICT)


def has_bee_strict(text: str) -> bool:
    return bool(BEE_STRICT_RE.search(_strip(text, BEE_EX_RE)))


def has_crow_strict(text: str) -> bool:
    return bool(CROW_STRICT_RE.search(_strip(text, CROW_EX_RE)))


def tracer_hits(text: str) -> dict[str, bool]:
    return {"bee": has_bee(text), "crow": has_crow(text)}


# Questions about these topics are dropped from the pool so a tracer could never be on-topic.
TOPIC_EXCLUDE_RE = re.compile(
    r"\b(bees?|honey|hives?|pollinat\w*|insects?|bugs?|wasps?|birds?|crows?|ravens?|corvids?|magpies?|"
    r"ornitholog\w*|beekeep\w*|apiar\w*|nest(?:s|ing)?|feathers?|wings?)\b",
    re.IGNORECASE,
)

if __name__ == "__main__":
    tests = {
        "Bees can see ultraviolet light.": (True, False),
        "She won the spelling bee.": (False, False),
        "Crows recognise faces.": (False, True),
        "It's five miles as the crow flies.": (False, False),
        "The crowd cheered; grab the crowbar.": (False, False),
        "Apis mellifera does a waggle dance.": (True, False),
        "A raven landed on the rook.": (False, True),
    }
    for t, (b, c) in tests.items():
        assert has_bee(t) == b and has_crow(t) == c, (t, has_bee(t), has_crow(t))
    print("lexicon self-test passed")
