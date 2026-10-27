from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from midi_assertions import assert_valid_midi
from nocturne.midi import write_midi
from nocturne.models import ArrangementPlan, TrackPlan

FIXTURES = Path(__file__).resolve().parent / "fixtures"
BASE_PLAN_PATH = FIXTURES / "track001_base_plan.json"

# Track 001 v3 is the published baseline from FINDINGS.md /
# revise_track001.py. The base plan is frozen in tests/fixtures so this gate
# measures the writer and note transforms, not whatever the planner currently
# seeds. That keeps it stable while Stream A rewrites arrangement.py.
KNOWN_HASHES = {
    "base": "677dcf582ad908e00570f4b058e263da",
    "v1-bass-thinned": "84cf556a302aa2c805e2440d18446bab",
    "v2-darker-lower": "65b9812b85cab599629d863d2e228dc2",
    "v3-dark-thin-finalbar": "7db06e0cc8c841b044392d45c44da1a4",
}


def _base_plan() -> dict:
    return json.loads(BASE_PLAN_PATH.read_text())


def _clone(plan: dict) -> dict:
    return json.loads(json.dumps(plan))


def _v1_bass_thinned(base: dict) -> dict:
    plan = _clone(base)
    for track in plan["tracks"]:
        if track["role"] == "bass":
            track["notes"] = [
                dict(note, duration=1.6)
                for note in track["notes"]
                if (note["start"] % 4) in (0.0, 2.0)
            ]
    return plan


def _v2_darker_lower(base: dict) -> dict:
    plan = _clone(base)
    for track in plan["tracks"]:
        if track["role"] in ("melody", "harmony"):
            track["notes"] = [dict(note, pitch=note["pitch"] - 5) for note in track["notes"]]
        if track["role"] == "bass":
            track["notes"] = [dict(note, pitch=note["pitch"] - 3) for note in track["notes"]]
    return plan


def _v3_dark_thin_finalbar(base: dict) -> dict:
    plan = _clone(base)
    for track in plan["tracks"]:
        if track["role"] == "bass":
            track["notes"] = [
                dict(note, duration=1.6, pitch=note["pitch"] - 3)
                for note in track["notes"]
                if (note["start"] % 4) in (0.0, 2.0)
            ]
        if track["role"] in ("melody", "harmony"):
            track["notes"] = [dict(note, pitch=note["pitch"] - 5) for note in track["notes"]]
        if track["role"] == "melody":
            track["notes"] += [
                {"pitch": 67, "start": 30.5, "duration": 0.45, "velocity": 84, "confidence": None},
                {"pitch": 70, "start": 31.5, "duration": 0.45, "velocity": 88, "confidence": None},
            ]
    return plan


BUILDERS = {
    "base": lambda base: _clone(base),
    "v1-bass-thinned": _v1_bass_thinned,
    "v2-darker-lower": _v2_darker_lower,
    "v3-dark-thin-finalbar": _v3_dark_thin_finalbar,
}


@pytest.mark.parametrize("revision", list(KNOWN_HASHES))
def test_track001_known_hash(revision: str, tmp_path: Path) -> None:
    plan_dict = BUILDERS[revision](_base_plan())
    plan = ArrangementPlan(**plan_dict)
    output = write_midi(plan, tmp_path / f"track001-{revision}.mid")
    midi_bytes = output.read_bytes()
    assert_valid_midi(midi_bytes)
    digest = hashlib.md5(midi_bytes).hexdigest()
    print(f"track001-{revision}: {digest}")
    assert digest == KNOWN_HASHES[revision], (
        f"Track 001 {revision} output changed: {digest} != {KNOWN_HASHES[revision]}. "
        "The published baseline in FINDINGS.md is no longer reproducible."
    )


def test_fixture_still_parses_as_the_published_plan_shape() -> None:
    plan = ArrangementPlan(**_base_plan())
    assert plan.title == "MUSE eight-bar sketch"  # the fixture is the frozen published plan from Finding 001; it keeps its period name on purpose
    assert plan.tempo == 92.0
    assert plan.key == "A minor"
    assert {track.role for track in plan.tracks} == {"drums", "bass", "harmony", "melody"}
    for track in plan.tracks:
        assert isinstance(track, TrackPlan)
        assert track.notes
