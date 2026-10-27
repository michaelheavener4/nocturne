# Stream A4 brief: song form, harmony, and melody that develops (Build 4)

Owner direction (her words, after hearing the 8-bar loop live in Ableton):
"the melody is repetitive. I want MUSE to be aware of keys, song structure,
melody, harmony, and be able to generate songs that change and make sense,
transitions between parts of a song, like an EDM beat or a Grimes song."

You own: src/muse/models.py, src/muse/arrangement.py, src/muse/intent.py,
and the new song CLI subcommand in src/muse/cli.py. Nothing else.

## Shared contract
- ArrangementPlan gains a form field: a list of sections, each
  {name, role, start_bar, bars, energy (0..1)}. Track notes are absolute
  across the whole timeline; plan.bars = sum of section bars.
- New CLI: muse song --prompt "TEXT" [--out DIR] writes song.mid and
  song.json (the full plan dump) into the out dir and prints JSON with
  the md5. Deterministic under the Planner v2 seed law (SHA-256 of
  brief content, feedback suffix stripped): same prompt, same bytes,
  any machine.
- The existing 8-bar demo/session behavior is UNCHANGED. Gates v1-v3
  must stay green untouched.

## What to build
1. FORM. Two templates selected from the brief: edm (default for
   dance/beat/edm language): intro 4, verse 8, build 8, drop 8,
   breakdown 4, drop 8, outro 4 = 44 bars. pop (song/vocal language):
   intro 4, verse 8, pre-chorus 4, chorus 8, verse 8, chorus 8,
   bridge 4, chorus 8, outro 4 = 56 bars. Each section has an energy
   target driving density, velocity, and register per part.
2. HARMONY. A chord progression per song, from the brief key/mode:
   minor default i-VI-III-VII (one chord per bar; verse may hold 2 bars
   per chord), major default I-V-vi-IV. The harmony track plays chord
   tones (voicings, not block stacks every beat); the bass follows
   chord roots with octave movement; breakdown strips harmony to
   root/fifth. Every pitch emitted must belong to the key scale, and
   melody/harmony should favor the current chord tones.
3. MELODY THAT DEVELOPS. Generate a 2-bar motif from scale degrees.
   Each return of the motif applies ONE seeded variation operator:
   degree transpose, octave shift, rhythmic shift, tail rewrite, or
   rest insertion. Verse = sparse variant (fewer notes, lower
   register); drop/chorus = the hook at full density. Rule: never more
   than 2 consecutive identical melody bars except a flagged hook
   return in the final chorus.
4. TRANSITIONS. The last bar of every section is a transition bar:
   drum fill (density spike), and into a drop/chorus a 2-bar riser
   (density ramp + register climb) at the end of the build section;
   drop/chorus bars start with an impact (all parts on beat 1).
   Breakdown drops the drums entirely.

## Proof required (state it in your final summary; coordinator commits)
- muse song on an EDM prompt and a pop prompt: section lists, bar
  totals, and md5s; two runs identical.
- A note audit printout: percentage of melody+harmony pitches that are
  scale tones (must be 100) and chord-tone share per section.
- Existing suite still passes.
