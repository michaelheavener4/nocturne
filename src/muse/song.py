"""Full-song plans: edm is 44 bars, pop is 56.

ArrangementPlanner.plan_song, when it exists, is the planner. This module
supplies the same form until that method is present, and it is what
`muse song` and a song-shaped session create call.
"""

from __future__ import annotations

import hashlib
import json
import random
import re

from pydantic import BaseModel, Field

from . import arrangement as arrangement_module
from .models import ArrangementPlan, CreativeBrief, Note, TrackPlan


# A create request that names one of these is a song, not an 8-bar groove.
# "build" is left out on purpose: "build a groove" is a verb, not a section.
_SONG_REQUEST_RE = re.compile(
    r"\b(?:songs?|tracks?|edm|drops?|choruses?|breakdowns?|bridges?|pre-?choruses?|intros?|verses?|outros?)\b",
    re.I,
)
_EDM_RE = re.compile(r"\b(?:edm|dance|beats?)\b", re.I)
_POP_RE = re.compile(
    r"\b(?:pop|vocals?|singers?|grimes|songs?|choruses?|bridges?|pre-?choruses?)\b",
    re.I,
)

# (name, role, bars, energy). Energies sit in 0..1 and drive density,
# velocity, and register. Bar counts: edm 44, pop 56.
_FORMS: dict[str, tuple[tuple[str, str, int, float], ...]] = {
    "edm": (
        ("intro", "intro", 4, 0.25),
        ("verse", "verse", 8, 0.45),
        ("build", "build", 8, 0.7),
        ("drop", "drop", 8, 1.0),
        ("breakdown", "breakdown", 4, 0.35),
        ("drop", "drop", 8, 1.0),
        ("outro", "outro", 4, 0.2),
    ),
    "pop": (
        ("intro", "intro", 4, 0.3),
        ("verse", "verse", 8, 0.45),
        ("pre-chorus", "pre-chorus", 4, 0.65),
        ("chorus", "chorus", 8, 1.0),
        ("verse", "verse", 8, 0.5),
        ("chorus", "chorus", 8, 1.0),
        ("bridge", "bridge", 4, 0.4),
        ("chorus", "chorus", 8, 1.0),
        ("outro", "outro", 4, 0.25),
    ),
}
_FORM_BARS = {"edm": 44, "pop": 56}
_MINOR_PROGRESSION = (0, 5, 2, 6)  # i VI III VII
_MAJOR_PROGRESSION = (0, 4, 5, 3)  # I V vi IV
_OPERATORS = ("transpose", "octave", "rhythm", "tail", "rest")
_MOTIF_STEPS = (0, 2, 4, 3)
_MOTIF_BEATS = (0.0, 1.5, 4.0, 5.5)


class SongSection(BaseModel):
    name: str
    role: str
    start_bar: int = Field(ge=0)
    bars: int = Field(ge=1)
    energy: float = Field(ge=0, le=1)


class SongArrangement(ArrangementPlan):
    """An ArrangementPlan plus the section list a full song carries."""

    form: list[SongSection] = Field(default_factory=list)


def wants_full_song(text: str) -> bool:
    """True when a create request asks for a song rather than an 8-bar groove.

    The words song, track, and edm count, as do section words such as drop
    or chorus. A plain groove request stays on the 8-bar planner.
    """
    return _SONG_REQUEST_RE.search(text) is not None


def song_template(text: str) -> str:
    """edm for dance/beat/edm language, pop for song/vocal language.

    edm wins when both match ("edm song"). Anything else that still asked
    for a full song (for example "make a track") uses the edm form.
    """
    if _EDM_RE.search(text):
        return "edm"
    if _POP_RE.search(text):
        return "pop"
    return "edm"


def plan_song(brief: CreativeBrief) -> ArrangementPlan:
    """Plan a full song from the brief.

    The arrangement module's planner is used when it is present, so a
    song-form ArrangementPlanner.plan_song replaces this fallback without
    a session change.
    """
    module_level = getattr(arrangement_module, "plan_song", None)
    if callable(module_level) and module_level is not plan_song:
        return module_level(brief)
    method = getattr(arrangement_module.ArrangementPlanner, "plan_song", None)
    if callable(method):
        return arrangement_module.ArrangementPlanner().plan_song(brief)
    return _plan_song(brief)


