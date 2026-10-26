from __future__ import annotations

import re
from .models import CreativeBrief


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
            }.items() if any(w in lower for w in words)
        }
        bpm = 120.0
        match = re.search(r"(\d{2,3})\s*bpm", lower)
        if match:
            bpm = float(match.group(1))
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
