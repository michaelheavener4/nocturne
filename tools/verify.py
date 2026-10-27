#!/usr/bin/env python3
"""MUSE merge gate: pytest plus explicit MIDI truth probes.

Usage:
    python tools/verify.py

Exits 0 only when the whole suite passes, feedback changes the output, the
prompt composes a distinct and key-correct sketch, and repeated prompts are
deterministic. Prints every probe hash.
"""
from __future__ import annotations

import hashlib
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
TESTS = REPO_ROOT / "tests"

sys.path.insert(0, str(TESTS))
from midi_assertions import (  # noqa: E402
    assert_valid_midi,
    expected_scale_pitch_classes,
    parse_prompt_key,
    pitched_pitch_classes,
)

PROMPT = "dark and tense, 92 bpm"
FEEDBACKS = (
    "make the bass less busy and let the notes ring",
    "take it darker and move the harmony into a lower register",
    "thin out the drums, add space, and write a new final-bar motif",
)
DARK_PROMPT = "dark and tense, D minor, 92 bpm"
BRIGHT_PROMPT = "bright and playful, C major, 120 bpm"
# Same mood and tempo as DARK_PROMPT; only the named key changes.
KEY_VARIANT_PROMPT = "dark and tense, C major, 92 bpm"


def _demo_env() -> dict[str, str]:
    env = os.environ.copy()
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = str(SRC) + (os.pathsep + existing if existing else "")
    return env


