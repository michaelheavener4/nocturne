# Stream B2 — Gate v2: prompt truth (seat: OpenCode Go, free model)

Branch: `build2-gate`. You own tests/ and tools/ only. Build 1's gate
proved feedback changes the output. Tonight's gate proves the PROMPT
composes the first sketch, and it must FAIL on current main.

## Add these probes to tools/verify.py and tests/
1. **Prompt sensitivity:** two contrasting prompts ("dark and tense,
   D minor, 92 bpm" vs "bright and playful, C major, 120 bpm") produce
   DISTINCT output hashes.
2. **Key truth:** parse each output MIDI (project code only, no new MIDI
   library); the pitched notes' pitch classes must be a subset of the
   prompt key's scale pitch classes (drum channel exempt). A prompt whose
   key changes must change the pitch-class set.
3. **Determinism:** the same prompt run twice yields identical hashes.
4. All Build 1 tests/probes keep passing unchanged.

## Rules
- Probes 1-2 MUST fail against current main (planner v1). Verify that,
  and say so in a commit message, before Stream A2 merges.
- No edits outside tests/ and tools/. No new runtime dependencies.
- Commit early and often on `build2-gate`.
