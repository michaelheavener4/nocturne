# Stream C — Packaging + CI Hardening (seat: Grok Build)

You are the hardening seat on the MUSE fleet build. Branch: `hardening`.
Streams A (planner) and B (test harness) own src/muse/arrangement.py,
src/muse/intent.py, tests/ and tools/. You own everything that makes the
repo trustworthy to outsiders: packaging and CI.

## Deliverables (only these paths)
1. `.github/workflows/ci.yml` — on push and PR: Python 3.11-3.13 matrix,
   `pip install -e .`, run the test suite (pytest) if tests/ exists on the
   merged tree, and a demo smoke run (`muse demo --prompt "ci smoke"` +
   assert a MIDI file is produced). Keep it fast and dependency-light.
2. pyproject.toml hygiene — confirm declared deps match actual imports
   (numpy was missing until 2026-10-26 and crashed clean installs; audit
   for any other undeclared import and fix it here, in packaging only).
   Add a `dev` optional-dependencies group (pytest) if absent.
3. A short `CONTRIBUTING.md`: how to install, run the demo, run the gate.
4. Commit early and often on `hardening`.

## Hard constraints
- Do NOT edit src/muse/arrangement.py, src/muse/intent.py, tests/, tools/.
- No new runtime dependencies beyond what the audit proves is imported.
- Every claim in a commit message must be something you actually ran
  (CI YAML can be validated locally with python -c yaml parse or actionlint
  if present; say which you used).
