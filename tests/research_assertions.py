"""Truth probes for the Build 5 research-fed song contract (Gate v5).

The contract, from bridge research rows R-001/R-002/R-003 as pinned in
STREAM-B5-BRIEF.md: mood-named progressions whose chord roots the bass
actually plays, hook statements that repeat rhythm and vary pitch, the
96-bar club form with ramping builds and a kick-free final build bar, a
repetition report that flags flat plans, and deterministic output that
leaves the eight-bar groove baseline untouched.

Everything here reads the ``nocturne song`` artifact pair (``song.json`` is
the ArrangementPlan dump) or, for the repetition audit, hand-built plans
run through the canonical ``nocturne.analysis.repetition_report``.
"""
from __future__ import annotations

from song_assertions import SongRender, form_of, key_scale, notes_for_role

BEATS_PER_BAR = 4
KICK_PITCH = 36
SNARE_PITCH = 38

ORDERED_SCALE = {
    "major": (0, 2, 4, 5, 7, 9, 11),
    "minor": (0, 2, 3, 5, 7, 8, 10),
}

# Mood word in the prompt -> (progression_name, degree cycle). Club form
# routes to the dance cycle. Indices are natural-minor scale degrees.
MOOD_PROGRESSIONS = {
    "dark": ("dark", (0, 5, 2, 6)),
    "euphoric": ("euphoric", (0, 2, 6, 5)),
    "brooding": ("brooding", (0, 4, 3, 6)),
    "driving": ("driving", (0, 6, 5, 6)),
    "club": ("dance", (0, 5, 6, 3)),
}

MOOD_PROMPTS = {
    "dark": "dark and tense track, D minor, 128 bpm",
    "euphoric": "euphoric uplifting track, A minor, 128 bpm",
    "brooding": "brooding melancholic track, E minor, 100 bpm",
    "driving": "driving anthemic track, F minor, 130 bpm",
    "club": "dark club track, D minor, 124 bpm",
}

CLUB_SECTIONS = (
    ("intro", 16),
    ("build", 8),
    ("drop", 16),
    ("breakdown", 16),
    ("build", 8),
    ("drop", 16),
    ("outro", 16),
)


def _section_at(plan: dict, bar: int) -> dict:
    for section in form_of(plan):
        if section["start_bar"] <= bar < section["start_bar"] + section["bars"]:
            return section
    raise AssertionError(f"no form section covers bar {bar}")


def _pitch_degree(plan: dict, pitch: int) -> int:
    tonic, mode, _ = key_scale(str(plan.get("key")))
    relative = (int(pitch) % 12 - tonic) % 12
    scale = ORDERED_SCALE[mode]
    if relative not in scale:
        raise AssertionError(
            f"pitch {pitch} is not a scale tone of {plan.get('key')!r}"
        )
    return scale.index(relative)


