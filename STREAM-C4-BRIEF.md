# Stream C4 brief: full-song render + session wiring (Build 4)

You own: src/muse/render.py integration for long files, the song render
path in src/muse/cli.py, and the session hookup in src/muse/session.py.
Do NOT touch models.py / arrangement.py / intent.py (Stream A4 owns
them) or tests/ (Stream B4 owns them).

## Contract you build against (Stream A4 builds it)
- muse song --prompt "TEXT" --out DIR writes song.mid + song.json:
  a full-form plan (edm 44 bars, pop 56 bars), deterministic md5.

## What to build
1. SONG RENDER: muse song --render renders the full song to song.wav
   with the existing soundfont resolution order (flag, env, user dir,
   system). A 44-bar song at 92 bpm is about 115 seconds; the render
   must complete and report duration and file size. Missing soundfont
   exits nonzero naming the fix, same manners as muse render.
2. SESSION HOOKUP: when a create request asks for a full song (the
   words song, track, edm, or a structure word like drop/chorus), the
   CreativeSession plans through the song planner instead of the 8-bar
   planner, and the round MIDI in the ledger is the full song. Plain
   groove requests keep the 8-bar path byte-identical to today
   (baseline aaf9da4b must not move). The rounds.jsonl contract is
   unchanged.
3. Manners: any provider failure in a live session still falls back
   per Build 3; nothing in this stream may weaken the Build 3
   fallback, pin, or fixture behavior.

## Proof required (state it in commit messages and your summary)
- A rendered song WAV: prompt, md5 of the .mid, WAV duration/size.
- A scripted offline session: song request round md5 distinct from
  aaf9da4b; groove request round md5 exactly aaf9da4b.
- Existing suite still passes.
