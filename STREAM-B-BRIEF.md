# Stream B — Verification Harness (seat: OpenCode Go, free model)

You are the verification seat on the MUSE fleet build. Branch: `harness`.
Your harness is the merge gate for the whole build. Nobody merges to main
unless your tests pass.

## The defect you are proving (Finding 001)
`muse demo` currently produces byte-identical MIDI no matter what
`--feedback` says. Verified baseline on two machines:
prompt "dark and tense, 92 bpm" -> MD5 677dcf582ad908e00570f4b058e263da,
with or without feedback. Feedback is parsed and stored but never reaches
the planner.

## Deliverables (only these paths: tests/, tools/)
1. `tests/test_feedback_changes_output.py` — runs the demo pipeline with at
   least 3 materially different feedback inputs; asserts the resulting MIDI
   files have DISTINCT MD5 hashes and all parse as valid MIDI (header +
   track structure). This test MUST FAIL on the current code and PASS once
   Stream A's planner fix lands.
2. `tests/test_baseline_regression.py` — Track 001 v3 baseline (see
   revise_track001.py) still generates its known output; hash-check it.
3. `tools/verify.sh` (or .py) — one command that runs the full gate:
   pytest + the multi-feedback hash probe, prints hashes, exits nonzero on
   any failure.
4. Commit early and often on `harness`. Small commits, clear messages.

## Hard constraints
- Do NOT edit src/muse/arrangement.py or src/muse/intent.py (Stream A owns
  them). If you find a bug there, write it up as a failing test or an issue
  note in tests/ — do not fix it yourself.
- No new runtime dependencies for the package; test-only deps go in a
  clearly marked place and must be pip-installable.
- Every claim in a commit message must be something you actually ran.
