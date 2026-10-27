"""Truth probes for full-song output (Gate v4).

The helpers here read the ``nocturne song`` artifact pair directly: ``song.json``
is the ArrangementPlan dump and ``song.mid`` is the rendered file. Nothing in
this module calls a model or an external MIDI library, so the same probes run
offline and deterministically.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import statistics
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from midi_assertions import (
    NOTE_PITCH_CLASS,
    SCALE_INTERVALS,
    assert_valid_midi,
    parse_prompt_key,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
BEATS_PER_BAR = 4

EDM_PROMPT = "dark and tense EDM track, D minor, 128 bpm"
POP_PROMPT = "bright and playful pop song, C major, 120 bpm"

# The published eight-bar demo baseline from FINDINGS.md. A full song must not
# collapse back onto this sketch.
DEMO_BASELINE_MD5 = "91c023a806e8b839ae686232e1709ff1"  # was aaf9da4b under the MUSE name; track names are in the MIDI, so the 2026-10-26 NOCTURNE rename moved it

EDM_ROLES = (
    "intro",
    "verse",
    "build",
    "drop",
    "breakdown",
    "drop",
    "outro",
)
POP_ROLES = (
    "intro",
    "verse",
    "pre-chorus",
    "chorus",
    "verse",
    "chorus",
    "bridge",
    "chorus",
    "outro",
)
TEMPLATES = {
    "edm": {"prompt": EDM_PROMPT, "bars": 44, "roles": EDM_ROLES},
    "pop": {"prompt": POP_PROMPT, "bars": 56, "roles": POP_ROLES},
}
HIGH_ENERGY_ROLES = frozenset({"drop", "chorus"})
PITCHED_ROLES = ("bass", "harmony", "melody")
ALL_ROLES = ("drums", "bass", "harmony", "melody")

_KEY_NAME_RE = re.compile(
    r"^\s*([A-Ga-g])([#♯b♭]?)\s*(major|minor|maj|min|m)?\s*$", re.IGNORECASE
)


@dataclass
class SongRender:
    prompt: str
    md5: str
    midi_bytes: bytes
    plan: dict
    stdout: str


def run_song(workdir: Path, prompt: str, *, label: str = "song") -> SongRender:
    """Run ``nocturne song`` offline and return the artifact pair plus stdout."""
    out_dir = workdir / label
    out_dir.mkdir(parents=True, exist_ok=True)
    command = [
        sys.executable,
        "-m",
        "nocturne",
        "song",
        "--prompt",
        prompt,
        "--out",
        str(out_dir),
    ]
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
        timeout=180,
    )
    if result.returncode != 0:
        raise AssertionError(
            f"nocturne song failed for prompt={prompt!r} (exit {result.returncode})\n"
            f"command: {' '.join(command)}\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )

    midi_path = out_dir / "song.mid"
    plan_path = out_dir / "song.json"
    if not midi_path.is_file():
        raise AssertionError(
            f"nocturne song did not write {midi_path}\nstdout:\n{result.stdout}"
        )
    if not plan_path.is_file():
        raise AssertionError(
            f"nocturne song did not write {plan_path}\nstdout:\n{result.stdout}"
        )

    midi_bytes = midi_path.read_bytes()
    assert_valid_midi(midi_bytes)
    payload = json.loads(plan_path.read_text())
    return SongRender(
        prompt=prompt,
        md5=hashlib.md5(midi_bytes).hexdigest(),
        midi_bytes=midi_bytes,
        plan=plan_of(payload),
        stdout=result.stdout,
    )


def plan_of(payload: dict) -> dict:
    """Accept either a bare plan dump or a wrapper with a ``plan`` member."""
    if isinstance(payload.get("form"), list) and isinstance(payload.get("tracks"), list):
        return payload
    if isinstance(payload.get("plan"), dict):
        return payload["plan"]
    return payload


def normalize_role(role: object) -> str:
    value = str(role).strip().lower().replace("_", "-").replace(" ", "-")
    while "--" in value:
        value = value.replace("--", "-")
    if value == "prechorus":
        value = "pre-chorus"
    return value


def form_of(plan: dict) -> list[dict]:
    form = plan.get("form")
    if not isinstance(form, list) or not form:
        raise AssertionError(
            f"song plan has no form list (keys: {sorted(plan)}); "
            "the song contract requires sections"
        )
    return form


def tracks_by_role(plan: dict, required: tuple[str, ...] = ALL_ROLES) -> dict[str, dict]:
    tracks = plan.get("tracks")
    if not isinstance(tracks, list):
        raise AssertionError(f"song plan has no tracks list (keys: {sorted(plan)})")
    grouped: dict[str, list[dict]] = {}
    for track in tracks:
        if not isinstance(track, dict):
            raise AssertionError(f"track entry is not an object: {track!r}")
        grouped.setdefault(normalize_role(track.get("role", "")), []).append(track)
    result: dict[str, dict] = {}
    for role in required:
        matches = grouped.get(role, [])
        if len(matches) != 1:
            raise AssertionError(
                f"expected one {role!r} track, found {len(matches)}; "
                f"roles present: {sorted(grouped)}"
            )
        result[role] = matches[0]
    return result


def notes_for_role(plan: dict, role: str) -> list[dict]:
    track = tracks_by_role(plan, required=(role,))[role]
    notes = track.get("notes")
    if not isinstance(notes, list):
        raise AssertionError(f"{role!r} track has no notes list")
    for note in notes:
        if not isinstance(note, dict):
            raise AssertionError(f"{role!r} note is not an object: {note!r}")
        for field in ("pitch", "start", "duration"):
            if field not in note:
                raise AssertionError(f"{role!r} note is missing {field!r}: {note!r}")
    return notes


def note_bar(note: dict) -> int:
    """Absolute bar index for a note.

    ArrangementPlan notes keep the project's existing ``start`` field in
    beats. A note that starts on the bar line belongs to that bar.
    """
    if "start_bar" in note:
        return int(note["start_bar"])
    return int(float(note["start"]) // BEATS_PER_BAR)


def parse_key_name(name: str) -> tuple[int, str] | None:
    parsed = parse_prompt_key(name)
    if parsed is not None:
        return parsed
    match = _KEY_NAME_RE.fullmatch(str(name))
    if not match:
        return None
    letter, accidental, mode = match.groups()
    tonic = NOTE_PITCH_CLASS[letter.upper()]
    if accidental in ("#", "♯"):
        tonic += 1
    elif accidental in ("b", "♭"):
        tonic -= 1
    major = bool(mode) and mode.lower().startswith("maj")
    return tonic % 12, "major" if major else "minor"


def key_scale(name: str) -> tuple[int, str, frozenset[int]]:
    parsed = parse_key_name(name)
    if parsed is None:
        raise AssertionError(f"song plan key is not readable: {name!r}")
    tonic, mode = parsed
    scale = frozenset((tonic + interval) % 12 for interval in SCALE_INTERVALS[mode])
    return tonic, mode, scale


def form_audit(
    render: SongRender,
    *,
    expected_bars: int | None = None,
    expected_roles: tuple[str, ...] | None = None,
) -> dict:
    """Sections must tile the timeline from bar 0 and the MIDI must be real."""
    plan = render.plan
    form = form_of(plan)
    plan_bars = plan.get("bars")
    if not isinstance(plan_bars, int) or plan_bars < 1:
        raise AssertionError(f"song plan has no positive bars field: {plan_bars!r}")
    if expected_bars is not None and plan_bars != expected_bars:
        raise AssertionError(
            f"expected a {expected_bars}-bar song template, plan says {plan_bars} bars"
        )

    sections: list[dict] = []
    cursor = 0
    for index, section in enumerate(form):
        if not isinstance(section, dict):
            raise AssertionError(f"section {index} is not an object: {section!r}")
        missing = [field for field in ("name", "role", "start_bar", "bars", "energy") if field not in section]
        if missing:
            raise AssertionError(f"section {index} is missing fields {missing}: {section!r}")
        start = int(section["start_bar"])
        bars = int(section["bars"])
        energy = float(section["energy"])
        if bars < 1:
            raise AssertionError(f"section {index} has non-positive bars: {bars}")
        if not 0.0 <= energy <= 1.0:
            raise AssertionError(f"section {index} energy is outside 0..1: {energy}")
        if start != cursor:
            raise AssertionError(
                f"section {index} ({section['name']!r}) starts at bar {start}, "
                f"expected contiguous bar {cursor}"
            )
        cursor += bars
        sections.append(
            {
                "name": str(section["name"]),
                "role": normalize_role(section["role"]),
                "start_bar": start,
                "bars": bars,
                "energy": energy,
            }
        )

    if cursor != plan_bars:
        raise AssertionError(
            f"section bars sum to {cursor}, but plan.bars is {plan_bars}"
        )
    if expected_roles is not None:
        actual = [section["role"] for section in sections]
        expected = [normalize_role(role) for role in expected_roles]
        if actual != expected:
            raise AssertionError(
                f"unexpected section roles: {actual}; expected {expected}"
            )

    assert_valid_midi(render.midi_bytes)
    return {"bars": plan_bars, "sections": sections}


def key_audit(render: SongRender) -> dict:
    """Every pitched note must be a scale tone, song-wide."""
    plan = render.plan
    key = plan.get("key")
    if not isinstance(key, str) or not key:
        raise AssertionError(f"song plan has no key: {key!r}")
    tonic, mode, scale = key_scale(key)
    prompt_key = parse_prompt_key(render.prompt)
    if prompt_key is not None and prompt_key != (tonic, mode):
        raise AssertionError(
            f"plan key {key!r} does not match the prompt key {prompt_key}"
        )

    total = 0
    outside: dict[str, list[dict]] = {}
    per_role: dict[str, dict] = {}
    for role in PITCHED_ROLES:
        notes = notes_for_role(plan, role)
        role_outside = []
        for note in notes:
            pitch = int(note["pitch"])
            if pitch % 12 not in scale:
                role_outside.append(
                    {"pitch": pitch, "start": float(note["start"]), "bar": note_bar(note)}
                )
        per_role[role] = {"notes": len(notes), "outside": role_outside}
        total += len(notes)
        if role_outside:
            outside[role] = role_outside

    if total == 0:
        raise AssertionError("song has no pitched notes to audit")
    if outside:
        sample = {role: items[:5] for role, items in outside.items()}
        raise AssertionError(
            f"pitched notes leave the plan key {key!r} (scale {sorted(scale)}): {sample}"
        )
    return {
        "key": key,
        "tonic": tonic,
        "mode": mode,
        "scale": sorted(scale),
        "total": total,
        "outside": {},
        "per_role": per_role,
        "share": 1.0,
    }


def _chord_roots_by_bar(plan: dict, total_bars: int, tonic: int) -> dict[int, int]:
    """Infer one chord root per bar from the bass track's first note."""
    bass = notes_for_role(plan, "bass")
    roots: dict[int, int] = {}
    for bar in range(total_bars):
        in_bar = [note for note in bass if note_bar(note) == bar]
        if not in_bar:
            continue
        first = min(in_bar, key=lambda note: (float(note["start"]), int(note["pitch"])))
        roots[bar] = int(first["pitch"]) % 12
    previous = tonic
    for bar in range(total_bars):
        if bar in roots:
            previous = roots[bar]
        else:
            roots[bar] = previous
    return roots