def _run_demo(
    workdir: Path,
    feedback: str | None = None,
    prompt: str = PROMPT,
) -> tuple[str, str, bytes]:
    workdir.mkdir(parents=True, exist_ok=True)
    run_label = f"{prompt}\0{feedback or ''}".encode()
    data_dir = workdir / f"run-{hashlib.md5(run_label).hexdigest()[:8]}"
    command = [
        sys.executable,
        "-m",
        "muse",
        "demo",
        "--prompt",
        prompt,
        "--data",
        str(data_dir),
    ]
    if feedback is not None:
        command += ["--feedback", feedback]
    result = subprocess.run(
        command,
        cwd=workdir,
        env=_demo_env(),
        text=True,
        capture_output=True,
        timeout=120,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"demo failed for prompt={prompt!r} feedback={feedback!r} "
            f"(exit {result.returncode})\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    midi_path = data_dir / "projects" / "muse_sketch.mid"
    if not midi_path.is_file():
        raise RuntimeError(f"demo did not write {midi_path}\nstdout:\n{result.stdout}")
    midi_bytes = midi_path.read_bytes()
    return prompt, hashlib.md5(midi_bytes).hexdigest(), midi_bytes


def run_hash_probe() -> bool:
    print("== multi-feedback hash probe ==")
    print(f"prompt: {PROMPT}")
    try:
        with tempfile.TemporaryDirectory(prefix="muse-verify-") as tmp:
            results = [_run_demo(Path(tmp), feedback) for feedback in FEEDBACKS]
    except Exception as exc:  # noqa: BLE001 - report, then fail the gate
        print(f"PROBE ERROR: {exc}")
        return False

    for feedback, (_, md5, midi_bytes) in zip(FEEDBACKS, results):
        try:
            assert_valid_midi(midi_bytes)
            validity = "valid MIDI"
        except AssertionError as exc:
            validity = f"INVALID MIDI: {exc}"
        print(f"  {md5}  {validity:<11}  {feedback}")

    hashes = [md5 for _, md5, _ in results]
    distinct = len(set(hashes)) == len(hashes)
    if distinct:
        print(f"probe: PASS ({len(hashes)} distinct hashes)")
    else:
        print(
            f"probe: FAIL (feedback is cosmetic: {len(set(hashes))} distinct "
            f"hash(es) across {len(hashes)} runs)"
        )
    return distinct


def run_prompt_sensitivity_probe() -> bool:
    print("== prompt sensitivity probe ==")
    try:
        with tempfile.TemporaryDirectory(prefix="muse-prompt-") as tmp:
            dark = _run_demo(Path(tmp) / "dark", prompt=DARK_PROMPT)
            bright = _run_demo(Path(tmp) / "bright", prompt=BRIGHT_PROMPT)
    except Exception as exc:  # noqa: BLE001 - report, then fail the gate
        print(f"PROBE ERROR: {exc}")
        return False

    for prompt, md5, midi_bytes in (dark, bright):
        try:
            assert_valid_midi(midi_bytes)
            validity = "valid MIDI"
        except AssertionError as exc:
            validity = f"INVALID MIDI: {exc}"
        print(f"  {md5}  {validity:<11}  {prompt}")

    distinct = dark[1] != bright[1]
    if distinct:
        print("probe: PASS (contrasting prompts produced distinct hashes)")
    else:
        print("probe: FAIL (the prompt is cosmetic: contrasting prompts share a hash)")
    return distinct


def run_key_truth_probe() -> bool:
    print("== key truth probe ==")
    prompts = (DARK_PROMPT, BRIGHT_PROMPT, KEY_VARIANT_PROMPT)
    try:
        with tempfile.TemporaryDirectory(prefix="muse-key-") as tmp:
            results = {
                prompt: _run_demo(Path(tmp) / str(index), prompt=prompt)
                for index, prompt in enumerate(prompts)
            }
    except Exception as exc:  # noqa: BLE001 - report, then fail the gate
        print(f"PROBE ERROR: {exc}")
        return False

    all_in_key = True
    for prompt, (_, md5, midi_bytes) in results.items():
        try:
            assert_valid_midi(midi_bytes)
            actual = pitched_pitch_classes(midi_bytes)
        except AssertionError as exc:
            print(f"  {md5}  INVALID MIDI: {exc}  {prompt}")
            all_in_key = False
            continue
        expected = expected_scale_pitch_classes(prompt)
        outside = sorted(actual - expected)
        in_key = bool(actual) and not outside
        all_in_key = all_in_key and in_key
        print(
            f"  {md5}  key={parse_prompt_key(prompt)}  "
            f"outside={outside}  {prompt}"
        )

    dark_set = pitched_pitch_classes(results[DARK_PROMPT][2])
    variant_set = pitched_pitch_classes(results[KEY_VARIANT_PROMPT][2])
    key_changes_output = dark_set != variant_set
    print(f"  D minor pitch classes: {sorted(dark_set)}")
    print(f"  C major pitch classes: {sorted(variant_set)}")

    if all_in_key and key_changes_output:
        print("probe: PASS (pitched notes follow the prompt key and change with it)")
    else:
        reasons = []
        if not all_in_key:
            reasons.append("pitched notes leave the prompt key")
        if not key_changes_output:
            reasons.append("changing only the key did not change the pitch-class set")
        print(f"probe: FAIL ({'; '.join(reasons)})")
    return all_in_key and key_changes_output


def run_determinism_probe() -> bool:
    print("== determinism probe ==")
    try:
        with tempfile.TemporaryDirectory(prefix="muse-determinism-") as tmp:
            first = _run_demo(Path(tmp) / "first", prompt=DARK_PROMPT)
            repeat = _run_demo(Path(tmp) / "repeat", prompt=DARK_PROMPT)
    except Exception as exc:  # noqa: BLE001 - report, then fail the gate
        print(f"PROBE ERROR: {exc}")
        return False

    print(f"  {first[1]}  {DARK_PROMPT}")
    print(f"  {repeat[1]}  {DARK_PROMPT} (repeat)")
    deterministic = first[1] == repeat[1]
    if deterministic:
        print("probe: PASS (same prompt produced identical hashes)")
    else:
        print("probe: FAIL (same prompt produced different hashes)")
    return deterministic


def main() -> int:
    pytest_cmd = [sys.executable, "-m", "pytest", "-q", "tests"]
    print("== pytest ==")
    print("$ " + " ".join(pytest_cmd))
    pytest_result = subprocess.run(pytest_cmd, cwd=REPO_ROOT, env=_demo_env()).returncode
    print(f"pytest: {'PASS' if pytest_result == 0 else 'FAIL'} (exit {pytest_result})")

    probes = {
        "feedback hash": run_hash_probe(),
        "prompt sensitivity": run_prompt_sensitivity_probe(),
        "key truth": run_key_truth_probe(),
        "determinism": run_determinism_probe(),
    }

    print("\n== probe summary ==")
    for name, passed in probes.items():
        print(f"  {'PASS' if passed else 'FAIL'}  {name}")

    if pytest_result == 0 and all(probes.values()):
        print("\nGATE PASSED")
        return 0
    print("\nGATE FAILED")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
