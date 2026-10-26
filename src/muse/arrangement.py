from __future__ import annotations

from .models import ArrangementPlan, CreativeBrief, Note, TrackPlan


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
        tracks = [
            TrackPlan(name="MUSE Drums", role="drums", instrument="Ableton Core Kit", notes=_repeat(drum_seed)),
            TrackPlan(name="MUSE Bass", role="bass", instrument="Operator", notes=_repeat(bass_seed)),
            TrackPlan(name="MUSE Atmosphere", role="harmony", instrument="Wavetable", notes=_repeat(harmony_seed)),
            TrackPlan(name="MUSE Motif", role="melody", instrument="Operator", notes=_repeat(melody_seed)),
        ]
        return ArrangementPlan(title="MUSE eight-bar sketch", tempo=tempo, bars=8, key=key, tracks=tracks,
                               rationale=["Low register anchors the pulse.", "Sustained harmony leaves room for the motif.", "Final-bar variation can be added during refinement."])