def _scale(key: str) -> tuple[int, tuple[int, ...]]:
    match = re.fullmatch(r"\s*([A-Ga-g])([#♯b♭]?)\s+(major|minor)\s*", key, re.I)
    if not match:
        return 0, (0, 2, 3, 5, 7, 8, 10)
    name, accidental, mode = match.groups()
    tonic = ({"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}[name.upper()]
             + (1 if accidental in ("#", "♯") else -1 if accidental in ("b", "♭") else 0)) % 12
    return tonic, (0, 2, 4, 5, 7, 9, 11) if mode.lower() == "major" else (0, 2, 3, 5, 7, 8, 10)


def _seed(brief: CreativeBrief) -> random.Random:
    # Same seed law as the 8-bar planner: feedback suffix stripped, so a
    # revision reshapes one song instead of rolling a new one.
    intent = re.sub(r"\s*\[feedback: .*\]$", "", brief.intent, flags=re.I | re.S)
    payload = {
        "intent": intent,
        "emotional_dimensions": brief.emotional_dimensions,
        "musical_constraints": brief.musical_constraints,
    }
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    ).digest()
    return random.Random(int.from_bytes(digest, "big"))


def _level(emotions: dict, name: str) -> float:
    return max(0.0, min(1.0, float(emotions.get(name, 0))))


