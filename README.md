# MUSE: a local-first agentic music studio


MUSE turns a plain-language creative brief ("dark, tense, 92 bpm, leave room to revise") into editable MIDI: a small, transparent Python agent that interprets intent, plans an 8-bar arrangement, renders it to MIDI, and can hand it to Ableton Live through a bridge adapter. Everything runs locally. There is no cloud account, no telemetry phone-home, and no copyrighted audio involved: the output is original notes.

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

Revision language changes the music, measurably. `muse demo --feedback "..."` parses recognized phrases (darker, thinner, busier, more space, lower register, and friends) into signed dimensions in `intent.py`, and the planner in `arrangement.py` maps those dimensions onto register, density, velocity, and structure. The mapping is an explicit table you can read, output is deterministic, and the claim is testable in one command:

```bash
python tools/verify.py   # pytest suite + multi-feedback hash probe
```

Before the fix, every feedback string produced the same MD5. See `FINDINGS.md`, Finding 001, for the autopsy and the resolution hashes.

## Run it

Requires Python 3.12 and pydantic.

```bash
git clone https://github.com/michaelheavener4/muse.git
cd muse
python -m venv .venv && source .venv/bin/activate
pip install -e .
muse demo --prompt "dark and tense, 92 bpm"
```

The demo runs the full pipeline against the mock DAW and writes a MIDI sketch plus its analysis. The Ableton bridge path is macOS + Ableton Live 12 and is exercised separately (`live-demo`).

## Status and roadmap

- ✅ End-to-end pipeline: brief → plan → MIDI → analysis, with session memory and taste capture.
- ✅ Track 001 produced three real, human-directed revisions (see FINDINGS for why "human-directed" is the operative phrase).
- 🔨 **Current build: the planner upgrade.** v1's planner builds every arrangement from hardcoded seed patterns; FINDINGS.md proves user feedback changes nothing at note level. The upgrade makes the brief: key, emotion, density, feedback: actually drive note generation, with before/after MIDI hash evidence for every claimed change.
- ⬜ Packaging (pyproject, tests) as the repo matures.

## Findings

Engineering notes live in [FINDINGS.md](FINDINGS.md). Finding 001 (feedback is cosmetic at note level) includes the full method and hash table: steal the method, it's a good one: *if a system claims to respond to feedback, hash the output and vary the feedback.*

## License

MIT. See [LICENSE](LICENSE).
