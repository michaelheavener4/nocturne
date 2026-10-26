from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from pathlib import Path

from midi_assertions import assert_valid_midi

REPO_ROOT = Path(__file__).resolve().parents[1]
PROMPT = "dark and tense, 92 bpm"
FEEDBACKS = (
    "make the bass less busy and let the notes ring",
    "take it darker and move the harmony into a lower register",
    "thin out the drums, add space, and write a new final-bar motif",
)


def _run_demo(workdir: Path, feedback: str) -> tuple[str, str, bytes]:
    data_dir = workdir / f"run-{hashlib.md5(feedback.encode()).hexdigest()[:8]}"
    env = os.environ.copy()
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = str(REPO_ROOT / "src") + (os.pathsep + existing if existing else "")
    command = [
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
    ]
    result = subprocess.run(
        command,
        cwd=workdir,
        env=env,
        text=True,
        capture_output=True,
        timeout=120,
    )
    if result.returncode != 0:
        raise AssertionError(
            f"demo failed for feedback {feedback!r} (exit {result.returncode})\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    midi_path = data_dir / "projects" / "muse_sketch.mid"
    assert midi_path.is_file(), f"demo did not write {midi_path}\nstdout:\n{result.stdout}"
    midi_bytes = midi_path.read_bytes()
    return feedback, hashlib.md5(midi_bytes).hexdigest(), midi_bytes


def test_feedback_changes_midi_output(tmp_path: Path) -> None:
    """Finding 001 gate: distinct feedback must produce distinct MIDI bytes.

    This test is expected to FAIL against the v1 planner, where feedback is
    parsed and stored but never reaches note generation. It must PASS once the
    planner fix (Stream A) actually consumes feedback.
    """
    results = [_run_demo(tmp_path, feedback) for feedback in FEEDBACKS]

    for feedback, md5, midi_bytes in results:
        assert_valid_midi(midi_bytes)
        print(f"{md5}  {feedback}")

    hashes = [md5 for _, md5, _ in results]
    detail = "\n".join(f"  {md5}  {feedback}" for feedback, md5, _ in results)
    assert len(set(hashes)) == len(hashes), (
        "feedback is cosmetic: materially different feedback produced the same "
        f"MIDI bytes ({len(set(hashes))} distinct hash(es) across {len(hashes)} runs)\n"
        f"{detail}\n"
        "Expected the planner fix to make each feedback input change the rendered notes."
    )
