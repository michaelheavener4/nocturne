# NOCTURNE: a local-first agentic music studio

> Renamed from MUSE on 2026-10-26: the old name collided with Meta's Muse. The findings keep the old name in their period text; history is not rewritten.


NOCTURNE turns a plain-language creative brief ("dark, tense, 92 bpm, leave room to revise") into editable MIDI: a small, transparent Python agent that interprets intent, plans an 8-bar arrangement, renders it to MIDI, and can hand it to Ableton Live through a bridge adapter. Everything runs locally. There is no cloud account, no telemetry phone-home, and no copyrighted audio involved: the output is original notes.

It is a working prototype, built in the open as a learning project. This README describes what the code actually does today: including, in [FINDINGS.md](FINDINGS.md), the first hard lesson it taught: **the feedback loop in v1 is cosmetic**, proven with content hashes, and the planner upgrade that fixes it is the project's current build.

## How it works

```
prompt ──► IntentInterpreter ──► CreativeBrief ──► ArrangementPlanner ──► ArrangementPlan
                                                              │                    │
                                              (optional LLM route via OpenCode)    ├─► write_midi ──► .mid file
                                                                                   └─► DAWAdapter ──► MockDAW (offline)
                                                                                                  └─► AbletonBridgeAdapter (Live)
```

- **Intent** (`intent.py`): a small, transparent keyword parser (an LLM can replace it without changing the schema) that produces a `CreativeBrief`: emotional dimensions, tempo, key, goals, and explicit uncertainty.
- **Planning** (`arrangement.py`): `ArrangementPlanner` converts the brief into an `ArrangementPlan`: drum, bass, harmony, and melody tracks as note data.
- **Rendering** (`midi.py`, `daw.py`): a hand-rolled MIDI writer (no external MIDI library) plus DAW adapters: a mock DAW for offline runs and an Ableton Live bridge.
- **Session** (`session.py`): `CreativeSession` orchestrates the loop, with sqlite-backed sound memory (`memory.py`), a taste store (`taste.py`, `preferences.py`), arrangement analysis (`analysis.py`), and local-only telemetry (`telemetry.py`).
- **Extras**: hum-to-notes transcription (`humming.py`); all shared types are pydantic dataclasses in `models.py`.

15 modules, 1,173 lines of Python. The whole pipeline is inspectable: that is the point of the project.

## Feedback

Revision language changes the music, measurably. `nocturne demo --feedback "..."` parses recognized phrases (darker, thinner, busier, more space, lower register, and friends) into signed dimensions in `intent.py`, and the planner in `arrangement.py` maps those dimensions onto register, density, velocity, and structure. The mapping is an explicit table you can read, output is deterministic, and the claim is testable in one command:

```bash
python tools/verify.py   # pytest suite + multi-feedback hash probe
```

Before the fix, every feedback string produced the same MD5. See `FINDINGS.md`, Finding 001, for the autopsy and the resolution hashes.

## Sessions

One prompt is a sketch; a session is the conversation. `nocturne session` keeps every round on disk so a revision can be audited, not just believed:

```bash
nocturne session --data ~/my-session --offline \
  --say "Make a dark and tense electronic groove at 92 bpm" \
  --say "keep the bass, thinner drums" \
  --say "take it darker"
nocturne render ~/my-session/rounds/round-002.mid   # hear any round
```

Each round writes `rounds/round-NNN.mid` and its plan JSON, plus a line in `rounds.jsonl`: the text, the accumulated feedback, the frozen parts, and the MD5. Feedback accumulates across rounds, and "keep the bass" (or drums, melody, harmony) freezes that part note for note while the rest is replanned. With a live provider configured the interpreter is an LLM; any provider failure falls back to the deterministic interpreter and records why, so a session never dies because a model did. See Finding 003.

## Songs

```bash
nocturne song --prompt "Make a dark and tense edm track at 92 bpm" --out DIR [--render]
```

A full song, not a loop: form (edm 44 bars, pop 56), a progression the harmony and bass actually follow, a motif that returns varied instead of repeated, transitions and risers between sections, and a breakdown that drops the drums. `--render` writes song.wav at the song's tempo. Sessions plan songs too when the request asks for one; groove requests keep the 8-bar sketch. See Finding 004.

## Run it

Requires Python 3.12 and pydantic.

```bash
git clone https://github.com/michaelheavener4/nocturne.git
cd nocturne
python -m venv .venv && source .venv/bin/activate
pip install -e .
nocturne demo --prompt "dark and tense, 92 bpm"
```

The demo runs the full pipeline against the mock DAW and writes a MIDI sketch plus its analysis. The Ableton bridge path is macOS + Ableton Live 12 and is exercised separately (`live-demo`).

## Status and roadmap

- ✅ End-to-end pipeline: brief → plan → MIDI → analysis, with session memory and taste capture.
- ✅ Track 001 produced three real, human-directed revisions (see FINDINGS for why "human-directed" is the operative phrase).
- ✅ Planner upgrade (Builds 1–3): feedback, the prompt, and the key verifiably drive the notes; sessions keep state and freeze parts on request.
- ✅ Songs (Build 4): full form, progression harmony, a developing melody, transitions. Finding 004.
- ✅ Renamed to NOCTURNE (2026-10-26): repo, package, and CLI. SoundFont lookup still honors pre-rename install directories.
- 🔨 Next: a refinement round fed by the research loop (arrangement anatomy, hook variation rates).

## Findings

Engineering notes live in [FINDINGS.md](FINDINGS.md). Finding 001 (feedback is cosmetic at note level) includes the full method and hash table: steal the method, it's a good one: *if a system claims to respond to feedback, hash the output and vary the feedback.*

## License

MIT. See [LICENSE](LICENSE).
