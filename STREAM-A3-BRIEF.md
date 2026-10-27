# Stream A3 — Session rounds: the program remembers (seat: Codex)

Branch: `build3-session`. Files you own: src/muse/session.py,
src/muse/arrangement.py (planner hook only), src/muse/cli.py (the
scripted driver only). Not intent.py, not llm.py, not tests/tools.

## Current truth
CreativeSession (session.py) already interprets (LLM via llm.py's
OpenCodeProvider, or the table when use_model=False), plans with
ArrangementPlanner v2, and executes to the mock DAW. But it is an
in-memory interactive loop: no persisted rounds, no hashes, no way to
drive it headlessly, and its revise paths predate the Build 1/2
feedback machinery. The demo path ignores sessions entirely.

## Shared contract (Streams B3/C3 build against exactly this)
Every create/revise handled by the session ALSO persists, in the session
root:
- `rounds/round-000.mid`, `round-001.mid`, ... the round's sketch MIDI
  (the ArrangementPlan rendered with the project's own write_midi).
- `rounds/round-000.json`, ... the plan dump for that round.
- `rounds.jsonl` at the session root, one JSON object per round:
  {"n": int, "kind": "create"|"revise", "text": str,
   "accumulated_feedback": str, "frozen_parts": [roles...],
   "md5": hex md5 of the round's .mid file}

## Deliverables
1. **Rounds ledger** per the contract, for both create and revise flows
   (including the existing variation/develop paths if they produce a new
   plan: ledger them as kind "revise" with their text).
2. **Feedback through the current stack.** A revise round's brief
   carries the ACCUMULATED feedback (every revise text so far, joined)
   in the [feedback: ...] form Planner v2 already understands, so
   round 2 never silently drops round 1's instruction.
3. **Part preservation.** "keep the bass" (also drums/melody/harmony;
   "keep everything else" freezes all unmentioned parts) in a revise
   text freezes those parts: ArrangementPlanner gains
   plan(brief, previous=None, frozen=frozenset()) and frozen parts'
   notes are copied from the previous plan verbatim. Record frozen
   parts in the ledger.
4. **Scripted driver.** `muse session --data DIR --say "TEXT"` runs ONE
   handle() call non-interactively and prints the result JSON including
   the round's md5; repeat --say to script a whole conversation.
   Existing interactive `create` behavior unchanged.
Determinism with use_model=False must hold end to end: same script,
same hashes, any machine. Commit early and often; if the sandbox blocks
git again, leave the tree tidy and list intended commit messages.
