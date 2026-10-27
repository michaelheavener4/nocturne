from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from midi_assertions import assert_valid_midi

REPO_ROOT = Path(__file__).resolve().parents[1]
CREATE_PROMPT = "Make a dark and tense groove at 92 bpm."
REVISE_DARKER = "take it darker and move the harmony into a lower register"
REVISE_THIN_DRUMS = "thin out the drums, add space, and write a new final-bar motif"
PRESERVE_BASS = "keep the bass, thinner drums"


def run_session(
    workdir: Path,
    says: list[str],
    *,
    offline: bool = True,
) -> tuple[subprocess.CompletedProcess[str], Path]:
    """Run the scripted session driver and return (process, data directory)."""
    data_dir = workdir / "session"
    data_dir.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = str(REPO_ROOT / "src") + (os.pathsep + existing if existing else "")

    command = [sys.executable, "-m", "nocturne", "session", "--data", str(data_dir)]
    if offline:
        command.append("--offline")
    for text in says:
        command += ["--say", text]

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
            f"nocturne session failed (exit {result.returncode})\n"
            f"command: {' '.join(command)}\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    return result, data_dir


def read_ledger(data_dir: Path) -> list[dict]:
    path = data_dir / "rounds.jsonl"
    assert path.is_file(), f"session did not write the rounds ledger at {path}"
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def round_path(data_dir: Path, n: int, suffix: str) -> Path:
    return data_dir / "rounds" / f"round-{n:03d}{suffix}"


def read_round_plan(data_dir: Path, n: int) -> dict:
    path = round_path(data_dir, n, ".json")
    assert path.is_file(), f"session did not write the round plan at {path}"
    return json.loads(path.read_text())


def notes_for_role(plan: dict, role: str) -> list[dict]:
    tracks = plan.get("tracks")
    if tracks is None and isinstance(plan.get("plan"), dict):
        tracks = plan["plan"].get("tracks")
    assert isinstance(tracks, list), f"round plan has no tracks list: {sorted(plan)}"
    matches = [track for track in tracks if track.get("role") == role]
    assert len(matches) == 1, f"expected one {role!r} track, found {len(matches)}"
    notes = matches[0].get("notes")
    assert isinstance(notes, list), f"{role!r} track has no notes list"
    return notes


def test_session_ledger_integrity(tmp_path: Path) -> None:
    says = [CREATE_PROMPT, REVISE_DARKER, REVISE_THIN_DRUMS]
    result, data_dir = run_session(tmp_path, says)
    rounds = read_ledger(data_dir)

    assert [record["n"] for record in rounds] == [0, 1, 2]
    assert [record["kind"] for record in rounds] == ["create", "revise", "revise"]
    assert [record["text"] for record in rounds] == says

    hashes = []
    for record in rounds:
        midi_path = round_path(data_dir, record["n"], ".mid")
        plan_path = round_path(data_dir, record["n"], ".json")
        assert midi_path.is_file(), f"missing round MIDI {midi_path}"
        assert plan_path.is_file(), f"missing round plan {plan_path}"
        midi_bytes = midi_path.read_bytes()
        assert_valid_midi(midi_bytes)
        digest = hashlib.md5(midi_bytes).hexdigest()
        assert record["md5"] == digest, (
            f"round {record['n']} ledger md5 {record['md5']} does not match "
            f"{midi_path} ({digest})"
        )
        assert isinstance(record.get("accumulated_feedback"), str)
        assert isinstance(record.get("frozen_parts"), list)
        hashes.append(digest)

    assert len(set(hashes)) == len(hashes), (
        f"rounds did not produce distinct sketches: {hashes}"
    )
    assert hashes[-1] in result.stdout, (
        "the scripted driver did not print the final round md5\n"
        f"stdout:\n{result.stdout}"
    )


def test_revise_preserves_frozen_bass(tmp_path: Path) -> None:
    _, data_dir = run_session(tmp_path, [CREATE_PROMPT, PRESERVE_BASS])
    rounds = read_ledger(data_dir)
    assert len(rounds) == 2
    assert "bass" in rounds[1]["frozen_parts"]

    before = read_round_plan(data_dir, 0)
    after = read_round_plan(data_dir, 1)
    assert notes_for_role(after, "bass") == notes_for_role(before, "bass"), (
        "the bass part changed even though the revise text said 'keep the bass'"
    )
    assert notes_for_role(after, "drums") != notes_for_role(before, "drums"), (
        "the drum part did not change even though the revise text said 'thinner drums'"
    )


def test_feedback_accumulates_across_revise_rounds(tmp_path: Path) -> None:
    _, data_dir = run_session(
        tmp_path,
        [CREATE_PROMPT, REVISE_DARKER, REVISE_THIN_DRUMS],
    )
    rounds = read_ledger(data_dir)
    assert len(rounds) == 3
    assert REVISE_DARKER in rounds[2]["accumulated_feedback"], (
        "round 2 dropped round 1's feedback; accumulated feedback was "
        f"{rounds[2]['accumulated_feedback']!r}"
    )
    assert rounds[2]["md5"] != rounds[0]["md5"]
    assert rounds[2]["md5"] != rounds[1]["md5"]


@pytest.mark.skipif(
    os.environ.get("NOCTURNE_LIVE_EVAL") != "1",
    reason="set NOCTURNE_LIVE_EVAL=1 to run the live provider smoke check",
)
def test_live_provider_smoke() -> None:
    from nocturne.llm import OpenCodeProvider

    result = OpenCodeProvider().interpret(CREATE_PROMPT)
    assert result.brief.intent
    print(f"provider={result.provider} model={result.model} error={result.error}")
