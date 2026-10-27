from __future__ import annotations

import json, os, re, subprocess, time
from dataclasses import dataclass
from typing import Any

from .intent import IntentInterpreter
from .models import CreativeBrief


# Mark on ModelResult.provider when the brief came from IntentInterpreter.
FALLBACK_PROVIDER = "deterministic-fallback"
# Free default. Used when it appears in the discovered catalog.
PINNED_FREE_MODEL = "opencode/deepseek-v4.1-flash-free"
# Scan the free OpenCode catalog first so "first discovered" is stable.
DISCOVERY_PROVIDERS = ("opencode", "opencode-go")


@dataclass
class ModelResult:
    brief: CreativeBrief
    provider: str
    model: str | None
    latency_ms: float
    output_chars: int
    usage: dict[str, Any] | None = None
    error: str | None = None


def _cause(exc: BaseException) -> str:
    message = " ".join(str(exc).split())
    name = type(exc).__name__
    if not message or message == name:
        return name
    return f"{name}: {message}"


def _clip(text: str, limit: int = 500) -> str:
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


class OpenCodeModelRouter:
    """Discover models through the supported OpenCode CLI, with no provider API assumptions."""

    def __init__(self, timeout: int = 15):
        self.timeout = timeout
        self.catalog: dict[str, list[str]] = {}
        self.errors: list[str] = []
        self._discovered = False
        self._binary_error: str | None = None

    def discover(self) -> None:
        """List models once. A CLI failure is recorded and does not raise."""
        if self._discovered:
            return
        self._discovered = True
        for provider in DISCOVERY_PROVIDERS:
            models, error = self._list(provider)
            self.catalog[provider] = models
            if error and error not in self.errors:
                self.errors.append(error)

    def models_in_discovery_order(self) -> list[str]:
        """Model ids in CLI order. Not sorted: the first entry is the first discovered."""
        self.discover()
        found: list[str] = []
        for provider in DISCOVERY_PROVIDERS:
            for model in self.catalog.get(provider, []):
                if model not in found:
                    found.append(model)
        return found

    def select(self, complexity: str = "routine", requested: str | None = None) -> tuple[str | None, str]:
        """Choose a model and say why.

        An explicit listed request wins. Otherwise the pinned free model wins when
        it was discovered, otherwise the first discovered id. complexity is kept
        for callers and does not change the choice.
        """
        del complexity
        available = self.models_in_discovery_order()
        if requested and requested in available:
            return requested, "requested"
        if PINNED_FREE_MODEL in available:
            return PINNED_FREE_MODEL, "pinned"
        if available:
            return available[0], "first-discovered"
        return None, "none"

    def _list(self, provider: str) -> tuple[list[str], str | None]:
        if self._binary_error:
            return [], self._binary_error
        try:
            result = subprocess.run(
                ["opencode", "models", provider],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                stdin=subprocess.DEVNULL,
                timeout=self.timeout,
            )
        except FileNotFoundError:
            self._binary_error = "opencode binary not found on PATH"
            return [], self._binary_error
        except subprocess.TimeoutExpired:
            return [], f"opencode models {provider} timed out after {self.timeout}s"
        except OSError as exc:
            return [], _clip(_cause(exc))
        except subprocess.SubprocessError as exc:
            return [], _clip(_cause(exc))
        if result.returncode != 0:
            detail = (result.stderr or "").strip() or (result.stdout or "").strip()
            message = f"opencode models {provider} exited {result.returncode}"
            if detail:
                message = f"{message}: {detail}"
            return [], _clip(message)
        models: list[str] = []
        prefix = provider + "/"
        for line in result.stdout.splitlines():
            line = line.strip()
            if not line.startswith(prefix):
                continue
            model_id = line.split()[0]
            if model_id not in models:
                models.append(model_id)
        return models, None


