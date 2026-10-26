# MUSE: Findings


Engineering findings from building MUSE, written the way they were earned: by testing the system against its own claims.

---

## Finding 001: In v1, feedback is cosmetic at note level

**Claim tested:** MUSE revises its output in response to feedback.

**Method:** Run the full pipeline five times on the same starting brief, varying the feedback/refinement input between runs. Hash every output MIDI (MD5) and compare bytes, not vibes.

**Result:** All five outputs are the same file.

| Run | Output | MD5 |
|---|---|---|
| track001 (base) | `muse_sketch.mid` | `677dcf582ad908e00570f4b058e263da` |
| track001-r1 | `muse_sketch.mid` | `677dcf582ad908e00570f4b058e263da` |
| track001-r2 | `muse_sketch.mid` | `677dcf582ad908e00570f4b058e263da` |
| track001-r3 | `muse_sketch.mid` | `677dcf582ad908e00570f4b058e263da` |
| track001-r4 | `muse_sketch.mid` | `677dcf582ad908e00570f4b058e263da` |

**Mechanism: three separate causes, each sufficient on its own:**

1. **The planner barely reads the brief.** `ArrangementPlanner.plan()` consumes exactly two values from the `CreativeBrief`: `tempo_bpm` and `key`. The brief's emotional dimensions, arrangement goals, and uncertainty: all computed by the interpreter: are never passed into note generation.
2. **The notes are hardcoded seeds.** Drum, bass, harmony, and melody parts are literal note lists in `arrangement.py`, tiled across 8 bars by a repeat helper. Even the `key` the planner does read is only a label on the plan: change the key and the seed pitches do not move.
3. **Refinement changes text, not music.** In REFINE mode the interpreter appends a goal string ("preserve approved material and revise only the requested element"): and nothing downstream consumes goals. The only inputs that reach the output at all are an explicit `NNN bpm` in the prompt (tempo metadata) and dark/tense keywords (the key label).

**What is NOT cosmetic:** Track 001's three revisions are real, distinct artifacts:

| Revision | MD5 |
|---|---|
| v1: bass thinned | `84cf556a302aa2c805e2440d18446bab` |
| v2: darker, lower | `65b9812b85cab599629d863d2e228dc2` |
| v3: dark, thin, final bar | `7db06e0cc8c841b044392d45c44da1a4` |

: but they were produced by human-directed revision work (a revision script and the Ableton bridge's note transforms, e.g. darkening/transposition at the adapter layer), not by the agent's own feedback loop. The system demos like a creative partner and behaves like a stamp.

**The fix (current build):** the planner upgrade. The brief must drive generation: seeds derived from key and mode, density and register driven by the emotional dimensions, and a refinement path that takes the previous `ArrangementPlan` plus feedback as inputs and produces measurably different notes. Acceptance test is the same hash method inverted: same brief + different feedback must yield different MD5s, and each claimed change (thinner bass, darker harmony) must be visible in the note data, not just the rationale text.

**Lesson:** if a system claims to respond to feedback, hash the output and vary the feedback. Anything less is reviewing the demo, not the system.
