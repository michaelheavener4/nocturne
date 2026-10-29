# NOCTURNE — Feature Map

A trustworthy map of `src/nocturne`. One line per module: what it owns.
Marked `(inferred)` where the role was guessed from the module name and should
be confirmed against the code before you rely on it.

## CLI entry point

| Path | Owns |
| --- | --- |
| `src/nocturne/cli.py` | The `nocturne` command: argument parsing, subcommand dispatch, user-facing output. |
| `src/nocturne/__main__.py` | Thin `python -m nocturne` shim that delegates to `cli.py`. |
| `src/nocturne/__init__.py` | Package surface: version and re-exports; no behavior of its own. |

## Modules

| Module | Owns |
| --- | --- |
| `src/nocturne/analysis.py` | Analysis pass over generated material — the read side (inferred). |
| `src/nocturne/arrangement.py` | Turning a completed song into an arrangement (sections, layering, order) (inferred). |
| `src/nocturne/daw.py` | DAW-facing integration: session interchange or export the DAW consumes (inferred). |
| `src/nocturne/grooves.py` | Groove generation and rhythmic transforms; `apply_swing` lives here. |
| `src/nocturne/humming.py` | Melody/humming input capture or transcription into pitched material (inferred). |
| `src/nocturne/intent.py` | Modeling user intent — the normalized request the rest of the pipeline reads (inferred). |
| `src/nocturne/llm.py` | All LLM calls: prompting, model access, response parsing. |
| `src/nocturne/memory.py` | Persistence of prior sessions/knowledge that informs later generations (inferred). |
| `src/nocturne/midi.py` | MIDI primitives: note/track types, read/write, file-level byte truth. |
| `src/nocturne/models.py` | Core data structures shared across the pipeline (inferred). |
| `src/nocturne/preferences.py` | User taste/preferences loading and application to generation (inferred). |
| `src/nocturne/render.py` | Rendering generated material to final output (audio or file bytes) (inferred). |
| `src/nocturne/session.py` | Session lifecycle: open, mutate, save — one writer per file set. |
| `src/nocturne/song.py` | Song construction; `plan_song` is the one true planner (see Finding 004). |
| `src/nocturne/songbook.py` | Collection/persistence layer for finished songs (inferred). |
| `src/nocturne/taste.py` | Taste model — stylistic preference handling distinct from `preferences.py` (inferred). |
| `src/nocturne/telemetry.py` | Instrumentation and metrics emission (inferred). |

## The merge gate

- **`tools/verify.py` is the merge gate.** It runs the full pytest suite plus
  MIDI truth probes and prints **`GATE PASSED`** on success. Nothing merges
  without it.
- New tests belong in `tests/`; the gate runs them as-is.

## Baselines that must never move

These are asserted in `tools/verify.py` and in `tests/`. If either changes,
the gate fails — that is the point. Do not "fix" the baseline to make CI green.

- **Groove baseline hash:** `91c023a806e8b839ae686232e1709ff1`
- **Default song bytes:** exact default song output, byte-for-byte.

## Known traps

- **Parallel seats use git worktrees.** Each parallel work session works in its
  own worktree. Maintain **one writer per file set** — two writers on the same
  files will clobber each other.
- **Finding 001 — user feedback must change output bytes.** A feedback loop that
  does not move the output bytes is a no-op; the gate treats that as a defect.
- **Chorus register rises by scale degrees at generation.** The register lift is
  computed in scale degrees while generating — never applied later as a
  post-hoc semitone transpose.
- **`apply_swing` in `grooves.py` is duck-typed on purpose.** It accepts
  `SimpleNamespace` in tests. Do not narrow it to a concrete type.
- **Finding 004 — the song planner arrived twice.** `song.py:plan_song` is the
  one true planner. Any other planner is a duplicate; route around it and
  delete it rather than reconciling the two.
