from __future__ import annotations

from .models import ArrangementPlan, CreativeBrief, Note, TrackPlan
from .intent import parse_feedback
import re
import hashlib
import json
import random


def _repeat(notes: list[Note], bars: int = 8) -> list[Note]:
    return [n.model_copy(update={"start": n.start + bar * 4}) for bar in range(bars) for n in notes]


def _scale(key: str) -> tuple[int, tuple[int, ...]]:
    match = re.fullmatch(r"\s*([A-Ga-g])([#♯b♭]?)\s+(major|minor)\s*", key, re.I)
    if not match:
        return 0, (0, 2, 3, 5, 7, 8, 10)
    name, accidental, mode = match.groups()
    tonic = ({"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}[name.upper()]
             + (1 if accidental in ("#", "♯") else -1 if accidental in ("b", "♭") else 0)) % 12
    return tonic, (0, 2, 4, 5, 7, 9, 11) if mode.lower() == "major" else (0, 2, 3, 5, 7, 8, 10)


class ArrangementPlanner:
    def plan(self, brief: CreativeBrief) -> ArrangementPlan:
        tempo = float(brief.musical_constraints.get("tempo_bpm", 120))
        key = str(brief.musical_constraints.get("key", "C minor"))
        tonic, scale = _scale(key)
        def pitch(degree: int, octave: int) -> int:
            return 12 * octave + tonic + scale[degree % 7] + 12 * (degree // 7)

        # Feedback revises the same initial sketch; it must not reseed it.
        seed_content = {"intent": re.sub(r"\s*\[feedback: .*\]$", "", brief.intent, flags=re.I | re.S),
                        "emotional_dimensions": brief.emotional_dimensions,
                        "musical_constraints": brief.musical_constraints}
        seed = hashlib.sha256(json.dumps(seed_content, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()).digest()
        rng = random.Random(int.from_bytes(seed, "big"))
        emotions = brief.emotional_dimensions
        def level(name: str) -> float:
            return max(0.0, min(1.0, float(emotions.get(name, 0))))
        bright = level("brightness") + level("playfulness") - level("darkness")
        tense = level("tension")
        energy_base = level("energy") + .5 * level("playfulness")
        register = 1 if bright > .25 else -1 if bright < -.25 else 0
        velocity = round(8 * energy_base + 4 * tense)
        drum_seed = [Note(pitch=p, start=s, duration=.18, velocity=max(1, min(127, v + velocity))) for p, s, v in [(36,0,112),(42,.5,72),(42,1.5,70),(38,2,105),(42,2.5,76),(42,3.5,72)]]
        bass_seed = [Note(pitch=pitch(d, 3), start=s, duration=.8, velocity=92 + velocity) for d, s in [(0,0),(0,1),(2,2),(4,3)]]
        harmony_seed = [Note(pitch=pitch(d, 4 + register), start=0, duration=3.8, velocity=54 + velocity) for d in (0,2,4)]
        melody_seed = [Note(pitch=pitch(d, 5 + register), start=s, duration=.45, velocity=78 + velocity) for d, s in [(0,.5),(2,1.25),(4,2),(rng.choice((3, 5)),3)]]
        if bright > .25 or energy_base > .4:
            melody_seed.append(Note(pitch=pitch(1, 5 + register), start=3.5, duration=.25, velocity=74 + velocity))
            bass_seed.append(Note(pitch=pitch(4, 3), start=3.5, duration=.35, velocity=82 + velocity))
        if tense > .25:
            harmony_seed.append(Note(pitch=pitch(1, 4 + register), start=0, duration=3.8, velocity=48 + velocity))
        # The demo appends feedback after interpretation; extract only that suffix
        # so prompt adjectives do not accidentally act as revision instructions.
        match = re.search(r"\[feedback: (.*)\]$", brief.intent, flags=re.I | re.S)
        feedback = match.group(1) if match else ""
        dimensions = parse_feedback(feedback)
        density = dimensions.get("density", 0)
        energy = dimensions.get("energy", 0)
        brightness = dimensions.get("brightness", 0)
        tension = dimensions.get("tension", 0)
        bars = 8 + 4 * dimensions.get("length", 0)

        # Density changes note count and rhythmic subdivision. A named part is
        # revised on its own; otherwise the bass, drums and motif all respond.
        named = {role for role, words in {
            "bass": ("bass",), "drums": ("drum", "drums"),
            "melody": ("melody", "motif"), "harmony": ("harmony", "pad"),
        }.items() if any(re.search(r"\b" + word + r"\b", feedback.lower()) for word in words)}
        def targeted(role: str) -> bool:
            return not named or role in named

        if density < 0:
            if targeted("drums"):
                drum_seed = [n for n in drum_seed if n.pitch != 42 or n.start in (.5, 2.5)]
            if targeted("bass"):
                bass_seed = [n.model_copy(update={"duration": 1.6}) for n in bass_seed if n.start in (0, 2)]
            if targeted("melody"):
                melody_seed = [n for i, n in enumerate(melody_seed) if i % 2 == 0]
        elif density > 0:
            if targeted("drums"):
                drum_seed += [Note(pitch=42, start=s, duration=.18, velocity=65) for s in (1, 2, 3)]
            if targeted("bass"):
                bass_seed += [Note(pitch=p, start=s, duration=.4, velocity=82) for p, s in ((pitch(0, 3),.5), (pitch(2, 3),2.5))]
            if targeted("melody"):
                melody_seed += [Note(pitch=pitch(3, 5 + register), start=2.5, duration=.25, velocity=74)]

        # Brightness shifts the pitched register, energy shifts velocity, and
        # tension adds/removes a dissonant harmony tone and motif articulation.
        def shape(seed: list[Note], role: str) -> list[Note]:
            shaped = []
            for note in seed:
                pitch = note.pitch + (brightness * (3 if role == "bass" else 5) if role != "drums" and targeted(role) else 0)
                velocity = max(1, min(127, note.velocity + 15 * energy))
                duration = note.duration
                if role == "melody" and tension:
                    duration = .25 if tension > 0 else .7
                shaped.append(note.model_copy(update={"pitch": pitch, "velocity": velocity, "duration": duration}))
            return shaped

        if tension > 0:
            harmony_seed.append(Note(pitch=pitch(1, 4 + register), start=0, duration=3.8, velocity=48))
        elif tension < 0:
            harmony_seed = [n for n in harmony_seed if n.pitch != pitch(2, 4 + register)]
        drum_seed = shape(drum_seed, "drums")
        bass_seed = shape(bass_seed, "bass")
        harmony_seed = shape(harmony_seed, "harmony")
        melody_seed = shape(melody_seed, "melody")
        melody_notes = _repeat(melody_seed, bars)
        if re.search(r"\bfinal[- ]bar\b", feedback.lower()) and re.search(r"\b(motif|melody|variation)\b", feedback.lower()):
            melody_notes += [Note(pitch=pitch(4, 5 + register) + brightness * 5, start=(bars - 1) * 4 + 2.5, duration=.45, velocity=max(1, min(127, 84 + 15 * energy)))]
        tracks = [
            TrackPlan(name="MUSE Drums", role="drums", instrument="Ableton Core Kit", notes=_repeat(drum_seed, bars)),
            TrackPlan(name="MUSE Bass", role="bass", instrument="Operator", notes=_repeat(bass_seed, bars)),
            TrackPlan(name="MUSE Atmosphere", role="harmony", instrument="Wavetable", notes=_repeat(harmony_seed, bars)),
            TrackPlan(name="MUSE Motif", role="melody", instrument="Operator", notes=melody_notes),
        ]
        return ArrangementPlan(title="MUSE eight-bar sketch" if bars == 8 else f"MUSE {bars}-bar sketch", tempo=tempo, bars=bars, key=key, tracks=tracks,
                               rationale=["Low register anchors the pulse.", "Sustained harmony leaves room for the motif.", "Final-bar variation can be added during refinement."])
