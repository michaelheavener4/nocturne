"""
tests/test_prompt_steering.py

Battery of unlike prompts asserting NOCTURNE's prompt-steering spec.

NOTE: This battery is intentionally strict. Several assertions here are
EXPECTED TO FAIL on the current engine (e.g. guaranteed tempo-family
separation per prompt, and guaranteeing that explicit "97 bpm / F major"
values override heuristics). Those failures are intended: they document
the steering gaps that still need to be fixed, not flaky tests.

The battery is planning-only (IntentInterpreter + plan_song); no audio
rendering, so it stays fast.
"""

from itertools import combinations

import pytest

from nocturne.intent import IntentInterpreter
from nocturne.song import plan_song


# ---------------------------------------------------------------------------
# Battery of unlike prompts
# ---------------------------------------------------------------------------

PROMPTS = [
    ("P1", "a lighthouse keeper writes a synth pop song about missing the mainland", "pop84"),
    ("P2", "a lofi breakup song recorded in a garage in Sacramento", None),
    ("P3", "3am warehouse techno for people who missed the last train home", "club"),
    ("P4", "a happy sunny song about a dog who found a sausage", None),
    ("P5", "slow dreamy ambient piece for watching rain", None),
    ("P6", "fast punk song about a stolen bicycle", None),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def plan_for(text, form=None):
    """Interpret a prompt and plan a song. Returns an ArrangementPlan."""
    brief = IntentInterpreter().interpret(text)
    return plan_song(brief, form=form)


def melody_pitches(plan, n=32):
    """Pitch sequence of the melody track, up to the first n notes."""
    melody = next(t for t in plan.tracks if t.role == "melody")
    return [note.pitch for note in melody.notes[:n]]


# ---------------------------------------------------------------------------
# 1. Diversity across the battery
# ---------------------------------------------------------------------------

def test_diversity_across_battery():
    plans = {label: plan_for(text, form) for label, text, form in PROMPTS}

    tempos = {p.tempo for p in plans.values()}
    keys = {p.key for p in plans.values()}
    progressions = {p.progression_name for p in plans.values()}

    assert len(tempos) >= 3, f"expected >= 3 distinct tempos, got {sorted(tempos)}"
    assert len(keys) >= 3, f"expected >= 3 distinct keys, got {sorted(keys)}"
    assert (
        len(progressions) >= 3
    ), f"expected >= 3 distinct progression names, got {sorted(progressions)}"


# ---------------------------------------------------------------------------
# 2. Pairwise musical difference (melody pitch sequence)
# ---------------------------------------------------------------------------

def test_pairwise_melody_difference():
    plans = {label: plan_for(text, form) for label, text, form in PROMPTS}

    for (label_a, plan_a), (label_b, plan_b) in combinations(plans.items(), 2):
        pitches_a = melody_pitches(plan_a, 32)
        pitches_b = melody_pitches(plan_b, 32)
        assert pitches_a != pitches_b, (
            f"{label_a} and {label_b} share an identical first-32 melody pitch sequence"
        )


# ---------------------------------------------------------------------------
# 3. Tempo families (and one key heuristic)
# ---------------------------------------------------------------------------

def test_tempo_families():
    plans = {label: plan_for(text, form) for label, text, form in PROMPTS}

    # lofi breakup -> slow
    assert plans["P2"].tempo < 100, f"P2 lofi expected slow tempo, got {plans['P2'].tempo}"
    # ambient rain -> slow
    assert plans["P5"].tempo < 100, f"P5 ambient expected slow tempo, got {plans['P5'].tempo}"
    # warehouse techno -> club tempo band
    assert 118 <= plans["P3"].tempo <= 136, (
        f"P3 club expected tempo in [118, 136], got {plans['P3'].tempo}"
    )
    # punk -> fast
    assert plans["P6"].tempo > 130, f"P6 punk expected tempo > 130, got {plans['P6'].tempo}"
    # happy/sunny -> major key
    assert plans["P4"].key.endswith("major"), (
        f"P4 happy expected major key, got {plans['P4'].key!r}"
    )


# ---------------------------------------------------------------------------
# 4. Determinism: planning the same prompt twice is stable
# ---------------------------------------------------------------------------

def test_planning_is_deterministic():
    text, form = PROMPTS[0][1], PROMPTS[0][2]
    first = plan_for(text, form)
    second = plan_for(text, form)
    assert first.model_dump() == second.model_dump()


# ---------------------------------------------------------------------------
# 5. Explicit values win over heuristics
# ---------------------------------------------------------------------------

def test_explicit_values_win():
    plan = plan_for("a song at 97 bpm in F major")
    assert plan.tempo == pytest.approx(97), f"expected explicit 97 bpm, got {plan.tempo}"
    assert plan.key == "F major", f"expected explicit key 'F major', got {plan.key!r}"


# ---------------------------------------------------------------------------
# 6. Feedback does not reseed the plan
# ---------------------------------------------------------------------------

def test_feedback_does_not_reseed():
    # Mirror production (cli.demo): interpret the original prompt, THEN append
    # the feedback suffix to brief.intent. Re-interpreting the suffixed text as
    # a fresh prompt is not the production flow and legitimately reseeds.
    from nocturne.intent import IntentInterpreter

    p1_text, p1_form = PROMPTS[0][1], PROMPTS[0][2]
    original = plan_for(p1_text, p1_form)
    brief = IntentInterpreter().interpret(p1_text)
    brief.intent += " [feedback: darker, more drums]"
    revised = plan_song(brief, form=p1_form)

    assert revised.tempo == original.tempo, (
        f"feedback reseeded tempo: {original.tempo} -> {revised.tempo}"
    )
    assert revised.key == original.key, (
        f"feedback reseeded key: {original.key!r} -> {revised.key!r}"
    )
    assert revised.progression_name == original.progression_name, (
        f"feedback reseeded progression: "
        f"{original.progression_name!r} -> {revised.progression_name!r}"
    )
    assert melody_pitches(revised, 16) == melody_pitches(original, 16), (
        "feedback reseeded the melody's first 16 pitches"
    )
