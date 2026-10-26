# Stream A2 — Planner v2: the prompt composes (seat: Codex)

Branch: `build2-planner`. Build 1 made FEEDBACK change the music. Tonight
the PROMPT has to compose the first sketch. Files you own:
src/muse/arrangement.py, src/muse/intent.py, src/muse/models.py. Nothing else.

## Current truth (read arrangement.py first)
The planner's seeds are literal note lists. The brief's key is a label:
change the prompt's key and the seed pitches do not move.
CreativeBrief already carries emotional_dimensions (dict[str, float]) and
musical_constraints, computed by IntentInterpreter; the planner ignores
almost all of it. Prompt adjectives deliberately do NOT act as revisions
(the [feedback: ...] suffix extraction stays as is).

## Deliverables
1. **Key/mode-derived generation.** Parse the key from musical_constraints
   (e.g. "D minor", "C major"; default sensibly when absent). Build the
   scale; generate bass/harmony/melody pitches FROM scale degrees, not
   literal pitch constants. Changing the prompt key must change the actual
   pitch content, and generated pitch classes must belong to the scale
   (drums exempt).
2. **Brief dimensions shape the first plan.** Consume emotional_dimensions
   (and any explicit constraints) to set the plan's baselines: note density,
   register center, velocity range, tension/dissonance level. A "bright and
   playful" brief and a "dark and tense" brief at the same tempo must
   produce audibly and measurably different sketches BEFORE any feedback.
3. **Determinism.** Any variation is driven by a seeded RNG seeded from the
   brief content. Same brief in, same bytes out, every run, every machine.
4. **No regressions.** The Build 1 feedback path works unchanged on top of
   the new generation; tools/verify.py v1 probes (feedback distinctness,
   no-feedback stability WITHIN a version) still pass. The no-feedback
   baseline hash WILL change versus v1: that is the point. Record the new
   baseline in your final commit message with the prompt it came from.

## Acceptance (Stream B2's gate decides)
- "dark and tense, D minor, 92 bpm" vs "bright and playful, C major,
  120 bpm" -> distinct hashes AND distinct pitch-class sets, each
  consistent with its own scale.
- Same prompt twice -> identical hash.
- Feedback on the new planner still yields distinct hashes per feedback.
Commit early and often; messages state what you ran and the hashes you saw.
