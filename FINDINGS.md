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

---

## Finding 001 — RESOLVED (2026-10-26)

The planner upgrade described above shipped, built as a multi-agent fleet exercise on a second machine (Omarchy Linux) and merged only after passing a purpose-built verification gate.

**What changed:**
- `intent.py` gained `parse_feedback`: recognized revision phrases map to signed dimensions (energy, density, brightness, tension, length), each bounded to −1/0/+1. Conflicting directions cancel; wording repetition changes nothing. The mapping is a readable table, not a model call.
- `arrangement.py` now consumes those dimensions in the plan: register, note density, velocity, and section/final-bar changes follow the parsed feedback. Output stays deterministic — same brief + same feedback, same bytes.
- No-feedback generation is byte-identical to the v1 baseline: the fix changed what feedback does, not what silence does.

**Verification (the same hash method, inverted):** the merge gate (`tools/verify.py`: pytest suite + multi-feedback hash probe) was written FIRST, by a different agent on a free model, and failed against the old code exactly as designed (3 feedback variants, 1 hash). After the fix, on `main`:

| Feedback (prompt: "dark and tense, 92 bpm") | MD5 |
|---|---|
| none | `677dcf582ad908e00570f4b058e263da` (baseline, unchanged) |
| "make the bass less busy and let the notes ring" | `84cf556a302aa2c805e2440d18446bab` |
| "take it darker and move the harmony into a lower register" | `b1604267a0ee778e9e12c1e00cc2d51b` |
| "thin out the drums, add space, and write a new final-bar motif" | `f6791b973d7c4503d85388cae5a9fc05` |

One result worth pausing on: the "less busy bass" output is byte-identical to Track 001 v1 (`84cf556a…`) — a revision that originally took human-directed scripting. The agent's own feedback loop now produces it.

**Process note:** three coding agents (different vendors, different models) worked the same repo in parallel worktrees, one writer per file set, with this gate as the only road to `main`. The gate caught nothing the second time because it had already caught everything the first time. That is what gates are for.

---

## Finding 002: In v1, the prompt did not compose either

**Claim tested:** MUSE writes music from a plain-language brief.

**Method:** vary ONLY the prompt (key, mood) on the v1 planner and hash the outputs; inspect where the seed pitches come from.

**Result:** the seed notes were literal constants in `arrangement.py`. The brief's key was a label on the plan: change the key and no pitch moved. `CreativeBrief` carried `emotional_dimensions` the planner never read. The system responded to revisions (after Finding 001's fix) but the opening sketch was always the same sketch wearing a name tag.

