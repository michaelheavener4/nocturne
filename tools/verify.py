#!/usr/bin/env python3
"""MUSE merge gate: pytest plus an explicit multi-feedback MIDI hash probe.

Usage:
    python tools/verify.py

Exits 0 only when the whole suite passes and distinct feedback produces
distinct, well-formed MIDI files. Prints every probe hash.
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
from midi_assertions import assert_valid_midi  # noqa: E402

PROMPT = "dark and tense, 92 bpm"
FEEDBACKS = (
    "make the bass less busy and let the notes ring",
    "take it darker and move the harmony into a lower register",
    "thin out the drums, add space, and write a new final-bar motif",
)


def _demo_env() -> dict[str, str]:
    env = os.environ.copy()
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = str(SRC) + (os.pathsep + existing if existing else "")
    return env


def _run_demo(workdir: Path, feedback: str) -> tuple[str, str, bytes]:
    data_dir = workdir / f"run-{hashlib.md5(feedback.encode()).hexdigest()[:8]}"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "muse",
            "demo",
            "--prompt",
            PROMPT,
            "--feedback",
            feedback,
            "--data",
            str(data_dir),
        ],
        cwd=workdir,
        env=_demo_env(),
        text=True,
        capture_output=True,
        timeout=120,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"demo failed for {feedback!r} (exit {result.returncode})\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    midi_path = data_dir / "projects" / "muse_sketch.mid"
    if not midi_path.is_file():
        raise RuntimeError(f"demo did not write {midi_path}\nstdout:\n{result.stdout}")
    midi_bytes = midi_path.read_bytes()
    return feedback, hashlib.md5(midi_bytes).hexdigest(), midi_bytes


def run_hash_probe() -> bool:
    print("== multi-feedback hash probe ==")
    print(f"prompt: {PROMPT}")
    try:
        with tempfile.TemporaryDirectory(prefix="muse-verify-") as tmp:
            results = [_run_demo(Path(tmp), feedback) for feedback in FEEDBACKS]
    except Exception as exc:  # noqa: BLE001 - report, then fail the gate
        print(f"PROBE ERROR: {exc}")
        return False

    for feedback, md5, midi_bytes in results:
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


def main() -> int:
    pytest_cmd = [sys.executable, "-m", "pytest", "-q", "tests"]
    print("== pytest ==")
    print("$ " + " ".join(pytest_cmd))
    pytest_result = subprocess.run(pytest_cmd, cwd=REPO_ROOT, env=_demo_env()).returncode
    print(f"pytest: {'PASS' if pytest_result == 0 else 'FAIL'} (exit {pytest_result})")

    probe_ok = run_hash_probe()

    if pytest_result == 0 and probe_ok:
        print("\nGATE PASSED")
        return 0
    print("\nGATE FAILED")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
