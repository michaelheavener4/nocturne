# Stream A — Planner Feedback Fix (seat: Codex)

You are the planner seat on the MUSE fleet build. Branch: `planner-feedback`.

## The defect (Finding 001)
Feedback is cosmetic. `muse demo --prompt "dark and tense, 92 bpm"` yields
MD5 677dcf582ad908e00570f4b058e263da with ANY feedback or none.
src/muse/arrangement.py's planner (~25 lines) is hardcoded and never reads
the feedback that intent.py parses and memory stores.

## Deliverable
Make feedback materially condition the arrangement through an EXPLICIT,
INSPECTABLE mapping — a reviewer must be able to read the code and say
which feedback term changed which musical parameter:
- Parse feedback into dimensions (e.g. energy, density, brightness,
  tension) in intent.py.
- Map dimensions to planner parameters (note density, velocity range,
  register, rhythmic subdivision, section lengths) in arrangement.py.
- Same prompt + different feedback must produce audibly different,
  still-valid MIDI. Same prompt + same feedback must be deterministic
  (same hash every run — no unseeded randomness).

## Acceptance (Stream B's harness on the `harness` branch is the gate)
- 3+ feedback variants -> 3+ distinct MD5s, all valid MIDI.
- No-feedback output stays valid (need not equal the old hash, but say in
  your commit if it changed and why).
- Track 001 v3 baseline path (revise_track001.py) still works.
- Demo CLI contract unchanged (--prompt, --feedback, --data).

## Hard constraints
- Only src/muse/arrangement.py and src/muse/intent.py (plus, if truly
  needed, src/muse/models.py fields). Do NOT edit tests/ or tools/
  (Stream B owns them).
- No unseeded randomness. No new runtime dependencies.
- Commit early and often on `planner-feedback`; messages state what you ran.
