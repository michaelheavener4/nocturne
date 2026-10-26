from __future__ import annotations

import json, re, time
from pathlib import Path

from .arrangement import ArrangementPlanner
from .daw import AbletonBridgeAdapter, MockDAW
from .llm import ModelResult, OpenCodeProvider
from .intent import IntentInterpreter
from .memory import SoundMemory
from .models import ArrangementPlan, MemoryItem
from .telemetry import LocalTelemetry


class CreativeSession:
    def __init__(self, root: str | Path, live: bool = False, use_model: bool = True):
        self.root = Path(root); self.root.mkdir(parents=True, exist_ok=True)
        self.live = live
        self.adapter = AbletonBridgeAdapter() if live else MockDAW(self.root / "mock_daw")
        self.llm = OpenCodeProvider(cwd=str(self.root.parent.parent if self.root.name == "data" else self.root))
        self.use_model = use_model
        self.memory = SoundMemory(self.root / "memory")
        self.telemetry = LocalTelemetry(self.root / "telemetry.jsonl")
        self.context: list[str] = []
        self.plan: ArrangementPlan | None = None
        self.track_indices: dict[str, int] = {}
        self.branches: list[dict] = []
        self.selected_branch: dict | None = None
        self.started = False

    def _live_tracks(self) -> dict[str, int]:
        snapshot = self.adapter.inspect()
        return {t["name"]: t["index"] for t in snapshot.get("tracks", []) if t.get("name", "").startswith("MUSE ")}

    def handle(self, text: str) -> dict:
        started = time.perf_counter(); self.context.append(text)
        low = text.lower().strip()
        try:
            if not self.started:
                result = self._create_from_prompt(text) if self._looks_like_create(low) else {"status": "unsupported", "message": "Start with a musical creation request, such as 'Make a dark electronic groove with an atmospheric pad.'"}
            elif any(x in low for x in ("syncop", "more rhythmic", "change the bass")) and "bass" in low:
                result = self._revise_bass()
            elif ("three" in low or "3" in low) and ("variation" in low or "version" in low) and ("dark" in low or "groove" in low):
                result = self._create_variations()
            elif re.search(r"(?:select|choose|pick)\s+(?:variation|version)\s*[1-3]", low):
                result = self._select_variation(low)
            elif "audition" in low and ("variation" in low or "version" in low):
                result = self._audition_variation(low)
            elif "develop" in low or "turn it into a song" in low:
                result = self._develop_selected()
            elif "arrangement" in low or all(x in low for x in ("intro", "verse", "chorus", "outro")):
                result = self._arrangement_mode()
            elif "session view" in low or "session mode" in low or "launch the loops" in low:
                result = self._session_mode()
            elif "keep" in low and "drum" in low and ("exact" in low or "unchanged" in low):
                result = {"status": "acknowledged", "preservation": "drums locked for subsequent revisions"}
            elif "mechanical" in low and ("synth" in low or "synthesizer" in low or "bass" in low):
                result = self._mechanical_sound()
            elif low.startswith("save ") and ("bass" in low or "sound" in low or "preset" in low):
                result = self._save_preset(text)
            elif low.startswith("use ") and ("again" in low or "bass" in low or "sound" in low):
                result = self._recall_preset(text)
            elif low in {"approve", "approved", "save this", "yes"}:
                result = {"status": "approved", "note": "The current state is ready to save; use a named preset request to persist exact device state."}
            elif low in {"quit", "exit"}:
                result = {"status": "session_complete"}
            else:
                result = {"status": "unsupported", "message": "I can create an arrangement, revise bass rhythm, preserve drums, make an Operator sound more mechanical, or save/recall an exact preset."}
            result["context_turn"] = len(self.context)
            self.context.append(json.dumps(result, default=str))
            self.telemetry.record("creative_session_turn", started, result.get("status") not in {"unsupported", "error"}, tool_calls=int(self.live), manual_corrections=0)
            return result
        except Exception as exc:
            self.telemetry.record("creative_session_turn", started, False, tool_calls=int(self.live))
            return {"status": "error", "error": str(exc), "context_turn": len(self.context)}

    @staticmethod
    def _is_command(text: str) -> bool:
        return any(text.startswith(x) for x in ("make ", "keep ", "change ", "save ", "use ", "approve", "exit", "quit", "yes"))

    @staticmethod
    def _looks_like_create(text: str) -> bool:
        return any(x in text for x in ("make ", "create ", "build ", "groove", "arrangement"))

    def _create_from_prompt(self, text: str) -> dict:
        if self.use_model:
            model = self.llm.interpret(text, self.context[-6:])
        else:
            fallback = IntentInterpreter().interpret(text)
            model = ModelResult(fallback, "deterministic-test", None, 0.0, 0)
        self.plan = ArrangementPlanner().plan(model.brief)
        self.started = True
        if self.live:
            existing = self._live_tracks()
            if existing:
                self.track_indices = {"drums": existing.get("MUSE Drums", -1), "bass": existing.get("MUSE Bass", -1), "harmony": existing.get("MUSE Atmosphere", -1), "melody": existing.get("MUSE Motif", -1)}
                execution = {"status": "reused_existing_muse_tracks", "tracks": existing, "verified": True}
            else:
                execution = self.adapter.create_arrangement(self.plan)
                self.track_indices = {x["role"]: x["index"] for x in execution["created_tracks"]}
            save = self.adapter.save()
            reminder = None if save.get("saved") else "Ableton bridge cannot save this Live version; press Cmd+S manually."
        else:
            execution = self.adapter.create_arrangement(self.plan); self.track_indices = {t.role: i for i,t in enumerate(self.plan.tracks)}; reminder = None
        return {"status": "created", "provider": model.provider, "model": model.model, "model_error": model.error, "latency_ms": round(model.latency_ms, 1), "brief": model.brief.model_dump(), "execution": execution, "question": model.brief.proposed_questions[0] if model.brief.proposed_questions else None, "manual_save_reminder": reminder}

    def _source_tracks(self) -> dict[str, int]:
        tracks = self.track_indices or self._live_tracks()
        return {"drums": tracks.get("drums", tracks.get("MUSE Drums", -1)),
                "bass": tracks.get("bass", tracks.get("MUSE Bass", -1)),
                "harmony": tracks.get("harmony", tracks.get("MUSE Atmosphere", -1)),
                "melody": tracks.get("melody", tracks.get("MUSE Motif", -1))}

    def _create_variations(self) -> dict:
        source = {role: index for role, index in self._source_tracks().items() if index >= 0}
        if self.live:
            result = self.adapter.create_variation_branches(source, 3)
        else:
            result = self.adapter.create_variation_branches(source, 3)
        self.branches = result.get("branches", [])
        return {"status": "branched", "operation": "three darker variations", "branches": [
            {k: branch.get(k) for k in ("id", "label", "difference", "tracks")} for branch in self.branches],
            "source_preserved": result.get("source_preserved", False), "execution": result,
            "model_status": "deterministic musical transformation; model is used only for interpretation when available",
            "manual_save_reminder": "Press Cmd+S manually." if self.live else None}

    @staticmethod
    def _variation_number(text: str) -> int | None:
        match = re.search(r"(?:variation|version)\s*([1-3])", text)
        return int(match.group(1)) if match else None

    def _select_variation(self, text: str) -> dict:
        number = self._variation_number(text)
        if number is None or number > len(self.branches):
            return {"status": "unsupported", "message": "Create the three variations first, then select variation 1, 2, or 3."}
        self.selected_branch = self.branches[number - 1]
        return {"status": "selected", "branch_id": self.selected_branch["id"], "label": self.selected_branch["label"], "non_destructive": True}

    def _audition_variation(self, text: str) -> dict:
        number = self._variation_number(text)
        if number is None or number > len(self.branches):
            return {"status": "unsupported", "message": "Specify variation 1, 2, or 3."}
        branch = self.branches[number - 1]
        if self.live:
            result = self.adapter.audition_branch(branch)
            result["status"] = "auditioning"
            return result
        return {"status": "auditioning", "mode": "session", "location": "Session View clip slots", "branch_id": branch["id"]}

    def _develop_selected(self) -> dict:
        if not self.selected_branch:
            return {"status": "unsupported", "message": "Select a variation before developing it into a song."}
        sections = [("intro", 0.0), ("verse", 32.0), ("chorus", 64.0), ("outro", 96.0)]
        if self.live:
            result = self.adapter.develop_branch(self.selected_branch, sections)
            result["status"] = "created" if result.get("verified") else "error"
            result["manual_save_reminder"] = "Press Cmd+S manually." if not self.adapter.save().get("saved") else None
            return result
        return {"status": "planned", "mode": "arrangement", "location": "Arrangement timeline", "sections": [x[0] for x in sections], "branch_id": self.selected_branch["id"], "source_preserved": True}

    def _revise_bass(self) -> dict:
        if self.live:
            bass = self.track_indices.get("bass", self._live_tracks().get("MUSE Bass", -1)); drums = self.track_indices.get("drums", self._live_tracks().get("MUSE Drums", -1))
            before_drums = self.adapter._call("get_clip_notes", {"track_index": drums, "clip_index": 0})
            revision = self.adapter.revise_bass(bass, 8)
            after_drums = self.adapter._call("get_clip_notes", {"track_index": drums, "clip_index": 0})
            return {"status": "revised", "element": "bass rhythm", "changed": revision["changed"], "drums_unchanged": before_drums == after_drums, "manual_save_reminder": "Press Cmd+S manually." if not self.adapter.save().get("saved") else None}
        track = next(t for t in self.plan.tracks if t.role == "bass")
        original = track.notes; track.notes = [n.model_copy(update={"start": n.start + (.25 if i % 2 else 0)}) for i,n in enumerate(original)]
        self.adapter.create_arrangement(self.plan)
        return {"status": "revised", "element": "bass rhythm", "changed": original != track.notes, "drums_unchanged": True}

    def _session_mode(self) -> dict:
        if not self.live:
            return {"status": "launched", "mode": "session", "location": "Session View clip slots", "arrangement_untouched": True}
        indices = list(self.track_indices.values()) or list(self._live_tracks().values())
        return {"status": "launched", **self.adapter.session_mode(indices)}

    def _arrangement_mode(self) -> dict:
        if not self.live:
            return {"status": "planned", "mode": "arrangement", "location": "Arrangement timeline", "sections":["intro","verse","chorus","outro"]}
        tracks = self.track_indices or {"drums": self._live_tracks().get("MUSE Drums", -1), "bass": self._live_tracks().get("MUSE Bass", -1), "harmony": self._live_tracks().get("MUSE Atmosphere", -1), "melody": self._live_tracks().get("MUSE Motif", -1)}
        tracks = {k:v for k,v in tracks.items() if v >= 0}
        result = self.adapter.arrangement_mode(tracks, [("intro",0.0),("verse",32.0),("chorus",64.0),("outro",96.0)])
        result["status"] = "created" if result["verified"] else "error"
        result["manual_save_reminder"] = "Press Cmd+S manually." if not self.adapter.save().get("saved") else None
        return result

    def _mechanical_sound(self) -> dict:
        if not self.live: return {"status": "planned", "element": "synth character", "action": "mechanical oscillator waveform and tighter articulation"}
        index = self.track_indices.get("bass", self._live_tracks().get("MUSE Bass", -1))
        params = self.adapter._call("get_device_parameters", {"track_index": index, "device_index": 0}).get("parameters", [])
        names = {p["name"]: p for p in params}
        changed = []
        if "Osc-A Wave" in names and names["Osc-A Wave"].get("value_items"):
            self.adapter._call("set_device_parameter", {"track_index": index, "device_index": 0, "parameter": "Osc-A Wave", "value": "Saw 16"}); changed.append("Osc-A Wave")
        if "Shaper Drive" in names:
            self.adapter._call("set_device_parameter", {"track_index": index, "device_index": 0, "parameter": "Shaper Drive", "value": 0.2}); changed.append("Shaper Drive")
        return {"status": "revised" if changed else "unsupported", "element": "synth character", "parameters_changed": changed, "manual_save_reminder": "Press Cmd+S manually." if not self.adapter.save().get("saved") else None}

    def _save_preset(self, text: str) -> dict:
        match = re.search(r"(?:as|called)\s+(.+)$", text, re.I); label = (match.group(1).strip() if match else "favorite bass")
        if self.live:
            index = self.track_indices.get("bass", self._live_tracks().get("MUSE Bass", -1)); state = {"track_index": index, "device_state": self.adapter._device_state(index)}
        else:
            state = {"plan": self.plan.model_dump() if self.plan else {}}
        path = self.root / "presets" / (re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_") + ".json"); path.parent.mkdir(parents=True, exist_ok=True); path.write_text(json.dumps(state, indent=2))
        item = self.memory.store(MemoryItem(kind="preset", label=label, description="Approved MUSE session preset", path=str(path), metadata={"source":"live-device-state" if self.live else "mock-plan"}))
        return {"status": "saved", "label": label, "memory_id": item, "path": str(path), "exact_state_saved": True}

    def _recall_preset(self, text: str) -> dict:
        query = text.replace("use", "").replace("again", "").strip()
        matches = self.memory.search(query) or self.memory.search("bass")
        if not matches: return {"status": "unsupported", "message": "No saved preset matched; I did not claim a recall."}
        path = matches[0]["path"]
        if self.live and path and Path(path).is_file():
            state = json.loads(Path(path).read_text())
            index = self.track_indices.get("bass", self._live_tracks().get("MUSE Bass", -1))
            applied = []
            for device in state.get("device_state", []):
                for param in (device.get("parameters") or {}).get("parameters", []):
                    try:
                        self.adapter._call("set_device_parameter", {"track_index": index, "device_index": device.get("index", 0), "parameter": param["name"], "value": param["value"]})
                        applied.append(param["name"])
                    except Exception:
                        pass
            return {"status": "recalled", "label": matches[0]["label"], "path": path, "exact_state_available": True, "parameters_applied": len(applied), "manual_save_reminder": "Press Cmd+S manually." if not self.adapter.save().get("saved") else None}
        return {"status": "recalled", "label": matches[0]["label"], "path": path, "exact_state_available": bool(path), "applied": False if self.live else "mock-plan"}
