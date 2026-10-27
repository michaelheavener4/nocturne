from __future__ import annotations

from collections import Counter
from .models import AnalysisReport, ArrangementPlan


def analyze_arrangement(plan: ArrangementPlan) -> AnalysisReport:
    notes = [n for t in plan.tracks for n in t.notes]
    pitches = [n.pitch for n in notes]
    starts = sorted(n.start for n in notes)
    density = len(notes) / plan.bars
    subdivisions = Counter(round((n.start % 1) * 4) / 4 for n in notes)
    return AnalysisReport(metrics={"note_count": len(notes), "notes_per_bar": round(density, 2),
                                   "pitch_min": min(pitches), "pitch_max": max(pitches),
                                   "unique_onset_subdivisions": len(subdivisions),
                                   "span_beats": round(max(n.start+n.duration for n in notes)-min(starts), 2)},
                          claims=[
                              {"kind":"MEASURED", "statement":"MIDI note count", "value":len(notes), "uncertainty":"Exact for the generated plan."},
                              {"kind":"MEASURED", "statement":"Pitch range in MIDI semitones", "value":f"{min(pitches)}-{max(pitches)}", "uncertainty":"Does not describe timbre or perceived register."},
                              {"kind":"HYPOTHESIS", "statement":"The sustained harmony may create space for a foreground motif.", "source":"Arrangement heuristic; test by listening."},
                          ])


def repetition_report(plan: ArrangementPlan) -> dict[str, float | int | bool]:
    """Measure identical two-bar melody cells and melodic movement."""
    notes = sorted((n for track in plan.tracks if track.role == "melody" for n in track.notes),
                   key=lambda n: (n.start, n.pitch, n.duration))
    cells = []
    for start in range(0, plan.bars * 4, 8):
        cells.append(tuple((n.pitch, n.start - start, n.duration)
                           for n in notes if start <= n.start < start + 8))
    counts = Counter(cells)
    share = max(counts.values(), default=0) / len(cells) if cells else 0.0
    pitches = [n.pitch for n in notes]
    pitch_range = max(pitches) - min(pitches) if pitches else 0
    stepwise = all(abs(b - a) <= 2 for a, b in zip(pitches, pitches[1:]))
    return {"identical_cell_share": share, "range_semitones": pitch_range,
            "stepwise_only": stepwise,
            "repetitive_flag": (share > .75 and bool(cells) and cells[-1] == cells[0])
                               or (pitch_range < 5 and stepwise)}
