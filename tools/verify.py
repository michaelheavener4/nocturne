#!/usr/bin/env python3
"""NOCTURNE merge gate: pytest plus explicit MIDI truth probes.

Usage:
    python tools/verify.py

Exits 0 only when the whole suite passes, feedback changes the output, the
prompt composes a distinct and key-correct sketch, repeated prompts are
deterministic, scripted sessions persist an honest rounds ledger, and full
songs have real form, key-true harmony, a developing melody, and transitions.
Prints every probe hash.
"""
from __future__ import annotations

import hashlib
import json
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
from song_assertions import (  # noqa: E402
    EDM_PROMPT,
    TEMPLATES,
    chord_tone_audit,
    determinism_audit,
    form_audit,
    key_audit,
    melody_audit,
    run_song,
    transition_audit,
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
SESSION_CREATE_PROMPT = "Make a dark and tense groove at 92 bpm."
SESSION_REVISE_DARKER = "take it darker and move the harmony into a lower register"
SESSION_REVISE_THIN_DRUMS = "thin out the drums, add space, and write a new final-bar motif"
SESSION_PRESERVE_BASS = "keep the bass, thinner drums"


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
        "nocturne",
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


def _run_session(
    workdir: Path,
    says: list[str],
) -> tuple[subprocess.CompletedProcess[str], Path]:
    data_dir = workdir / "session"
    data_dir.mkdir(parents=True, exist_ok=True)
    command = [
        sys.executable,
        "-m",
        "nocturne",
        "session",
        "--data",
        str(data_dir),
        "--offline",
    ]
    for text in says:
        command += ["--say", text]
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
            f"session failed (exit {result.returncode})\n"
            f"command: {' '.join(command)}\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    return result, data_dir


def _session_ledger(data_dir: Path) -> list[dict]:
    path = data_dir / "rounds.jsonl"
    if not path.is_file():
        raise RuntimeError(f"session did not write the rounds ledger at {path}")
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _session_round_path(data_dir: Path, n: int, suffix: str) -> Path:
    return data_dir / "rounds" / f"round-{n:03d}{suffix}"


def _session_round_plan(data_dir: Path, n: int) -> dict:
    path = _session_round_path(data_dir, n, ".json")
    if not path.is_file():
        raise RuntimeError(f"session did not write the round plan at {path}")
    return json.loads(path.read_text())


def _session_notes(plan: dict, role: str) -> list[dict]:
    tracks = plan.get("tracks")
    if tracks is None and isinstance(plan.get("plan"), dict):
        tracks = plan["plan"].get("tracks")
    if not isinstance(tracks, list):
        raise RuntimeError(f"round plan has no tracks list: {sorted(plan)}")
    matches = [track for track in tracks if track.get("role") == role]
    if len(matches) != 1:
        raise RuntimeError(f"expected one {role!r} track, found {len(matches)}")
    notes = matches[0].get("notes")
    if not isinstance(notes, list):
        raise RuntimeError(f"{role!r} track has no notes list")
    return notes


def run_session_ledger_probe() -> bool:
    print("== session ledger probe ==")
    says = [SESSION_CREATE_PROMPT, SESSION_REVISE_DARKER, SESSION_REVISE_THIN_DRUMS]
    try:
        with tempfile.TemporaryDirectory(prefix="nocturne-session-ledger-") as tmp:
            result, data_dir = _run_session(Path(tmp), says)
            rounds = _session_ledger(data_dir)
            if [record["n"] for record in rounds] != [0, 1, 2]:
                raise AssertionError(f"expected rounds 0,1,2, got {rounds}")
            if [record["kind"] for record in rounds] != ["create", "revise", "revise"]:
                raise AssertionError(
                    f"unexpected round kinds: {[record['kind'] for record in rounds]}"
                )
            if [record["text"] for record in rounds] != says:
                raise AssertionError("ledger text does not preserve the scripted turns")
            hashes = []
            for record in rounds:
                midi_path = _session_round_path(data_dir, record["n"], ".mid")
                if not midi_path.is_file():
                    raise AssertionError(f"missing round MIDI {midi_path}")
                midi_bytes = midi_path.read_bytes()
                assert_valid_midi(midi_bytes)
                digest = hashlib.md5(midi_bytes).hexdigest()
                if record["md5"] != digest:
                    raise AssertionError(
                        f"round {record['n']} ledger md5 {record['md5']} does not "
                        f"match {midi_path} ({digest})"
                    )
                if not isinstance(record.get("accumulated_feedback"), str):
                    raise AssertionError("accumulated_feedback is not a string")
                if not isinstance(record.get("frozen_parts"), list):
                    raise AssertionError("frozen_parts is not a list")
                print(
                    f"  round {record['n']}: {digest}  {record['kind']:<6}  "
                    f"{record['text']}"
                )
                hashes.append(digest)
            if len(set(hashes)) != len(hashes):
                raise AssertionError(f"rounds did not produce distinct sketches: {hashes}")
            if hashes[-1] not in result.stdout:
                raise AssertionError("the scripted driver did not print the final round md5")
    except Exception as exc:  # noqa: BLE001 - report, then fail the gate
        print(f"PROBE ERROR: {exc}")
        return False
    print("probe: PASS (three honest rounds, distinct hashes)")
    return True


def run_session_preservation_probe() -> bool:
    print("== session preservation probe ==")
    try:
        with tempfile.TemporaryDirectory(prefix="nocturne-session-preserve-") as tmp:
            _, data_dir = _run_session(
                Path(tmp), [SESSION_CREATE_PROMPT, SESSION_PRESERVE_BASS]
            )
            rounds = _session_ledger(data_dir)
            if len(rounds) != 2:
                raise AssertionError(f"expected 2 rounds, got {len(rounds)}")
            if "bass" not in rounds[1].get("frozen_parts", []):
                raise AssertionError(
                    f"round 1 did not record bass as frozen: "
                    f"{rounds[1].get('frozen_parts')}"
                )
            before = _session_round_plan(data_dir, 0)
            after = _session_round_plan(data_dir, 1)
            before_bass = _session_notes(before, "bass")
            after_bass = _session_notes(after, "bass")
            before_drums = _session_notes(before, "drums")
            after_drums = _session_notes(after, "drums")
            print(f"  bass notes:  {len(before_bass)} -> {len(after_bass)} (frozen)")
            print(f"  drum notes:  {len(before_drums)} -> {len(after_drums)} (revised)")
            if after_bass != before_bass:
                raise AssertionError(
                    "the bass part changed even though the revise text said 'keep the bass'"
                )
            if after_drums == before_drums:
                raise AssertionError(
                    "the drum part did not change even though the revise text said "
                    "'thinner drums'"
                )
    except Exception as exc:  # noqa: BLE001 - report, then fail the gate
        print(f"PROBE ERROR: {exc}")
        return False
    print("probe: PASS (bass preserved exactly, drums revised)")
    return True


def run_session_accumulation_probe() -> bool:
    print("== session accumulation probe ==")
    try:
        with tempfile.TemporaryDirectory(prefix="nocturne-session-accumulate-") as tmp:
            _, data_dir = _run_session(
                Path(tmp),
                [SESSION_CREATE_PROMPT, SESSION_REVISE_DARKER, SESSION_REVISE_THIN_DRUMS],
            )
            rounds = _session_ledger(data_dir)
            if len(rounds) != 3:
                raise AssertionError(f"expected 3 rounds, got {len(rounds)}")
            accumulated = rounds[2].get("accumulated_feedback", "")
            print(f"  round 2 accumulated_feedback: {accumulated!r}")
            if SESSION_REVISE_DARKER not in accumulated:
                raise AssertionError("round 2 dropped round 1's feedback")
            hashes = [record["md5"] for record in rounds]
            if hashes[2] == hashes[0] or hashes[2] == hashes[1]:
                raise AssertionError(
                    f"round 2 hash {hashes[2]} repeats an earlier round: {hashes}"
                )
    except Exception as exc:  # noqa: BLE001 - report, then fail the gate
        print(f"PROBE ERROR: {exc}")
        return False
    print("probe: PASS (round 2 carries round 1's instruction and a new hash)")
    return True


def run_hash_probe() -> bool:
    print("== multi-feedback hash probe ==")
    print(f"prompt: {PROMPT}")
    try:
        with tempfile.TemporaryDirectory(prefix="nocturne-verify-") as tmp:
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
        with tempfile.TemporaryDirectory(prefix="nocturne-prompt-") as tmp:
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
        with tempfile.TemporaryDirectory(prefix="nocturne-key-") as tmp:
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
        with tempfile.TemporaryDirectory(prefix="nocturne-determinism-") as tmp:
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


def run_song_form_probe() -> bool:
    print("== song form probe ==")
    try:
        with tempfile.TemporaryDirectory(prefix="nocturne-song-form-") as tmp:
            for label, template in TEMPLATES.items():
                render = run_song(Path(tmp), template["prompt"], label=label)
                report = form_audit(
                    render,
                    expected_bars=template["bars"],
                    expected_roles=template["roles"],
                )
                print(
                    f"  {render.md5}  {report['bars']} bars  {template['prompt']}"
                )
                for section in report["sections"]:
                    print(
                        f"    bar {section['start_bar']:>2} +{section['bars']:<2}  "
                        f"{section['name']} ({section['role']}) "
                        f"energy={section['energy']}"
                    )
    except Exception as exc:  # noqa: BLE001 - report, then fail the gate
        print(f"PROBE ERROR: {exc}")
        return False
    print("probe: PASS (contiguous form, bar totals, valid MIDI)")
    return True


def run_song_key_probe() -> bool:
    print("== song key truth probe ==")
    try:
        with tempfile.TemporaryDirectory(prefix="nocturne-song-key-") as tmp:
            for label, template in TEMPLATES.items():
                render = run_song(Path(tmp), template["prompt"], label=label)
                report = key_audit(render)
                print(
                    f"  {render.md5}  key={report['key']}  "
                    f"scale={report['scale']}  pitched_notes={report['total']}  "
                    f"outside={report['outside']}"
                )
                for section in chord_tone_audit(render):
                    share = (
                        "n/a"
                        if section["share"] is None
                        else f"{section['share']:.1%}"
                    )
                    print(
                        f"    {section['role']:<11} {section['name']:<18} "
                        f"chord tones {section['chord_tones']:>3}/"
                        f"{section['notes']:<3} = {share}"
                    )
    except Exception as exc:  # noqa: BLE001 - report, then fail the gate
        print(f"PROBE ERROR: {exc}")
        return False
    print("probe: PASS (100% scale tones, every section >= 50% chord tones)")
    return True


def run_song_melody_probe() -> bool:
    print("== song melody variation probe ==")
    try:
        with tempfile.TemporaryDirectory(prefix="nocturne-song-melody-") as tmp:
            for label, template in TEMPLATES.items():
                render = run_song(Path(tmp), template["prompt"], label=label)
                report = melody_audit(render)
                print(
                    f"  {render.md5}  verse_notes={report['verse_notes']}  "
                    f"hook_notes={report['hook_notes']}  "
                    f"verse_differs={report['verse_differs_from_hook']}"
                )
                for run in report["runs"]:
                    print(
                        f"    repeated run: {run['section']} bar {run['bar']} "
                        f"length {run['run']} allowed={run['allowed']}"
                    )
    except Exception as exc:  # noqa: BLE001 - report, then fail the gate
        print(f"PROBE ERROR: {exc}")
        return False
    print("probe: PASS (drops/choruses develop; verse differs from the hook)")
    return True


def run_song_transition_probe() -> bool:
    print("== song transition probe ==")
    try:
        with tempfile.TemporaryDirectory(prefix="nocturne-song-transition-") as tmp:
            for label, template in TEMPLATES.items():
                render = run_song(Path(tmp), template["prompt"], label=label)
                print(f"  {render.md5}  {template['prompt']}")
                for report in transition_audit(render):
                    if report["role"] == "breakdown":
                        print(
                            f"    breakdown {report['name']}: "
                            f"{report['drum_notes']} drum notes"
                        )
                        continue
                    print(
                        f"    before {report['role']} {report['name']} at bar "
                        f"{report['start_bar']}: pre bar {report['pre_bar']} "
                        f"drums={report['pre_drums']} vs median "
                        f"{report['median_drums']}; mean pitch="
                        f"{report['pre_mean_pitch']} vs "
                        f"{report['median_mean_pitch']}"
                    )
    except Exception as exc:  # noqa: BLE001 - report, then fail the gate
        print(f"PROBE ERROR: {exc}")
        return False
    print("probe: PASS (pre-drop bars differ; breakdowns have no drums)")
    return True


def run_song_determinism_probe() -> bool:
    print("== song determinism probe ==")
    try:
        with tempfile.TemporaryDirectory(prefix="nocturne-song-determinism-") as tmp:
            first = run_song(Path(tmp), EDM_PROMPT, label="first")
            repeat = run_song(Path(tmp), EDM_PROMPT, label="repeat")
            report = determinism_audit(first, repeat)
            print(f"  {report['md5']}  {report['prompt']}")
            print(f"  {report['repeat_md5']}  {report['prompt']} (repeat)")
            print(f"  eight-bar demo baseline: {report['demo_baseline']}")
    except Exception as exc:  # noqa: BLE001 - report, then fail the gate
        print(f"PROBE ERROR: {exc}")
        return False
    print("probe: PASS (same prompt, same song bytes; not the eight-bar demo)")
    return True


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
        "session ledger": run_session_ledger_probe(),
        "session preservation": run_session_preservation_probe(),
        "session accumulation": run_session_accumulation_probe(),
        "song form": run_song_form_probe(),
        "song key truth": run_song_key_probe(),
        "song melody variation": run_song_melody_probe(),
        "song transitions": run_song_transition_probe(),
        "song determinism": run_song_determinism_probe(),
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