def _chord_tones(root: int, scale: frozenset[int]) -> frozenset[int]:
    ordered = sorted(scale)
    if root in ordered:
        index = ordered.index(root)
        return frozenset(
            {root, ordered[(index + 2) % 7], ordered[(index + 4) % 7]}
        )
    return frozenset({root, (root + 4) % 12, (root + 7) % 12})


def chord_tone_audit(render: SongRender) -> list[dict]:
    """Report the chord-tone share of melody + harmony notes per section.

    The contract does not require a chord chart in the plan dump, so roots are
    inferred from the bass, which the contract says follows chord roots. Each
    bar's chord is the diatonic triad on that root inside the song key.
    """
    plan = render.plan
    tonic, _, scale = key_scale(plan["key"])
    total_bars = int(plan["bars"])
    roots = _chord_roots_by_bar(plan, total_bars, tonic)
    notes = notes_for_role(plan, "melody") + notes_for_role(plan, "harmony")

    reports: list[dict] = []
    for section in form_of(plan):
        start = int(section["start_bar"])
        bars = int(section["bars"])
        section_notes = [
            note for note in notes if start <= note_bar(note) < start + bars
        ]
        hits = 0
        misses: list[dict] = []
        used_roots: set[int] = set()
        for note in section_notes:
            bar = note_bar(note)
            root = roots.get(bar, tonic)
            used_roots.add(root)
            tones = _chord_tones(root, scale)
            pitch = int(note["pitch"])
            if pitch % 12 in tones:
                hits += 1
            else:
                misses.append(
                    {
                        "bar": bar,
                        "pitch": pitch,
                        "root": root,
                        "tones": sorted(tones),
                    }
                )
        share = hits / len(section_notes) if section_notes else None
        if share is not None and share < 0.5:
            raise AssertionError(
                f"section {section['name']!r} ({normalize_role(section['role'])}) "
                f"has chord-tone share {share:.1%}, below 50% "
                f"({hits}/{len(section_notes)}); misses: {misses[:6]}"
            )
        reports.append(
            {
                "name": str(section["name"]),
                "role": normalize_role(section["role"]),
                "start_bar": start,
                "bars": bars,
                "notes": len(section_notes),
                "chord_tones": hits,
                "share": share,
                "roots": sorted(used_roots),
                "misses": misses,
            }
        )
    if not any(report["notes"] for report in reports):
        raise AssertionError("no melody or harmony notes found in any song section")
    return reports


