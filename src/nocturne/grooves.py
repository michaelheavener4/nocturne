"""Sixteenth-step drum presets and reusable groove timing helpers."""
from __future__ import annotations

from .models import Note

GM_PERCUSSION = {
    "kick": 36, "rim": 37, "snare": 38, "clap": 39, "closed_hat": 42,
    "open_hat": 46, "crash": 49, "ride": 51, "maracas": 70, "shaker": 82,
}

GROOVE_PRESETS = {
    "house": {"kick": [0, 4, 8, 12], "snare": [4, 12], "hat": list(range(16)), "open_hat": [2, 6, 10, 14], "ghost": False},
    "backbeat": {"kick": [0, 8], "snare": [4, 12], "hat": list(range(0, 16, 2)), "open_hat": [], "ghost": False},
    "trap": {"kick": [0, 10], "snare": [8], "hat": list(range(16)), "open_hat": [], "ghost": True},
    "dubstep": {"kick": [0], "snare": [8], "hat": list(range(0, 16, 2)), "open_hat": [], "ghost": False},
    "dnb": {"kick": [0, 10], "snare": [4, 12], "hat": list(range(16)), "open_hat": [], "ghost": True},
    "dembow": {"kick": [0, 8], "snare": [3, 6, 11, 14], "hat": list(range(0, 16, 2)), "open_hat": [], "ghost": False},
    "dembow_b": {"kick": [0, 8], "snare": [0, 3, 6, 8, 11, 14], "hat": list(range(0, 16, 2)), "open_hat": [], "ghost": False},
}

# Practitioner-consensus editable defaults, not measured facts.
GENRE_SWING = {"house": 54, "backbeat": 50, "trap": 52, "dubstep": 50, "dnb": 51, "dembow": 50}

BASS_GRIDS = {
    "offbeat": [2, 6, 10, 14],
    "double_offbeat": [2, 3, 6, 7, 10, 11, 14, 15],
    "rolling": list(range(16)),
}

# Reserve frequencies below this for kick and sub; documentation only, no DSP.
MONO_SUB_HZ = 120


def apply_swing(notes: list[Note], swing_pct: float) -> list[Note]:
    """Copy notes, delaying on-grid odd sixteenths (one step = .25 beats).

    Accepts any note-like object with a ``start`` attribute: pydantic Notes
    are copied via model_copy, anything else via a shallow copy. The input
    objects are never mutated.
    """
    import copy as _copy

    delay = (swing_pct - 50) / 100 * .5
    result = []
    for note in notes:
        step = note.start / .25
        odd = abs(step - round(step)) < 1e-9 and round(step) % 2 == 1
        new_start = note.start + delay if odd else note.start
        if hasattr(note, "model_copy"):
            result.append(note.model_copy(update={"start": new_start}))
        else:
            clone = _copy.copy(note)
            clone.start = new_start
            result.append(clone)
    return result


def ghost_velocity(backbeat_velocity: int) -> int:
    return max(1, int(backbeat_velocity * .32))


def sidechain_release_ms(bpm: float, requested_ms: float = 300) -> float:
    return min(requested_ms, .9 * 60000 / bpm)
