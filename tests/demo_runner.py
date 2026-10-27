from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def run_demo(
    workdir: Path,
    prompt: str,
    feedback: str | None = None,
) -> tuple[str, str, bytes]:
    """Run the full demo pipeline and return (prompt, md5, midi bytes)."""
    workdir.mkdir(parents=True, exist_ok=True)
    run_label = f"{prompt}\0{feedback or ''}".encode()
    data_dir = workdir / f"run-{hashlib.md5(run_label).hexdigest()[:8]}"
    command = [
        sys.executable,
        "-m",
        "nocturne",
        "demo",
        "--prompt",
        prompt,
        "--data",
        str(data_dir),
    ]
    if feedback is not None:
        command += ["--feedback", feedback]

    env = os.environ.copy()
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = str(REPO_ROOT / "src") + (
        os.pathsep + existing if existing else ""
    )
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
            f"demo failed for prompt={prompt!r} feedback={feedback!r} "
            f"(exit {result.returncode})\nstdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )
    midi_path = data_dir / "projects" / "muse_sketch.mid"
    if not midi_path.is_file():
        raise AssertionError(
            f"demo did not write {midi_path}\nstdout:\n{result.stdout}"
        )
    midi_bytes = midi_path.read_bytes()
    return prompt, hashlib.md5(midi_bytes).hexdigest(), midi_bytes
