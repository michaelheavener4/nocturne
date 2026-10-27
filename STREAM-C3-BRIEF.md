# Stream C3 — Translator hardening: the LLM can fail safely (seat: Grok Build)

Branch: `build3-llm`. You own src/muse/llm.py only.

## Current truth
llm.py's OpenCodeProvider discovers models via the opencode CLI
(15s timeouts) and returns a ModelResult carrying a CreativeBrief.
CreativeSession trusts model.brief. The questions nobody has audited:
what happens on timeout, on malformed model output, on a brief that
fails validation, on opencode missing from PATH? Tonight the translator
becomes boring under failure.

## Deliverables
1. **Guaranteed fallback.** ANY provider failure (missing binary,
   timeout, nonzero exit, unparseable output, brief failing pydantic
   validation) yields a ModelResult whose brief comes from the
   deterministic IntentInterpreter, with provider marked as the
   fallback and error carrying the cause. interpret() never raises
   for a provider problem.
2. **Pinned default model.** Model selection prefers a pinned free
   OpenCode model (opencode/deepseek-v4.1-flash-free) when listed,
   else the first discovered; the choice is recorded in ModelResult.
3. **Fixture mode.** If $MUSE_LLM_FIXTURE points at a JSON file
   containing a CreativeBrief dump, interpret() returns it (marked
   provider "fixture") without calling opencode: the translator
   becomes deterministically testable.
4. Prove each failure mode you claim with a local run or a tiny
   throwaway script, and say which in the commit messages.
No changes outside llm.py. Commit early and often on build3-llm.
