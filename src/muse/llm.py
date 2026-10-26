from __future__ import annotations

import json, os, re, subprocess, time
from dataclasses import dataclass
from typing import Any

from .intent import IntentInterpreter
from .models import CreativeBrief


@dataclass
class ModelResult:
    brief: CreativeBrief
    provider: str
    model: str | None
    latency_ms: float
    output_chars: int
    usage: dict[str, Any] | None = None
    error: str | None = None


class OpenCodeModelRouter:
    """Discover models through the supported OpenCode CLI, with no provider API assumptions."""

    def __init__(self, timeout: int = 15):
        self.timeout = timeout
        self.catalog: dict[str, list[str]] = {}
        for provider in ("opencode-go", "opencode"):
            self.catalog[provider] = self._list(provider)

    def _list(self, provider: str) -> list[str]:
        try:
            result = subprocess.run(
                ["opencode", "models", provider],
                capture_output=True, text=True, timeout=self.timeout,
            )
            if result.returncode != 0:
                return []
            # OpenCode prints one model identifier per line, sometimes with metadata.
            models = []
            for line in result.stdout.splitlines():
                line = line.strip()
                if line.startswith(provider + "/"):
                    models.append(line.split()[0])
            return sorted(set(models))
        except (OSError, subprocess.SubprocessError):
            return []

    def select(self, complexity: str = "routine", requested: str | None = None) -> str | None:
        available = self.catalog.get("opencode-go", [])
        if requested and requested in available:
            return requested
        if complexity in {"complex", "ambiguous"}:
            priorities = ["opencode-go/deepseek-v4-pro", "opencode-go/deepseek-v4.1-flash", "opencode-go/glm-5.3"]
        else:
            priorities = ["opencode-go/deepseek-v4.1-flash", "opencode-go/glm-5.3-flash", "opencode-go/deepseek-v4-pro"]
        return next((model for model in priorities if model in available), None)


def _json_object(text: str) -> dict[str, Any]:
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.I)
    match = re.search(r"\{.*\}", text, re.S)
    if not match: raise ValueError("model response contained no JSON object")
    return json.loads(match.group(0))


class OpenCodeProvider:
    """Uses OpenCode's documented `run --format json` CLI, never an internal API."""

    def __init__(self, cwd: str = ".", model: str | None = None, timeout: int = 90):
        self.cwd = cwd
        self.timeout = timeout
        self.router = OpenCodeModelRouter()
        self.requested_model = model or os.environ.get("MUSE_MODEL")

    def availability(self) -> dict[str, list[str]]:
        return self.router.catalog

    def interpret(self, text: str, context: list[str] | None = None, complexity: str = "routine") -> ModelResult:
        selected = self.router.select(complexity, self.requested_model)
        if selected is None:
            fallback = IntentInterpreter().interpret(text)
            return ModelResult(
                fallback, "deterministic-fallback", None, 0.0, 0,
                usage={"status": "unavailable", "available_models": self.availability()},
                error="No OpenCode Go model is available in the installed CLI; no subscription or OpenRouter fallback was used.",
            )
        prompt = f"""You are MUSE, a conservative creative music assistant. Translate the artist's request into ONLY one JSON object matching this schema:
{{"intent": string, "emotional_dimensions": {{string: number}}, "musical_constraints": {{string: string|number}}, "sonic_references": [string], "arrangement_goals": [string], "uncertainty": [string], "assumptions": [string], "proposed_questions": [string, max one], "proposed_execution_plan": [string], "taste_prior": {{}}}}
Use questions only when an ambiguity materially changes the musical result. Never claim audio was analyzed. Keep project-specific intent authoritative.
Conversation context: {json.dumps(context or [])}
Artist request: {text}"""
        started = time.perf_counter()
        try:
            proc = subprocess.run(["opencode", "run", "--format", "json", "--pure", "--model", selected, "--dir", self.cwd, prompt], capture_output=True, text=True, timeout=self.timeout)
            raw = proc.stdout.strip()
            if proc.returncode != 0: raise RuntimeError(proc.stderr.strip() or f"opencode exited {proc.returncode}")
            texts: list[str] = []
            for line in raw.splitlines():
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                self._collect_text(event, texts)
            answer = "\n".join(texts) or raw
            brief = CreativeBrief.model_validate(_json_object(answer))
            return ModelResult(brief, "opencode-go", selected, (time.perf_counter()-started)*1000, len(raw), self._usage(raw))
        except Exception as exc:
            fallback = IntentInterpreter().interpret(text)
            return ModelResult(fallback, "deterministic-fallback", None, (time.perf_counter()-started)*1000, 0, {"status": "provider_failure", "requested_model": selected}, str(exc))

    @staticmethod
    def _usage(raw: str) -> dict[str, Any]:
        """Keep provider-reported usage only; missing token/cost fields remain unknown."""
        usage: dict[str, Any] = {"status": "reported_by_provider", "tokens": None, "cost": None}
        for line in raw.splitlines():
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(event, dict):
                for key in ("usage", "tokens"):
                    if isinstance(event.get(key), dict):
                        usage["tokens"] = event[key]
                if "cost" in event:
                    usage["cost"] = event["cost"]
        usage["cost_status"] = "reported" if usage["cost"] is not None else "not_reported"
        return usage

    @staticmethod
    def _collect_text(value: Any, out: list[str]) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                if key in {"text", "content"} and isinstance(child, str): out.append(child)
                elif key not in {"tool", "metadata"}: OpenCodeProvider._collect_text(child, out)
        elif isinstance(value, list):
            for child in value: OpenCodeProvider._collect_text(child, out)