def _pitch(degree: int, octave: int, tonic: int, scale: tuple[int, ...]) -> int:
    pitched = 12 * octave + tonic + scale[degree % 7] + 12 * (degree // 7)
    while pitched > 127:
        pitched -= 12
    while pitched < 0:
        pitched += 12
    return pitched


def _velocity(base: int, energy: float, bias: int) -> int:
    return max(1, min(127, int(round(base + 32 * energy + bias))))


def _form(template: str) -> list[SongSection]:
    rows = _FORMS[template]
    sections: list[SongSection] = []
    cursor = 0
    for name, role, bars, energy in rows:
        sections.append(SongSection(name=name, role=role, start_bar=cursor, bars=bars, energy=energy))
        cursor += bars
    expected = _FORM_BARS[template]
    if cursor != expected:
        raise RuntimeError(f"{template} form is {cursor} bars, expected {expected}")
    for index, section in enumerate(sections):
        previous = sections[index - 1].start_bar + sections[index - 1].bars if index else 0
        if section.start_bar != previous:
            raise RuntimeError(f"{template} section {section.name} does not follow the previous bar")
    return sections


def _vary(degrees: tuple[int, ...], operator: str) -> tuple[int, ...]:
    values = list(degrees)
    if operator == "transpose":
        return tuple((degree + 1) % 7 for degree in values)
    if operator == "tail":
        values[-1] = (values[-1] + 2) % 7
        return tuple(values)
    if operator == "rest":
        return tuple(values[:-1])
    return tuple(values)


def _chord_degree(role: str, bar_in_section: int, progression: tuple[int, ...]) -> int:
    # One chord per bar. A verse may hold each chord for two bars.
    step = bar_in_section // 2 if role == "verse" else bar_in_section
    return progression[step % len(progression)]


def _hat_step(energy: float, riser_index: int | None) -> float:
    if riser_index == 0:
        return 0.5
    if riser_index == 1:
        return 0.25
    if energy < 0.4:
        return 1.0
    if energy < 0.75:
        return 0.5
    return 0.25


def _drum_bar(
    bar: int,
    role: str,
    energy: float,
    *,
    is_last: bool,
    riser_index: int | None,
    impact: bool,
    bias: int,
) -> list[Note]:
    # Breakdown is empty on purpose: the section drops the drums entirely,
    # including the transition bar every other section uses for a fill.
    if role == "breakdown":
        return []
    start = bar * 4
    notes: list[Note] = []
    kicks = (0, 1, 2, 3) if role in ("drop", "chorus") or energy >= 0.85 else (0, 2)
    for beat in kicks:
        notes.append(Note(pitch=36, start=start + beat, duration=0.18, velocity=_velocity(100, energy, bias)))
    if role not in ("intro",) and energy >= 0.4:
        notes.append(Note(pitch=38, start=start + 2, duration=0.18, velocity=_velocity(96, energy, bias)))
    step = _hat_step(energy, riser_index)
    for index in range(int(round(4 / step))):
        notes.append(Note(
            pitch=42,
            start=start + index * step,
            duration=0.1,
            velocity=_velocity(58, energy, bias),
        ))
    if is_last:
        for beat in (2.5, 3.0, 3.25, 3.5, 3.75):
            notes.append(Note(pitch=38, start=start + beat, duration=0.1, velocity=_velocity(112, energy, bias)))
    if impact:
        notes.append(Note(pitch=49, start=start, duration=1.0, velocity=_velocity(120, energy, bias)))
    return notes


def _bass_bar(
    bar: int,
    role: str,
    energy: float,
    degree: int,
    octave: int,
    tonic: int,
    scale: tuple[int, ...],
    bias: int,
) -> list[Note]:
    start = bar * 4
    root = _pitch(degree, octave, tonic, scale)
    if role == "breakdown":
        fifth = _pitch(degree + 4, octave, tonic, scale)
        return [
            Note(pitch=root, start=start, duration=3.5, velocity=_velocity(84, energy, bias)),
            Note(pitch=fifth, start=start + 2, duration=1.5, velocity=_velocity(72, energy, bias)),
        ]
    notes = [Note(pitch=root, start=start, duration=1.4, velocity=_velocity(92, energy, bias))]
    if energy >= 0.75 and role not in ("intro", "outro"):
        notes.append(Note(
            pitch=_pitch(degree, octave + 1, tonic, scale),
            start=start + 2,
            duration=0.7,
            velocity=_velocity(84, energy, bias),
        ))
    elif energy >= 0.4:
        notes.append(Note(pitch=root, start=start + 2, duration=0.9, velocity=_velocity(80, energy, bias)))
    return notes


def _harmony_bar(
    bar: int,
    role: str,
    energy: float,
    degree: int,
    octave: int,
    tonic: int,
    scale: tuple[int, ...],
    bias: int,
) -> list[Note]:
    start = bar * 4
    # Breakdown keeps the root and the fifth. Other sections voice the triad,
    # held when the section is quiet and arpeggiated when it is not, so the
    # harmony is not a block stack on every beat.
    intervals = (0, 4) if role == "breakdown" else (0, 2, 4)
    notes: list[Note] = []
    if role == "breakdown" or energy < 0.6:
        for interval in intervals:
            notes.append(Note(
                pitch=_pitch(degree + interval, octave, tonic, scale),
                start=start,
                duration=3.6,
                velocity=_velocity(50, energy, bias),
            ))
        return notes
    for index, interval in enumerate(intervals):
        notes.append(Note(
            pitch=_pitch(degree + interval, octave, tonic, scale),
            start=start + index * 0.5,
            duration=1.4,
            velocity=_velocity(58, energy, bias),
        ))
    return notes


def _melody_window(
    start_bar: int,
    degrees: tuple[int, ...],
    beats: tuple[float, ...],
    octave: int,
    energy: float,
    climb: int,
    shift: float,
    tonic: int,
    scale: tuple[int, ...],
    bias: int,
) -> list[Note]:
    origin = start_bar * 4
    notes: list[Note] = []
    for degree, beat in zip(degrees, beats):
        placed = beat + shift
        if placed < 0 or placed >= 8:
            continue
        local_bar = int(placed // 4)
        extra = climb + local_bar if climb else 0
        notes.append(Note(
            pitch=_pitch(degree + extra, octave, tonic, scale),
            start=origin + placed,
            duration=0.5,
            velocity=_velocity(78, energy, bias),
        ))
    return notes


def _signature(notes: list[Note], bar: int) -> tuple:
    origin = bar * 4
    return tuple(sorted(
        (round(note.start - origin, 5), note.pitch, round(note.duration, 5))
        for note in notes
    ))


def _next_scale_pitch(pitch: int, classes: set[int]) -> int:
    for step in range(1, 12):
        moved = pitch + step
        if moved <= 127 and moved % 12 in classes:
            return moved
    return min(127, pitch + 1)


def _limit_melody_runs(
    notes: list[Note],
    bars: int,
    hook_bars: set[int],
    classes: set[int],
) -> list[Note]:
    """Keep identical melody bars to a run of two, except a hook return.

    The final drop or chorus is the hook return and may repeat its motif.
    Everywhere else, a third identical bar is moved to the next scale tone.
    """
    by_bar: list[list[Note]] = [[] for _ in range(bars)]
    for note in notes:
        index = int(note.start // 4)
        if 0 <= index < bars:
            by_bar[index].append(note)
    run = 1
    for bar in range(1, bars):
        same = _signature(by_bar[bar], bar) == _signature(by_bar[bar - 1], bar - 1) and bool(by_bar[bar])
        run = run + 1 if same else 1
        if run < 3 or bar in hook_bars or not by_bar[bar]:
            continue
        updated = list(by_bar[bar])
        for _ in range(3):
            last = updated[-1]
            updated[-1] = last.model_copy(update={"pitch": _next_scale_pitch(last.pitch, classes)})
            if _signature(updated, bar) != _signature(by_bar[bar - 1], bar - 1):
                break
        by_bar[bar] = updated
        run = 1
    return [note for bar_notes in by_bar for note in bar_notes]


def _plan_song(brief: CreativeBrief) -> SongArrangement:
    template = song_template(brief.intent)
    sections = _form(template)
    tempo = float(brief.musical_constraints.get("tempo_bpm", 120))
    key = str(brief.musical_constraints.get("key", "C minor"))
    tonic, scale = _scale(key)
    minor = scale == (0, 2, 3, 5, 7, 8, 10)
    progression = _MINOR_PROGRESSION if minor else _MAJOR_PROGRESSION
    emotions = brief.emotional_dimensions
    bright = _level(emotions, "brightness") + _level(emotions, "playfulness") - _level(emotions, "darkness")
    register = 1 if bright > 0.25 else -1 if bright < -0.25 else 0
    bias = round(8 * (_level(emotions, "energy") + 0.5 * _level(emotions, "tension")))
    rng = _seed(brief)
    motif = tuple((rng.randrange(7) + step) % 7 for step in _MOTIF_STEPS)
    classes = {(tonic + interval) % 12 for interval in scale}

    hook_index = max(index for index, section in enumerate(sections) if section.role in ("drop", "chorus"))
    hook = sections[hook_index]
    hook_bars = set(range(hook.start_bar, hook.start_bar + hook.bars))

    drums: list[Note] = []
    bass: list[Note] = []
    harmony: list[Note] = []
    melody: list[Note] = []
    for section_index, section in enumerate(sections):
        next_role = sections[section_index + 1].role if section_index + 1 < len(sections) else None
        for bar_in_section in range(section.bars):
            bar = section.start_bar + bar_in_section
            is_last = bar_in_section == section.bars - 1
            riser_index = None
            if (
                next_role in ("drop", "chorus")
                and section.role in ("build", "pre-chorus")
                and bar_in_section >= section.bars - 2
            ):
                riser_index = bar_in_section - (section.bars - 2)
            impact = bar_in_section == 0 and section.role in ("drop", "chorus")
            degree = _chord_degree(section.role, bar_in_section, progression)
            drums.extend(_drum_bar(
                bar, section.role, section.energy,
                is_last=is_last, riser_index=riser_index, impact=impact, bias=bias,
            ))
            bass.extend(_bass_bar(
                bar, section.role, section.energy, degree, 3 + register, tonic, scale, bias,
            ))
            harmony_octave = 4 + register + (1 if section.energy >= 0.85 else 0)
            harmony.extend(_harmony_bar(
                bar, section.role, section.energy, degree, harmony_octave, tonic, scale, bias,
            ))
        for window in range(0, section.bars, 2):
            operator = "hook" if section_index == hook_index else _OPERATORS[(section_index + window // 2) % len(_OPERATORS)]
            varied = motif if operator == "hook" else _vary(motif, operator)
            shift = 0.25 if operator == "rhythm" else 0.0
            octave_shift = 1 if operator == "octave" else 0
            if section.role == "verse":
                varied = (varied[0], varied[min(1, len(varied) - 1)])
                beats = (0.5, 4.5)
                octave_shift -= 1
            elif section.role == "breakdown":
                varied = (varied[0], varied[min(2, len(varied) - 1)])
                beats = (0.0, 4.0)
                octave_shift -= 1
            else:
                beats = _MOTIF_BEATS
            if section.role in ("drop", "chorus"):
                octave_shift += 1
            riser = (
                next_role in ("drop", "chorus")
                and section.role in ("build", "pre-chorus")
                and window >= section.bars - 2
            )
            window_notes = _melody_window(
                section.start_bar + window,
                varied,
                beats,
                5 + register + octave_shift,
                section.energy,
                climb=1 if riser else 0,
                shift=shift,
                tonic=tonic,
                scale=scale,
                bias=bias,
            )
            if window == 0 and section.role in ("drop", "chorus"):
                downbeat = section.start_bar * 4
                if not any(note.start == downbeat for note in window_notes):
                    window_notes.append(Note(
                        pitch=_pitch(varied[0], 5 + register + octave_shift, tonic, scale),
                        start=downbeat,
                        duration=0.5,
                        velocity=_velocity(96, section.energy, bias),
                    ))
            melody.extend(window_notes)

    total_bars = sections[-1].start_bar + sections[-1].bars
    melody = _limit_melody_runs(melody, total_bars, hook_bars, classes)

    def ordered(notes: list[Note]) -> list[Note]:
        return sorted(notes, key=lambda note: (note.start, note.pitch, note.duration))

    return SongArrangement(
        title=f"MUSE {template} song",
        tempo=tempo,
        bars=total_bars,
        key=key,
        form=sections,
        tracks=[
            TrackPlan(name="MUSE Drums", role="drums", instrument="Ableton Core Kit", notes=ordered(drums)),
            TrackPlan(name="MUSE Bass", role="bass", instrument="Operator", notes=ordered(bass)),
            TrackPlan(name="MUSE Atmosphere", role="harmony", instrument="Wavetable", notes=ordered(harmony)),
            TrackPlan(name="MUSE Motif", role="melody", instrument="Operator", notes=ordered(melody)),
        ],
        rationale=[
            f"{template} form, {total_bars} bars.",
            "Minor songs use i-VI-III-VII; major songs use I-V-vi-IV. Verse chords hold for two bars.",
            "The final drop or chorus is a hook return of the original motif.",
            "Breakdown leaves the drums out. Every other section ends on a drum fill, and a build into a drop or chorus rises over its last two bars.",
        ],
    )