def _bar_signature(notes: list[dict], bar: int) -> tuple | None:
    in_bar = [note for note in notes if note_bar(note) == bar]
    if not in_bar:
        return None
    return tuple(
        sorted(
            (
                int(note["pitch"]),
                round(float(note["start"]) - bar * BEATS_PER_BAR, 3),
                round(float(note["duration"]), 3),
            )
            for note in in_bar
        )
    )


def _section_note_tuples(notes: list[dict], section: dict) -> tuple:
    start = int(section["start_bar"])
    end = start + int(section["bars"])
    return tuple(
        sorted(
            (
                int(note["pitch"]),
                round(float(note["start"]) - note_bar(note) * BEATS_PER_BAR, 3),
                round(float(note["duration"]), 3),
            )
            for note in notes
            if start <= note_bar(note) < end
        )
    )


def _hook_return_flagged(plan: dict, section: dict) -> bool:
    for source in (section, plan):
        for key, value in source.items():
            if "hook" in str(key).lower() and bool(value):
                return True
            if "hook" in str(value).lower():
                return True
    if "hook" in str(section.get("name", "")).lower():
        return True
    rationale = plan.get("rationale", [])
    if isinstance(rationale, list):
        text = " ".join(str(item) for item in rationale)
    else:
        text = str(rationale)
    return bool(re.search(r"hook[\s_-]*return", text, re.IGNORECASE))


