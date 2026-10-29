"""JSON export of an arrangement plan for web players."""

from __future__ import annotations

import re

from .analysis import contrast_report
from .models import ArrangementPlan, CreativeBrief, Note, TrackPlan
from .song import form_used

_KEY_MODE_RE = re.compile(
    r"\s*([A-Ga-g])([#♯b♭]?)\s+(major|minor)\s*\Z",
    re.IGNORECASE,
)
_CONTRAST_FORMS = frozenset({"pop", "pop84"})


def song_to_json(plan: ArrangementPlan, brief: CreativeBrief | None = None) -> dict:
    """Return a JSON-serializable snapshot of ``plan``.

    The same plan always produces the same dict. Note order follows each
    track's list, and form order follows ``plan.form``. Contrast is the
    analysis report for pop and pop84 plans, and null otherwise.
    """
    payload: dict = {
        "title": _title(plan, brief),
        "tempo_bpm": float(plan.tempo),
    }
    key = str(plan.key).strip()
    if key:
        payload["key"] = key
        mode = _mode(key)
        if mode is not None:
            payload["mode"] = mode
    payload["form"] = [
        {"name": section.name, "bars": int(section.bars)} for section in plan.form
    ]
    payload["tracks"] = [_track_json(track) for track in plan.tracks]
    payload["contrast"] = (
        contrast_report(plan) if form_used(plan) in _CONTRAST_FORMS else None
    )
    return payload


def _title(plan: ArrangementPlan, brief: CreativeBrief | None) -> str:
    if brief is not None:
        intent = brief.intent.strip()
        if intent:
            return intent
    title = str(plan.title).strip()
    return title or "Untitled"


def _mode(key: str) -> str | None:
    match = _KEY_MODE_RE.fullmatch(key)
    if match is None:
        return None
    return match.group(3).lower()


def _track_json(track: TrackPlan) -> dict:
    return {
        "name": track.name,
        "notes": [_note_json(note) for note in track.notes],
    }


def _note_json(note: Note) -> dict:
    return {
        "pitch": int(note.pitch),
        "start_beats": float(note.start),
        "duration_beats": float(note.duration),
        "velocity": int(note.velocity),
    }
