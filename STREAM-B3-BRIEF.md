# Stream B3 — Gate v3: session truth (seat: OpenCode Go, free model)

Branch: `build3-gate`. You own tests/ and tools/ only.
Gate v3 proves the session remembers. All probes run with the
deterministic interpreter (use_model=False / --offline paths): the gate
NEVER calls a live LLM. Probes 1-3 MUST fail on current main (no
rounds ledger exists there); verify and say so in a commit.

## Contract under test (from Stream A3)
Session root gains: rounds/round-NNN.mid + round-NNN.json per round and
rounds.jsonl with {"n", "kind", "text", "accumulated_feedback",
"frozen_parts", "md5"} per round. CLI: muse session --data DIR
--say "TEXT" (repeatable), printing result JSON with the round md5.

## Probes to add (keep every v1+v2 probe green)
1. **Ledger integrity:** scripted create + 2 revises -> 3 rounds;
   rounds.jsonl md5 fields match the actual .mid files on disk; all
   3 hashes distinct.
2. **Preservation:** revise with "keep the bass, thinner drums" ->
   the bass part's note list in round-001.json equals round-000.json
   exactly, while the drum part differs.
3. **Accumulation:** round 2's ledger accumulated_feedback contains
   round 1's feedback text, and round 2's hash differs from both
   earlier rounds.
4. **Live-eval placeholder:** one test marked to skip unless
   MUSE_LIVE_EVAL=1 (body may be a simple provider smoke check);
   it must SKIP cleanly in the default run.
Commit early and often on build3-gate; messages state what you ran.