def melody_audit(render: SongRender) -> dict:
    """Drops/choruses must develop; verses must not be the drop melody."""
    plan = render.plan
    melody = notes_for_role(plan, "melody")
    sections = form_of(plan)
    high_sections = [
        section
        for section in sections
        if normalize_role(section["role"]) in HIGH_ENERGY_ROLES
    ]
    if not high_sections:
        raise AssertionError("song has no drop or chorus section to audit")
    final_high = high_sections[-1]

    runs: list[dict] = []
    violations: list[dict] = []
    for section in high_sections:
        start = int(section["start_bar"])
        bars = int(section["bars"])
        current_signature = None
        run_length = 0
        for bar in range(start, start + bars):
            signature = _bar_signature(melody, bar)
            if signature is None:
                current_signature = None
                run_length = 0
                continue
            if signature == current_signature:
                run_length += 1
            else:
                current_signature = signature
                run_length = 1
            if run_length > 2:
                flagged = section is final_high and _hook_return_flagged(plan, section)
                runs.append(
                    {
                        "section": str(section["name"]),
                        "role": normalize_role(section["role"]),
                        "bar": bar,
                        "run": run_length,
                        "allowed": flagged,
                    }
                )
                if not flagged:
                    violations.append(runs[-1])
    if violations:
        raise AssertionError(
            "a drop/chorus repeats an identical melody bar more than twice "
            f"without a flagged final hook return: {violations}"
        )

    verse_sections = [
        section
        for section in sections
        if normalize_role(section["role"]) == "verse"
    ]
    if not verse_sections:
        raise AssertionError("song has no verse section to compare with the drop")
    verse_notes = tuple(
        note
        for section in verse_sections
        for note in _section_note_tuples(melody, section)
    )
    hook_notes = tuple(
        note
        for section in high_sections
        for note in _section_note_tuples(melody, section)
    )
    if not verse_notes:
        raise AssertionError("verse sections contain no melody notes")
    if not hook_notes:
        raise AssertionError("drop/chorus sections contain no melody notes")
    if verse_notes == hook_notes:
        raise AssertionError(
            "verse melody notes are identical to the drop/chorus melody notes; "
            "the verse is not a sparse variant"
        )

    return {
        "runs": runs,
        "violations": violations,
        "verse_notes": len(verse_notes),
        "hook_notes": len(hook_notes),
        "verse_differs_from_hook": verse_notes != hook_notes,
    }