**Resolution (2026-10-26, same fleet pattern as Finding 001):**
- Pitches are generated from scale degrees: the key in the prompt selects the scale, and bass/harmony/melody are built from degrees, with register and velocity baselines set by the brief's own dimensions.
- Variation is seeded: SHA-256 of the brief content (feedback suffix stripped) seeds the RNG, so the same brief gives the same bytes on any machine, and feedback reshapes the same sketch instead of reseeding it.
- The v1 no-feedback baseline `677dcf58…` is retired. New baseline for "dark and tense, 92 bpm": `aaf9da4b9d5a3332e256d10edbc91b86`.
- Gate v2 (written first, verified failing on v1): prompt-sensitivity, key-truth (pitch classes subset of the prompt key's scale), and determinism probes join the feedback probes. All pass on main.
- Hearing no longer needs a DAW: `muse render` / `muse demo --render` wrap the system fluidsynth; the C major acceptance run reproduced its claimed hash exactly and emitted a 3.3 MB WAV in the same command.

| Prompt (no feedback) | MD5 |
|---|---|
| dark and tense, 92 bpm | `aaf9da4b9d5a3332e256d10edbc91b86` |
| dark and tense, D minor, 92 bpm | `769380191092db33b4029298e6ea4206` |
| bright and playful, C major, 120 bpm | `b38c6c75166a6586ec8780b95b8b1905` |

Feedback also composes: two revision sentences applied together produce a fourth, distinct hash (`d5d63931…`), neither single-feedback output. Stacking by accumulated instruction works today; the program keeping its own session state is the next build.

**Lesson:** a generator that cannot be surprised by its own input is a stamp with good marketing. Hash the prompt's effect, not just the feedback's.

## Finding 003: the session had no memory (2026-10-26)

**Method:** script a multi-round session against the v2 code and try to prove, from files on disk, what each revision did.

**Result:** impossible. Revisions lived only in process memory: no round files, no ledger, no record of what was asked, what was kept, or what changed. "Keep the bass" was a claim the program made about itself with no evidence anyone could check. The LLM translator had the same manners problem in reverse: a provider failure (missing binary, timeout, unparseable output) raised instead of degrading.

**Resolution (2026-10-26, Build 3, same fleet pattern):**
- Sessions persist every round: `rounds/round-NNN.mid` + `round-NNN.json`, and a `rounds.jsonl` ledger carrying each round's text, accumulated feedback, frozen parts, and MD5. The driver is `muse session --data DIR --say "TEXT"` (repeatable; `--offline` for the deterministic interpreter).
- "Keep the bass" freezes that part in the planner: frozen parts are copied note for note from the previous round while the rest is replanned. Feedback accumulates: round N's plan carries every revision sentence so far.
- The translator never raises for a provider problem: any failure returns the deterministic interpreter's brief, marked as fallback, with the cause recorded. The default model is pinned (`opencode/deepseek-v4.1-flash-free` when listed), and a fixture mode (`MUSE_LLM_FIXTURE` pointing at a CreativeBrief JSON) lets tests run with no provider at all.
- Gate v3 adds session probes: ledger integrity, frozen-part preservation, feedback accumulation. The live-provider test stays opt-in (`MUSE_LIVE_EVAL=1`).

**The gate earned its keep at this merge:** on the first merged run, the preservation probe failed on the sentence "keep the bass, thinner drums". The freeze detector consumed the whole sentence and froze the drums too, so the output was byte-identical to the previous round. Fixed by scoping the keep-list to the run of role mentions at the start of the phrase; a new instruction ends it. Gate after the fix: 7 of 7 probes, 16 passed, 1 skipped (live eval).

| Scripted session (offline) | MD5 |
|---|---|
| create: "Make a dark and tense electronic groove at 92 bpm" | `aaf9da4b9d5a3332e256d10edbc91b86` |
| revise: "keep the bass, thinner drums" (frozen: bass) | `b9bceded2bc49c7544a1ce9e1ec0f6ca` |
| revise: "take it darker" (feedback accumulated) | `5ae79eb612a9613303d619060e63da94` |

Round 0 and round 1 share every bass note exactly; the drums differ. Round 2 rendered to WAV in the same run (3.3 MB, FluidR3_GM).

**Lesson:** a revision you cannot audit is a promise. State is not bookkeeping; it is what makes "keep that, change this" a fact instead of a vibe.

## Finding 004 — The song planner arrived twice (2026-10-26, Build 4)

**Claim (owner direction, 2026-10-26 21:52):** after hearing the 8-bar loop live in Ableton, the melody was repetitive and the form static. MUSE needed key awareness, song structure, harmony, a developing melody, and transitions: whole songs in the shapes of an EDM track or a Grimes song.

**Result (Build 4, fleet):** `muse song --prompt "TEXT" [--render]` writes a complete song: form templates (edm: intro/verse/build/drop/breakdown/drop/outro, 44 bars; pop: 56 bars with pre-chorus and bridge), a per-song chord progression (minor i–VI–III–VII, major I–V–vi–IV) with harmony on chord tones and bass on roots, a 2-bar motif that returns varied (seeded operators: transpose, octave, rhythm, tail, rest), transition bars and risers into drops, and a breakdown with no drums. Sessions route song-shaped requests to the same planner; plain groove requests still produce the byte-identical 8-bar baseline `aaf9da4b`. The songbook module (progressions, voicings, fills, risers, section energies), written by the Mac's local model, rides along as a content library. Gate v4 adds five song probes: form integrity, key truth, melody variation, transitions, determinism. Gate: 12 of 12 probes; test suite 28 passed, 1 skipped.

**The merge earned its keep this time:** Build 4's streams A (planner) and C (render/session wiring) collided. Each had registered its own `song` subcommand, so the merged CLI refused to start; and C, finding no planner method yet, had shipped a complete fallback planner behind an adapter that looked for a method named `plan_song`. A named its method `song`, the adapter never matched, and the merge briefly carried two planners. Resolution: one planner (A's), one subcommand (C's handler, which renders at the plan tempo). The fallback planner, some 490 lines, is deleted; `song.py` is now only the shared classifier for "is this a song request" plus a delegating entry point. Stream briefs now pin shared method names in the contract, not just shapes.

| Proof on merged main (2026-10-26) | Value |
|---|---|
| EDM song, "dark and tense edm track at 92 bpm", MIDI MD5 | `f6b7d767d1ec7326b0edaa35679d4659` |
| Same song rendered, WAV duration / size | 117.5 s / 20.7 MB (FluidR3_GM) |
| Session create, same prompt (full song round) | `b5d845f94a314ca98947681e90612b47` |
| Session create, groove prompt (baseline unchanged) | `aaf9da4b9d5a3332e256d10edbc91b86` |

**Lesson:** parallel builders need name-level contracts. A shape-compatible interface with a different method name is a second implementation waiting to happen.
