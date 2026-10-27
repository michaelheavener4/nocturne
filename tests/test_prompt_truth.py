from __future__ import annotations

import pytest

from demo_runner import run_demo
from midi_assertions import (
    assert_valid_midi,
    expected_scale_pitch_classes,
    parse_prompt_key,
    pitched_pitch_classes,
)

DARK_PROMPT = "dark and tense, D minor, 92 bpm"
BRIGHT_PROMPT = "bright and playful, C major, 120 bpm"
# Same mood and tempo as DARK_PROMPT; only the named key changes.
KEY_VARIANT_PROMPT = "dark and tense, C major, 92 bpm"

PROMPTS = {
    "dark": DARK_PROMPT,
    "bright": BRIGHT_PROMPT,
    "key-variant": KEY_VARIANT_PROMPT,
}


@pytest.fixture(scope="module")
def renders(tmp_path_factory: pytest.TempPathFactory) -> dict[str, tuple[str, str, bytes]]:
    root = tmp_path_factory.mktemp("prompt-truth")
    results = {
        label: run_demo(root / label, prompt)
        for label, prompt in PROMPTS.items()
    }
    results["dark-repeat"] = run_demo(root / "dark-repeat", DARK_PROMPT)
    results["bright-repeat"] = run_demo(root / "bright-repeat", BRIGHT_PROMPT)
    return results


def test_contrasting_prompts_produce_distinct_hashes(
    renders: dict[str, tuple[str, str, bytes]],
) -> None:
    dark = renders["dark"]
    bright = renders["bright"]
    assert_valid_midi(dark[2])
    assert_valid_midi(bright[2])
    print(f"{dark[1]}  {DARK_PROMPT}")
    print(f"{bright[1]}  {BRIGHT_PROMPT}")
    assert dark[1] != bright[1], (
        "the prompt is cosmetic: contrasting prompts produced identical MIDI bytes\n"
        f"  {dark[1]}  {DARK_PROMPT}\n"
        f"  {bright[1]}  {BRIGHT_PROMPT}"
    )


@pytest.mark.parametrize("label", list(PROMPTS))
def test_pitched_notes_follow_prompt_key(
    renders: dict[str, tuple[str, str, bytes]],
    label: str,
) -> None:
    prompt, _, midi_bytes = renders[label]
    assert_valid_midi(midi_bytes)
    expected = expected_scale_pitch_classes(prompt)
    actual = pitched_pitch_classes(midi_bytes)
    outside = sorted(actual - expected)
    key = parse_prompt_key(prompt)
    print(f"{key}: expected={sorted(expected)} actual={sorted(actual)}")
    assert actual, f"no pitched notes found in output for {prompt!r}"
    assert not outside, (
        f"pitched notes leave the prompt key {key} for {prompt!r}: "
        f"outside pitch classes {outside} (actual {sorted(actual)}, "
        f"expected subset of {sorted(expected)})"
    )


def test_key_change_changes_pitch_class_set(
    renders: dict[str, tuple[str, str, bytes]],
) -> None:
    dark_pitch_classes = pitched_pitch_classes(renders["dark"][2])
    variant_pitch_classes = pitched_pitch_classes(renders["key-variant"][2])
    print(f"D minor pitch classes: {sorted(dark_pitch_classes)}")
    print(f"C major pitch classes: {sorted(variant_pitch_classes)}")
    assert dark_pitch_classes != variant_pitch_classes, (
        "changing only the prompt key did not change the output's pitch-class set "
        f"({sorted(dark_pitch_classes)}); the key is a label, not a musical input"
    )


@pytest.mark.parametrize(
    ("label", "repeat_label"),
    [("dark", "dark-repeat"), ("bright", "bright-repeat")],
)
def test_same_prompt_is_deterministic(
    renders: dict[str, tuple[str, str, bytes]],
    label: str,
    repeat_label: str,
) -> None:
    first_hash = renders[label][1]
    repeat_hash = renders[repeat_label][1]
    print(f"{first_hash}  {renders[label][0]}")
    print(f"{repeat_hash}  {renders[repeat_label][0]} (repeat)")
    assert first_hash == repeat_hash, (
        "the same prompt produced different MIDI bytes across runs: "
        f"{first_hash} != {repeat_hash}"
    )