def _json_object(text: str) -> dict[str, Any]:
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.I)
    match = re.search(r"\{.*\}", text, re.S)
    if not match:
        raise ValueError("model response contained no JSON object")
    try:
        parsed = json.loads(match.group(0))
    except json.JSONDecodeError as exc:
        raise ValueError(f"model response contained malformed JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise ValueError("model response JSON was not an object")
    return parsed


def _provider_of(model: str) -> str:
    provider, sep, _rest = model.partition("/")
    return provider if sep else "opencode"


class OpenCodeProvider:
    """Uses OpenCode's documented `run --format json` CLI, never an internal API.

    interpret() does not raise when the provider fails. The brief then comes from
    IntentInterpreter, provider is deterministic-fallback, and error carries the cause.

    If NOCTURNE_LLM_FIXTURE points at a JSON CreativeBrief dump, interpret() returns
    that brief with provider "fixture" and does not call opencode. A fixture that
    cannot be read or validated falls back the same way, still without opencode.
    """

    def __init__(self, cwd: str = ".", model: str | None = None, timeout: int = 90, discover_timeout: int = 15):
        self.cwd = cwd
        self.timeout = timeout
        self.router = OpenCodeModelRouter(timeout=discover_timeout)
        self.requested_model = model or os.environ.get("NOCTURNE_MODEL")

    def availability(self) -> dict[str, list[str]]:
        self.router.discover()
        return self.router.catalog

    def interpret(self, text: str, context: list[str] | None = None, complexity: str = "routine") -> ModelResult:
        fixture = os.environ.get("NOCTURNE_LLM_FIXTURE", "").strip()
        if fixture:
            return self._interpret_fixture(fixture, text)
        started = time.perf_counter()
        try:
            selected, reason = self.router.select(complexity, self.requested_model)
        except Exception as exc:
            return self._fallback(text, started, None, exc, {"status": "provider_failure", "selection": "none"})
        if selected is None:
            if self.router.errors:
                cause = "; ".join(self.router.errors)
            else:
                cause = (
                    "No OpenCode model is available in the installed CLI; "
                    "no subscription or OpenRouter fallback was used."
                )
            return self._fallback(
                text,
                started,
                None,
                cause,
                {"status": "unavailable", "selection": reason, "available_models": self.availability()},
            )
        try:
            raw = self._run(selected, _prompt(text, context))
            brief = CreativeBrief.model_validate(_json_object(_answer(raw)))
            usage = _usage(raw)
            usage["selection"] = reason
            return ModelResult(
                brief,
                _provider_of(selected),
                selected,
                _elapsed_ms(started),
                len(raw),
                usage,
            )
        except Exception as exc:
            return self._fallback(
                text,
                started,
                selected,
                exc,
                {"status": "provider_failure", "selection": reason, "requested_model": selected},
            )

    def _interpret_fixture(self, path: str, text: str) -> ModelResult:
        started = time.perf_counter()
        try:
            with open(path, encoding="utf-8") as handle:
                payload = json.loads(handle.read())
            brief = CreativeBrief.model_validate(payload)
        except Exception as exc:
            return self._fallback(
                text,
                started,
                None,
                exc,
                {"status": "fixture_invalid", "fixture": path},
            )
        return ModelResult(
            brief,
            "fixture",
            None,
            _elapsed_ms(started),
            os.path.getsize(path),
            {"status": "fixture", "fixture": path},
        )

    def _run(self, selected: str, prompt: str) -> str:
        try:
            proc = subprocess.run(
                ["opencode", "run", "--format", "json", "--pure", "--model", selected, "--dir", self.cwd, prompt],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                stdin=subprocess.DEVNULL,
                timeout=self.timeout,
            )
        except subprocess.TimeoutExpired as exc:
            raise TimeoutError(f"opencode run timed out after {self.timeout}s") from exc
        except FileNotFoundError as exc:
            raise FileNotFoundError("opencode binary not found on PATH") from exc
        if proc.returncode != 0:
            detail = (proc.stderr or "").strip() or (proc.stdout or "").strip()
            message = f"opencode exited {proc.returncode}"
            if detail:
                message = f"{message}: {detail}"
            raise RuntimeError(message)
        return proc.stdout.strip()

    def _fallback(
        self,
        text: str,
        started: float,
        model: str | None,
        cause: BaseException | str,
        usage: dict[str, Any] | None = None,
    ) -> ModelResult:
        error = _clip(cause) if isinstance(cause, str) else _clip(_cause(cause))
        return ModelResult(
            IntentInterpreter().interpret(text),
            FALLBACK_PROVIDER,
            model,
            _elapsed_ms(started),
            0,
            usage,
            error,
        )


def _elapsed_ms(started: float) -> float:
    return (time.perf_counter() - started) * 1000


def _prompt(text: str, context: list[str] | None) -> str:
    return f"""You are NOCTURNE, a conservative creative music assistant. Translate the artist's request into ONLY one JSON object matching this schema:
{{"intent": string, "emotional_dimensions": {{string: number}}, "musical_constraints": {{string: string|number}}, "sonic_references": [string], "arrangement_goals": [string], "uncertainty": [string], "assumptions": [string], "proposed_questions": [string, max one], "proposed_execution_plan": [string], "taste_prior": {{}}}}
Use questions only when an ambiguity materially changes the musical result. Never claim audio was analyzed. Keep project-specific intent authoritative.
Conversation context: {json.dumps(context or [])}
Artist request: {text}"""


def _answer(raw: str) -> str:
    texts: list[str] = []
    for line in raw.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        _collect_text(event, texts)
    return "\n".join(texts) or raw


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


def _collect_text(value: Any, out: list[str]) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if key in {"text", "content"} and isinstance(child, str):
                out.append(child)
            elif key not in {"tool", "metadata"}:
                _collect_text(child, out)
    elif isinstance(value, list):
        for child in value:
            _collect_text(child, out)
