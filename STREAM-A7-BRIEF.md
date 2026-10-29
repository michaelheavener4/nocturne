# STREAM A7 BRIEF — /correct pass over Builds 1–6 (Codex seat)

You are building in a worktree of NOCTURNE (agentic music engine, Python,
src/nocturne). Read FINDINGS.md and skim `git log --oneline -40` first.

TASK (poteto /correct pattern): mine FINDINGS.md (Findings 001–004) and the
commit history for REPEATED agent/engineer mistake classes — not one-offs.
For the top 2–3 repeated classes, implement a correction AT THE HIGHEST
RUNG available (architecture > types > lint/static > test > docs) and add
a check that PROVABLY FAILS on the original mistake (demonstrate by
temporarily reverting or by a fixture reproducing the old shape).

Rules:
- NO musical behavior changes. The groove baseline (91c023a806e8b839ae686232e1709ff1),
  the default Build 5/6 song bytes, and EDM/club song bytes must not move.
  Full pytest suite + tools/verify.py must stay green.
- Write your checks as ONE new file: tests/test_correct_pass.py. Do not edit
  existing test files.
- Touch src/nocturne only where a correction genuinely belongs there;
  prefer tooling/types/guards over engine edits.
- End with: the mistake classes found (with finding/commit evidence), the
  rung chosen for each fix and why, proof each new check fails on the old
  mistake and passes now, and the suite/gate result. Leave changes uncommitted.
