# Build A7 correction receipt

Two repeated mistake classes were selected from Findings 001–004 and the
Build 1–6 history. No planner or MIDI writer changes are needed.

1. **Shared contracts drift into parallel implementations.** Finding 004
   records a duplicate song command and a fallback planner using the wrong
   method name, removed by `0cb5e4b`. The pattern recurred in `5298b96`:
   CLI repetition analysis shipped a second implementation behind a dynamic
   import/name adapter even though `439efb6` supplied the canonical analysis.
   `615b899` subsequently added pop84 to the shared form registry while the
   CLI retained the three-form Build 5 list.

   Rung: architecture first. CLI analysis now imports the canonical function
   directly; CLI form choices use `SONG_FORMS`. Import errors surface at the
   boundary rather than silently selecting another algorithm. Static guards
   in `tools/check_contracts.py` reject duplicate command registrations, local
   repetition-report adapters/implementations, and a song entry point that
   does anything other than call `ArrangementPlanner.song`. The new test file
   also checks shared form choices and exercises CLI parsing for every form.
   These prevent the known divergence without changing musical generation.

2. **Claims/metadata substitute for observable input effects.** Finding 001
   found cosmetic feedback (`e51ba49` fixed generation); Finding 002 found
   cosmetic prompt keys (`cdf6678` fixed generation). Both carried apparently
   meaningful brief fields that did not reach notes. Their original hash
   gates (`2df8e8f`, `b93a69a`) established the recurring failure class.

   Rung: tests. Types can require a key or feedback field but cannot prove its
   semantic influence. Reworking the already corrected planner would risk
   musical changes. The new checks compare the requested part's actual notes
   under an isolated key change and a bass-density revision, disregarding
   title/key/rationale claims. Metadata-only fixtures retain identical notes
   and are rejected by the exact same assertion that accepts current output.

All new pytest checks are in `tests/test_correct_pass.py`; existing tests are
untouched. Negative fixtures reproduce duplicate registrations, a
`hasattr(plan_song)` fallback, parallel repetition analysis, a stale literal
form list, and metadata-only key/feedback changes. Each must raise the
expected failure. The static checker also rejects the actual original
`e6a1dc7` CLI source (canonical analysis import absent), and accepts current
source.

Byte locks were captured from `git archive HEAD src` before validation for
"dark and tense EDM track, D minor, 92 bpm":

| Form | Original and corrected MIDI MD5 |
| --- | --- |
| default / edm | 9a7380a0d56c55e13237172977ac01f9 |
| club | 036888b59e649c1ac1747dbd06a2f77b |
| pop | 96c43cea8f480e42e4f8b6a09035834d |
| pop84 | 198ae562ca074ebde0dcd64984a28163 |

The suite/gate also retain the groove lock
`91c023a806e8b839ae686232e1709ff1`. The architectural change deliberately
removes silent analysis fallback and exposes the already supported pop84
form to explicit CLI selection. Existing successful analysis and musical
output paths continue to use the same canonical functions.

Validation uses the existing project virtualenv interpreter with
`PYTHONPATH=src` (system Python lacks dependencies; network installation is
unavailable). Full pytest: **75 passed, 1 skipped**. The skip is the opt-in
live-provider test. `tools/verify.py`: **GATE PASSED**, all 17 probes green (and its nested pytest run: 75 passed, 1 skipped).
Changes are left uncommitted.
