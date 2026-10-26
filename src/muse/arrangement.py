from __future__ import annotations

from .models import ArrangementPlan, CreativeBrief, Note, TrackPlan
from .intent import parse_feedback
import re


def _repeat(notes: list[Note], bars: int = 8) -> list[Note]:
    return [n.model_copy(update={"start": n.start + bar * 4}) for bar in range(bars) for n in notes]


class ArrangementPlanner:
    def plan(self, brief: CreativeBrief) -> ArrangementPlan:
        tempo = float(brief.musical_constraints.get("tempo_bpm", 120))
        key = str(brief.musical_constraints.get("key", "C minor"))
        drum_seed = [Note(pitch=p, start=s, duration=.18, velocity=v) for p, s, v in [(36,0,112),(42,.5,72),(42,1.5,70),(38,2,105),(42,2.5,76),(42,3.5,72)]]
        bass_seed = [Note(pitch=p, start=s, duration=.8, velocity=92) for p, s in [(48,0),(48,1),(51,2),(46,3)]]
        harmony_seed = [Note(pitch=p, start=0, duration=3.8, velocity=54) for p in (48,51,55)]
        melody_seed = [Note(pitch=p, start=s, duration=.45, velocity=78) for p, s in [(60,.5),(63,1.25),(67,2),(65,3)]]
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
                bass_seed += [Note(pitch=p, start=s, duration=.4, velocity=82) for p, s in ((48,.5), (51,2.5))]
            if targeted("melody"):
                melody_seed += [Note(pitch=65, start=2.5, duration=.25, velocity=74)]

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
            harmony_seed.append(Note(pitch=54, start=0, duration=3.8, velocity=48))
        elif tension < 0:
            harmony_seed = [n for n in harmony_seed if n.pitch != 51]
        drum_seed = shape(drum_seed, "drums")
        bass_seed = shape(bass_seed, "bass")
        harmony_seed = shape(harmony_seed, "harmony")
        melody_seed = shape(melody_seed, "melody")
        melody_notes = _repeat(melody_seed, bars)
        if re.search(r"\bfinal[- ]bar\b", feedback.lower()) and re.search(r"\b(motif|melody|variation)\b", feedback.lower()):
            melody_notes += [Note(pitch=67 + brightness * 5, start=(bars - 1) * 4 + 2.5, duration=.45, velocity=max(1, min(127, 84 + 15 * energy)))]
        tracks = [
            TrackPlan(name="MUSE Drums", role="drums", instrument="Ableton Core Kit", notes=_repeat(drum_seed, bars)),
            TrackPlan(name="MUSE Bass", role="bass", instrument="Operator", notes=_repeat(bass_seed, bars)),
            TrackPlan(name="MUSE Atmosphere", role="harmony", instrument="Wavetable", notes=_repeat(harmony_seed, bars)),
            TrackPlan(name="MUSE Motif", role="melody", instrument="Operator", notes=melody_notes),
        ]
        return ArrangementPlan(title="MUSE eight-bar sketch" if bars == 8 else f"MUSE {bars}-bar sketch", tempo=tempo, bars=bars, key=key, tracks=tracks,
                               rationale=["Low register anchors the pulse.", "Sustained harmony leaves room for the motif.", "Final-bar variation can be added during refinement."])