def _bar_drum_stats(drums: list[dict], bar: int) -> tuple[int, float | None]:
    in_bar = [note for note in drums if note_bar(note) == bar]
    if not in_bar:
        return 0, None
    return len(in_bar), statistics.fmean(int(note["pitch"]) for note in in_bar)


def transition_audit(render: SongRender) -> list[dict]:
    """Pre-drop bars must differ from the section; breakdowns must be drumless."""
    plan = render.plan
    drums = notes_for_role(plan, "drums")
    sections = form_of(plan)
    reports: list[dict] = []

    for section in sections:
        role = normalize_role(section["role"])
        if role not in HIGH_ENERGY_ROLES:
            continue
        start = int(section["start_bar"])
        bars = int(section["bars"])
        pre_bar = start - 1
        if pre_bar < 0:
            raise AssertionError(
                f"section {section['name']!r} starts at bar 0, so it has no "
                "preceding transition bar"
            )
        pre_count, pre_mean = _bar_drum_stats(drums, pre_bar)
        section_counts = [
            _bar_drum_stats(drums, bar)[0] for bar in range(start, start + bars)
        ]
        section_means = [
            mean
            for mean in (_bar_drum_stats(drums, bar)[1] for bar in range(start, start + bars))
            if mean is not None
        ]
        median_count = statistics.median(section_counts)
        median_mean = statistics.median(section_means) if section_means else None
        count_diff = abs(pre_count - median_count)
        register_diff = (
            abs(pre_mean - median_mean)
            if pre_mean is not None and median_mean is not None
            else 0.0
        )
        differs = count_diff >= 1 or register_diff >= 1.0
        report = {
            "name": str(section["name"]),
            "role": role,
            "start_bar": start,
            "pre_bar": pre_bar,
            "pre_drums": pre_count,
            "pre_mean_pitch": pre_mean,
            "median_drums": median_count,
            "median_mean_pitch": median_mean,
            "count_diff": count_diff,
            "register_diff": register_diff,
            "differs": differs,
        }
        reports.append(report)
        if not differs:
            raise AssertionError(
                f"the bar before {section['name']!r} (bar {pre_bar}) does not "
                f"differ from the section's median bar: {report}"
            )

    breakdowns = [
        section
        for section in sections
        if normalize_role(section["role"]) == "breakdown"
    ]
    for section in breakdowns:
        start = int(section["start_bar"])
        bars = int(section["bars"])
        count = sum(
            1 for note in drums if start <= note_bar(note) < start + bars
        )
        report = {
            "name": str(section["name"]),
            "role": "breakdown",
            "start_bar": start,
            "bars": bars,
            "drum_notes": count,
        }
        reports.append(report)
        if count != 0:
            raise AssertionError(
                f"breakdown {section['name']!r} contains {count} drum notes; "
                "the contract strips drums from breakdowns"
            )
    return reports


def determinism_audit(first: SongRender, repeat: SongRender) -> dict:
    if first.prompt != repeat.prompt:
        raise AssertionError("determinism audit compares different prompts")
    if first.md5 != repeat.md5:
        raise AssertionError(
            f"the same prompt produced different song bytes: "
            f"{first.md5} != {repeat.md5}"
        )
    if first.md5 == DEMO_BASELINE_MD5:
        raise AssertionError(
            f"song output collapsed onto the eight-bar demo baseline {DEMO_BASELINE_MD5}"
        )
    if first.md5 not in first.stdout:
        raise AssertionError(
            f"nocturne song did not print its md5 {first.md5} in stdout:\n{first.stdout}"
        )
    return {
        "prompt": first.prompt,
        "md5": first.md5,
        "repeat_md5": repeat.md5,
        "demo_baseline": DEMO_BASELINE_MD5,
    }
