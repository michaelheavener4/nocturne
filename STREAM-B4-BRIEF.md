# Stream B4 brief: Gate v4, song truth probes (Build 4)

Owner complaint that defines this gate: "the melody is repetitive... songs
that change and make sense, transitions between parts." Gate v4 proves a
generated song has real form, real harmony, a developing melody, and real
transitions. You own: tests/ and tools/verify.py. Nothing else.

## Contract you test against (Stream A4 builds it)
- CLI: muse song --prompt "TEXT" --out DIR writes song.mid + song.json
  (full ArrangementPlan dump, including a form list of sections
  {name, role, start_bar, bars, energy} and absolute-bar notes).
- Templates: edm = 44 bars (intro/verse/build/drop/breakdown/drop/outro),
  pop = 56 bars. Deterministic: same prompt, same md5.
- Harmony: per-song progression (minor i-VI-III-VII, major I-V-vi-IV);
  all pitches in the key scale; melody/harmony favor chord tones.
- Melody: 2-bar motif + seeded variation operators; never more than 2
  consecutive identical melody bars except a flagged final-chorus hook
  return. Breakdown has no drums. Section-final bars are transitions.

## Probes to add (tests + tools/verify.py, same style as Gate v3)
1. form integrity: sections contiguous from bar 0, bars sum to
   plan.bars, song.mid valid MIDI.
2. key truth, song-wide: 100 percent of all pitches in the key scale;
   chord-tone share of melody+harmony notes reported and at least 50
   percent per section.
3. melody variation: in each drop/chorus, no run of more than 2
   identical consecutive melody bars (unless flagged hook return);
   verse melody notes differ from drop melody notes.
4. transitions: the bar before each drop/chorus differs measurably
   from that sections median bar (drum note count or mean register);
   breakdown sections contain zero drum notes.
5. determinism: two muse song runs on the same prompt give the same
   md5, distinct from the 8-bar demo baseline aaf9da4b.

## Rules
- Probes 1-5 MUST fail on current main (there is no song command and
  plans are 8 bars); verify and report that failure explicitly.
- Never call a live LLM. Offline/deterministic paths only.
- v1-v3 probes stay green and untouched in behavior.
- Commit on build4-gate with clear messages; state probe results
  against current main in your final summary.
