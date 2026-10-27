"""Gate v5: the Build 5 research contract (R-001/R-002/R-003).

Mood-named progressions with bass roots that follow them, hook statements
that repeat rhythm and vary pitch, the 96-bar club form with contract
build anatomy, a repetition report that flags flat plans, and club
determinism that leaves the eight-bar groove baseline untouched.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from demo_runner import run_demo
from midi_assertions import assert_valid_midi
from research_assertions import (
    MOOD_PROMPTS,
    build_anatomy_audit,
    club_form_audit,
    hook_audit,
    progression_audit,
    repetition_audit,
)
from song_assertions import DEMO_BASELINE_MD5, SongRender, run_song

MOODS = ("dark", "euphoric", "brooding", "driving")


@pytest.fixture(scope="module")
def renders(tmp_path_factory: pytest.TempPathFactory) -> dict[str, SongRender]:
    root = tmp_path_factory.mktemp("song-research")
    out: dict[str, SongRender] = {
        mood: run_song(root, MOOD_PROMPTS[mood], label=mood, form="edm")
        for mood in MOODS
    }
    out["club"] = run_song(root, MOOD_PROMPTS["club"], label="club", form="club")
    out["club_repeat"] = run_song(
        root, MOOD_PROMPTS["club"], label="club-repeat", form="club"
    )
    return out


@pytest.mark.parametrize("mood", list(MOODS) + ["club"])
def test_progression_truth(renders: dict[str, SongRender], mood: str) -> None:
    render = renders[mood]
    assert_valid_midi(render.midi_bytes)
    report = progression_audit(render, mood)
    print(
        f"{render.md5}  {mood}: progression={report['name']} "
        f"{report['cycle']} across {report['bars_checked']} bars"
    )


def test_hook_structure(renders: dict[str, SongRender]) -> None:
    report = hook_audit(renders["dark"])
    print(f"hook in {report['section']}: {report}")
    assert report["s2_rhythm_matches_s1"]
    assert report["s4_rhythm_matches_s1"]
    assert report["s2_pitches_differ"]
    assert report["s4_pitches_differ"]
    assert report["s1_max_interval"] >= 5


def test_club_form_and_build_anatomy(renders: dict[str, SongRender]) -> None:
    render = renders["club"]
    form = club_form_audit(render)
    print(f"{render.md5}  club form: {form['sections']} = {form['bars']} bars")
    progression_audit(render, "club")
    for build in build_anatomy_audit(render):
        print(
            f"  build at bar {build['start_bar']}: snare={build['snare_counts']} "
            f"kick={build['kick_counts']}"
        )


def test_repetition_report_flags_flat_and_clears_varied() -> None:
    report = repetition_audit()
    print(f"flat: {report['flat']}")
    print(f"varied: {report['varied']}")
    assert report["flat"]["repetitive_flag"]
    assert not report["varied"]["repetitive_flag"]


def test_club_determinism_and_groove_baseline(
    renders: dict[str, SongRender], tmp_path: Path
) -> None:
    first, repeat = renders["club"], renders["club_repeat"]
    print(f"{first.md5}  club")
    print(f"{repeat.md5}  club (repeat)")
    assert first.md5 == repeat.md5
    assert first.md5 != DEMO_BASELINE_MD5

    _, groove_md5, _ = run_demo(tmp_path, "dark and tense, 92 bpm")
    print(f"{groove_md5}  eight-bar groove baseline")
    assert groove_md5 == DEMO_BASELINE_MD5
