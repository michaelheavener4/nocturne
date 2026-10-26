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
