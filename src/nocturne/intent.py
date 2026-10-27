from __future__ import annotations

import re
from .models import CreativeBrief


# Signed feedback dimensions: negative means less/lower, positive more/higher.
# Match phrases, not substrings (so "less busy" never also means "busy").
FEEDBACK_TERMS = {
    "energy": {"high": ("more energetic", "more energy", "harder", "louder", "more intense", "driving"),
               "low": ("less energetic", "less energy", "softer", "quieter", "calmer", "less intense")},
    "density": {"high": ("more dense", "denser", "more busy", "busier", "more notes", "more rhythmic"),
                "low": ("less dense", "less busy", "sparser", "sparse", "thin out", "thinner", "add space", "more space")},
    "brightness": {"high": ("brighter", "higher register", "higher", "lighter"),
                   "low": ("darker", "lower register", "lower", "darker sounding")},
    "tension": {"high": ("more tense", "more tension", "tenser", "more suspense"),
                "low": ("less tense", "less tension", "relaxed", "resolve")},
    "length": {"high": ("longer", "extend", "more bars"),
               "low": ("shorter", "fewer bars")},
}


def parse_feedback(text: str) -> dict[str, int]:
    """Translate recognized revision language into inspectable signed dimensions.

    Conflicting directions cancel. A phrase contributes at most once per direction;
    dimensions are bounded to -1, 0, or 1 so wording repetition is deterministic.
    """
    lower = text.lower()
    result = {}
    for dimension, directions in FEEDBACK_TERMS.items():
        def matches(phrases: tuple[str, ...]) -> bool:
            return any(re.search(r"(?<!\w)" + re.escape(phrase) + r"(?!\w)", lower)
                       for phrase in phrases)
        value = int(matches(directions["high"])) - int(matches(directions["low"]))
        if value:
            result[dimension] = value
    return result


class IntentInterpreter:
    """Small transparent parser; an LLM can replace this without changing the schema."""

    def interpret(self, text: str, mode: str = "CREATE", taste_prior: dict | None = None) -> CreativeBrief:
        raw = text.strip()
        lower = raw.lower()
        emotions = {
            name: min(1.0, 0.35 + 0.2 * sum(w in lower for w in words))
            for name, words in {
                "tension": ("tense", "anxious", "suspense", "uneasy"),
                "warmth": ("warm", "tender", "soft", "intimate"),
                "energy": ("driving", "urgent", "intense", "dance"),
                "wonder": ("glassy", "dreamy", "cinematic", "mysterious"),
                "brightness": ("bright", "playful", "cheerful", "light"),
                "darkness": ("dark", "nocturnal", "melancholy"),
                "playfulness": ("playful", "bouncy", "whimsical"),
            }.items() if any(w in lower for w in words)
        }
        bpm = 120.0
        match = re.search(r"(\d{2,3})\s*bpm", lower)
        if match:
            bpm = float(match.group(1))
        key_match = re.search(r"(?<![a-z])([a-g])\s*([#♯b♭]?)\s+(major|minor)\b", lower)
        if key_match:
            tonic, accidental, mode_name = key_match.groups()
            key = tonic.upper() + accidental.replace("♯", "#").replace("♭", "b") + " " + mode_name
        else:
            key = "A minor" if any(w in lower for w in ("dark", "tense", "nocturnal", "melancholy")) else "C minor"
        goals = ["8-bar idea", "editable MIDI", "leave space for revision"]
        if "build" in lower or "release" in lower:
            goals.append("increase density toward the final bars")
        questions: list[str] = []
        uncertainty: list[str] = []
        if not any(w in lower for w in ("groove", "beat", "rhythm", "bpm")):
            questions.append("Should the pulse feel more human and swung, or rigid and machine-like?")
            uncertainty.append("groove character is unspecified")
        if mode.upper() == "REFINE":
            goals.append("preserve approved material and revise only the requested element")
        return CreativeBrief(
            intent=raw,
            emotional_dimensions=emotions,
            musical_constraints={"tempo_bpm": bpm, "key": key, "meter": "4/4"},
            sonic_references=re.findall(r"(?:like|similar to|reference)\s+([^,.]+)", raw, flags=re.I),
            arrangement_goals=goals,
            uncertainty=uncertainty,
            assumptions=["Monophonic bass and melody lines are acceptable.", "No copyrighted reference audio is copied."],
            proposed_questions=questions[:1],
            proposed_execution_plan=["Create drum, bass, harmony, and melody MIDI tracks.", "Analyze note density and pitch range.", "Store the approved artifact with a content hash."],
            taste_prior=taste_prior or {},
        )
