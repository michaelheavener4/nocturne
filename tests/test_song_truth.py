from __future__ import annotations

from pathlib import Path

import pytest

from midi_assertions import assert_valid_midi
from song_assertions import (
    DEMO_BASELINE_MD5,
    TEMPLATES,
    SongRender,
    chord_tone_audit,
    determinism_audit,
    form_audit,
    key_audit,
    melody_audit,
    run_song,
    transition_audit,
)


@pytest.fixture(scope="module")
def renders(tmp_path_factory: pytest.TempPathFactory) -> dict[str, SongRender]:
    root = tmp_path_factory.mktemp("song-truth")
    return {
        label: run_song(root, template["prompt"], label=label)
        for label, template in TEMPLATES.items()
    }


@pytest.mark.parametrize("label", list(TEMPLATES))
def test_song_form_integrity(renders: dict[str, SongRender], label: str) -> None:
    template = TEMPLATES[label]
    render = renders[label]
    assert render.prompt == template["prompt"]
    assert_valid_midi(render.midi_bytes)

    report = form_audit(
        render,
        expected_bars=template["bars"],
        expected_roles=template["roles"],
    )
    print(f"{render.md5}  {report['bars']} bars  {template['prompt']}")
    for section in report["sections"]:
        print(
            f"  bar {section['start_bar']:>2} +{section['bars']:<2}  "
            f"{section['name']} ({section['role']}) energy={section['energy']}"
        )
    assert report["bars"] == template["bars"]
    assert sum(section["bars"] for section in report["sections"]) == report["bars"]


@pytest.mark.parametrize("label", list(TEMPLATES))
def test_song_key_truth_song_wide(renders: dict[str, SongRender], label: str) -> None:
    render = renders[label]
    report = key_audit(render)
    print(
        f"{render.prompt}: key={report['key']} scale={report['scale']} "
        f"pitched_notes={report['total']} outside={report['outside']}"
    )
    assert report["total"] > 0
    assert not report["outside"], (
        f"pitched notes left the key {report['key']}: {report['outside']}"
    )
    assert report["share"] == 1.0


@pytest.mark.parametrize("label", list(TEMPLATES))
def test_chord_tone_share_per_section(
    renders: dict[str, SongRender], label: str
) -> None:
    reports = chord_tone_audit(renders[label])
    for report in reports:
        share = "n/a" if report["share"] is None else f"{report['share']:.1%}"
        print(
            f"  {report['role']:<11} {report['name']:<18} "
            f"chord tones {report['chord_tones']:>3}/{report['notes']:<3} = {share}"
        )
        if report["share"] is not None:
            assert report["share"] >= 0.5, (
                f"section {report['name']!r} chord-tone share {report['share']:.1%} "
                "is below 50%"
            )


@pytest.mark.parametrize("label", list(TEMPLATES))
def test_melody_varies_in_drop_or_chorus(
    renders: dict[str, SongRender], label: str
) -> None:
    report = melody_audit(renders[label])
    print(
        f"  verse melody notes={report['verse_notes']} "
        f"hook melody notes={report['hook_notes']} "
        f"differ={report['verse_differs_from_hook']}"
    )
    for run in report["runs"]:
        print(
            f"  repeated run: {run['section']} bar {run['bar']} "
            f"length {run['run']} allowed={run['allowed']}"
        )
    assert not report["violations"], (
        "a drop/chorus repeats an identical melody bar more than twice without "
        f"a flagged final hook return: {report['violations']}"
    )
    assert report["verse_differs_from_hook"], (
        "verse melody notes are identical to the drop/chorus melody notes"
    )


@pytest.mark.parametrize("label", list(TEMPLATES))
def test_transition_bars_and_breakdown(
    renders: dict[str, SongRender], label: str
) -> None:
    reports = transition_audit(renders[label])
    for report in reports:
        if report["role"] == "breakdown":
            print(
                f"  breakdown {report['name']}: {report['drum_notes']} drum notes"
            )
            assert report["drum_notes"] == 0
            continue
        print(
            f"  before {report['role']} {report['name']} at bar "
            f"{report['start_bar']}: pre bar {report['pre_bar']} drums="
            f"{report['pre_drums']} vs median {report['median_drums']}; "
            f"mean pitch={report['pre_mean_pitch']} vs "
            f"{report['median_mean_pitch']}"
        )
        assert report["differs"], (
            f"the bar before {report['name']!r} does not differ from the "
            f"section median: {report}"
        )


@pytest.mark.parametrize("label", list(TEMPLATES))
def test_song_is_deterministic_and_not_the_demo(
    renders: dict[str, SongRender], label: str, tmp_path: Path
) -> None:
    repeat = run_song(tmp_path, TEMPLATES[label]["prompt"], label="repeat")
    report = determinism_audit(renders[label], repeat)
    print(f"  {report['md5']}  {report['prompt']}")
    print(f"  {report['repeat_md5']}  {report['prompt']} (repeat)")
    print(f"  eight-bar demo baseline: {DEMO_BASELINE_MD5}")
    assert report["md5"] == report["repeat_md5"]
    assert report["md5"] != DEMO_BASELINE_MD5
