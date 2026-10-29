"""Player JSON export: round-trip, note counts, and contrast by form."""

from __future__ import annotations

import json

from nocturne.analysis import contrast_report
from nocturne.export import song_to_json
from nocturne.intent import IntentInterpreter
from nocturne.models import ArrangementPlan, CreativeBrief, Note, TrackPlan
from nocturne.song import plan_song

POP84_PROMPT = "bright chart pop song, C major, 120 bpm"
EDM_PROMPT = "dark and tense EDM track, D minor, 128 bpm"


def _plan(prompt: str, form: str):
    brief = IntentInterpreter().interpret(prompt)
    return brief, plan_song(brief, form=form)


def test_json_round_trips() -> None:
    brief, plan = _plan(POP84_PROMPT, "pop84")
    payload = song_to_json(plan, brief)
    assert json.loads(json.dumps(payload)) == payload
    assert song_to_json(plan, brief) == payload


def test_note_counts_match_plan_tracks() -> None:
    _brief, plan = _plan(EDM_PROMPT, "edm")
    payload = song_to_json(plan)
    assert [track["name"] for track in payload["tracks"]] == [track.name for track in plan.tracks]
    for exported, track in zip(payload["tracks"], plan.tracks, strict=True):
        assert len(exported["notes"]) == len(track.notes)
        for note, source in zip(exported["notes"], track.notes, strict=True):
            assert note == {
                "pitch": source.pitch,
                "start_beats": source.start,
                "duration_beats": source.duration,
                "velocity": source.velocity,
            }
    roles = {track.role for track in plan.tracks}
    assert {"melody", "bass", "drums"} <= roles


def test_pop84_contrast_has_chorus_above_verse() -> None:
    brief, plan = _plan(POP84_PROMPT, "pop84")
    payload = song_to_json(plan, brief)
    assert payload["contrast"] is not None
    assert payload["contrast"] == contrast_report(plan)
    chorus = payload["contrast"]["chorus"]
    verse = payload["contrast"]["verse"]
    assert chorus["mean_melody_velocity"] > verse["mean_melody_velocity"]
    assert chorus["mean_melody_pitch"] > verse["mean_melody_pitch"]
    assert payload["title"] == brief.intent
    assert payload["tempo_bpm"] == plan.tempo
    assert payload["key"] == plan.key
    assert payload["mode"] == "major"
    assert payload["form"] == [
        {"name": section.name, "bars": section.bars} for section in plan.form
    ]


def test_edm_exports_with_null_contrast() -> None:
    _brief, plan = _plan(EDM_PROMPT, "edm")
    payload = song_to_json(plan)
    assert payload["contrast"] is None
    assert payload["title"] == plan.title
    assert payload["tempo_bpm"] == plan.tempo
    assert payload["key"] == plan.key
    assert payload["mode"] == "minor"
    assert payload["tracks"]
    assert json.loads(json.dumps(payload)) == payload


def test_blank_title_falls_back_to_untitled() -> None:
    plan = ArrangementPlan(
        title="  ",
        tempo=100,
        bars=1,
        key="F# minor",
        tracks=[
            TrackPlan(
                name="NOCTURNE Drums",
                role="drums",
                instrument="kit",
                notes=[Note(pitch=36, start=0, duration=0.25, velocity=100)],
            )
        ],
    )
    assert song_to_json(plan)["title"] == "Untitled"
    assert song_to_json(plan)["mode"] == "minor"
    titled = song_to_json(plan, CreativeBrief(intent="Night bus"))
    assert titled["title"] == "Night bus"
    assert titled["contrast"] is None