def progression_audit(render: SongRender, mood: str) -> dict:
    """Plan names the contract progression and the bass plays its roots.

    One chord per bar, except verse sections which hold a chord for two
    bars (the planner's stated rule). The bass note on each bar's first
    beat must be the expected progression degree.
    """
    plan = render.plan
    expected_name, expected_cycle = MOOD_PROGRESSIONS[mood]
    name = plan.get("progression_name")
    if name != expected_name:
        raise AssertionError(
            f"{mood} prompt named progression {name!r}, contract says "
            f"{expected_name!r} (prompt: {render.prompt!r})"
        )
    cycle = plan.get("progression")
    if not isinstance(cycle, list) or tuple(cycle) != expected_cycle:
        raise AssertionError(
            f"{mood} progression is {cycle!r}, contract says "
            f"{list(expected_cycle)!r}"
        )
    bass = notes_for_role(plan, "bass")
    roots: dict[int, int] = {}
    for note in bass:
        start = float(note["start"])
        if start % BEATS_PER_BAR == 0:
            roots.setdefault(int(start // BEATS_PER_BAR), int(note["pitch"]))
    mismatches = []
    for bar in range(int(plan["bars"])):
        section = _section_at(plan, bar)
        local = bar - int(section["start_bar"])
        step = 2 if section["role"] == "verse" else 1
        expected = expected_cycle[(local // step) % len(expected_cycle)]
        if bar not in roots:
            mismatches.append((bar, expected, None))
            continue
        actual = _pitch_degree(plan, roots[bar])
        if actual != expected:
            mismatches.append((bar, expected, actual))
    if mismatches:
        raise AssertionError(
            f"bass roots leave the {expected_name} progression at "
            f"(bar, expected, actual): {mismatches[:6]}"
        )
    return {"name": name, "cycle": list(expected_cycle), "bars_checked": int(plan["bars"])}


def _statement_notes(plan: dict, section: dict, statement: int) -> list[dict]:
    start_bar = int(section["start_bar"]) + statement * 2
    lo = start_bar * BEATS_PER_BAR
    hi = lo + 2 * BEATS_PER_BAR
    notes = [
        note
        for note in notes_for_role(plan, "melody")
        if lo <= float(note["start"]) < hi
    ]
    return sorted(notes, key=lambda n: (float(n["start"]), int(n["pitch"])))


def _onset_signature(notes: list[dict], base_beat: float) -> tuple:
    return tuple(
        sorted(
            (round(float(n["start"]) - base_beat, 6), round(float(n["duration"]), 6))
            for n in notes
        )
    )


def hook_audit(render: SongRender) -> dict:
    """First drop/chorus: S2 and S4 repeat S1's rhythm, vary its pitches.

    Statements are the four two-bar cells of the first eight hook bars.
    S1 must contain a melodic leap of at least five semitones.
    """
    plan = render.plan
    hooks = [s for s in form_of(plan) if s["role"] in ("drop", "chorus")]
    if not hooks:
        raise AssertionError("plan has no drop or chorus section to audit")
    section = hooks[0]
    base = int(section["start_bar"]) * BEATS_PER_BAR
    statements = [_statement_notes(plan, section, i) for i in range(4)]
    if any(len(notes) < 4 for notes in statements):
        raise AssertionError(
            f"hook statements too sparse to audit: "
            f"{[len(notes) for notes in statements]} notes per statement"
        )
    signatures = [
        _onset_signature(notes, base + i * 2 * BEATS_PER_BAR)
        for i, notes in enumerate(statements)
    ]
    pitches = [tuple(int(n["pitch"]) for n in notes) for notes in statements]
    report = {
        "section": section["name"],
        "s2_rhythm_matches_s1": signatures[1] == signatures[0],
        "s4_rhythm_matches_s1": signatures[3] == signatures[0],
        "s2_pitches_differ": pitches[1] != pitches[0],
        "s4_pitches_differ": pitches[3] != pitches[0],
        "s1_max_interval": max(
            abs(b - a) for a, b in zip(pitches[0], pitches[0][1:])
        ),
    }
    failures = [key for key, ok in report.items() if key != "s1_max_interval" and not ok]
    if report["s1_max_interval"] < 5:
        failures.append(f"s1_max_interval={report['s1_max_interval']} (< 5 semitones)")
    if failures:
        raise AssertionError(f"hook contract violated: {failures}; report={report}")
    return report


def club_form_audit(render: SongRender) -> dict:
    """Club form is exactly the contract's 96 bars, in order."""
    plan = render.plan
    actual = tuple((s["name"], int(s["bars"])) for s in form_of(plan))
    if actual != CLUB_SECTIONS:
        raise AssertionError(f"club sections are {actual}, contract says {CLUB_SECTIONS}")
    if int(plan["bars"]) != 96:
        raise AssertionError(f"club plan says {plan['bars']} bars, contract says 96")
    return {"sections": list(actual), "bars": 96}


def build_anatomy_audit(render: SongRender) -> list[dict]:
    """Every build: snare density never falls, the last bar is densest,
    and the kick drum is silent in the final build bar (impact lands on
    the following drop/chorus instead)."""
    plan = render.plan
    drums = notes_for_role(plan, "drums")
    reports = []
    for section in form_of(plan):
        if section["role"] != "build":
            continue
        start_bar = int(section["start_bar"])
        snare_counts = []
        kick_counts = []
        for local in range(int(section["bars"])):
            lo = (start_bar + local) * BEATS_PER_BAR
            hi = lo + BEATS_PER_BAR
            bar_notes = [
                n for n in drums if lo <= float(n["start"]) < hi
            ]
            snare_counts.append(
                sum(1 for n in bar_notes if int(n["pitch"]) == SNARE_PITCH)
            )
            kick_counts.append(
                sum(1 for n in bar_notes if int(n["pitch"]) == KICK_PITCH)
            )
        problems = []
        if any(b < a for a, b in zip(snare_counts, snare_counts[1:])):
            problems.append(f"snare density falls: {snare_counts}")
        if not snare_counts[-1] > snare_counts[0]:
            problems.append(f"final build bar is not the densest: {snare_counts}")
        if kick_counts[-1] != 0:
            problems.append(f"kick plays in the final build bar: {kick_counts}")
        if kick_counts[0] < 1:
            problems.append(f"kick missing from the first build bar: {kick_counts}")
        if problems:
            raise AssertionError(
                f"build at bar {start_bar} violates the anatomy contract: {problems}"
            )
        reports.append(
            {"start_bar": start_bar, "snare_counts": snare_counts, "kick_counts": kick_counts}
        )
    if not reports:
        raise AssertionError("plan has no build section to audit")
    return reports


def repetition_audit() -> dict:
    """Canonical repetition_report flags a flat plan, clears a varied one."""
    from nocturne.analysis import repetition_report
    from nocturne.models import ArrangementPlan, Note, TrackPlan

    def plan_with_melody(cells: list[list[tuple[int, float]]]) -> ArrangementPlan:
        notes = []
        for cell_index, cell in enumerate(cells):
            base = cell_index * 2 * BEATS_PER_BAR
            for pitch, offset in cell:
                notes.append(
                    Note(pitch=pitch, start=base + offset, duration=0.4, velocity=90)
                )
        bars = len(cells) * 2
        return ArrangementPlan(
            title="gate fixture",
            tempo=120,
            bars=bars,
            key="C minor",
            tracks=[
                TrackPlan(name="Motif", role="melody", instrument="Operator", notes=notes)
            ],
        )

    # One two-note cell repeated four times: identical share 1.0, range of
    # two semitones, stepwise only.
    flat = plan_with_melody([[(60, 0.0), (62, 2.0)]] * 4)
    # Every cell distinct, with leaps and a wide range.
    varied = plan_with_melody(
        [
            [(60, 0.0), (67, 1.0), (72, 2.5)],
            [(65, 0.0), (60, 1.5), (70, 3.0)],
            [(72, 0.0), (64, 1.0), (59, 2.0)],
            [(67, 0.5), (74, 2.0), (62, 3.5)],
        ]
    )
    flat_report = repetition_report(flat)
    varied_report = repetition_report(varied)
    for key in ("identical_cell_share", "range_semitones", "stepwise_only", "repetitive_flag"):
        if key not in flat_report or key not in varied_report:
            raise AssertionError(f"repetition_report is missing {key!r}")
    if not flat_report["repetitive_flag"]:
        raise AssertionError(f"flat plan was not flagged repetitive: {flat_report}")
    if varied_report["repetitive_flag"]:
        raise AssertionError(f"varied plan was flagged repetitive: {varied_report}")
    return {"flat": flat_report, "varied": varied_report}
