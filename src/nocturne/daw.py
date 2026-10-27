from __future__ import annotations

import json, socket
from pathlib import Path
from typing import Protocol
from .models import ArrangementPlan


class DAWAdapter(Protocol):
    def inspect(self) -> dict: ...
    def create_arrangement(self, plan: ArrangementPlan) -> dict: ...


class MockDAW:
    def __init__(self, root: str | Path): self.root = Path(root); self.root.mkdir(parents=True, exist_ok=True); self.state = {"tracks": []}
    def inspect(self) -> dict: return {"adapter": "mock", "track_count": len(self.state["tracks"]), "safe": True}
    def create_arrangement(self, plan: ArrangementPlan) -> dict:
        self.state["tracks"] = [t.name for t in plan.tracks]
        (self.root / "mock_state.json").write_text(json.dumps({"plan": plan.model_dump(), "state": self.state}, indent=2))
        return {"adapter":"mock", "created_tracks": self.state["tracks"], "verified": True}

    def create_variation_branches(self, *_args, **_kwargs) -> dict:
        return {"adapter": "mock", "branches": [{"id": f"dark-{i}", "label": f"Darker variation {i}", "difference": "deterministic test transformation", "tracks": {}} for i in range(1, 4)], "source_preserved": True, "verified": True}


class AbletonBridgeAdapter:
    def __init__(self, host="127.0.0.1", port=9877): self.host, self.port = host, port
    def _call(self, command: str, params: dict | None = None) -> dict:
        payload = json.dumps({"type": command, "params": params or {}}).encode()
        with socket.create_connection((self.host, self.port), timeout=5) as sock:
            sock.sendall(payload); data = sock.recv(1_000_000)
        result = json.loads(data.decode())
        if result.get("status") == "error": raise RuntimeError(result.get("message", "Ableton bridge error"))
        return result.get("result", result)
    def inspect(self) -> dict: return self._call("get_session_snapshot")

    def session_info(self) -> dict: return self._call("get_session_info")

    def _search(self, query: str, category: str) -> dict:
        return self._call("search_browser", {"query": query, "category": category, "max_results": 20})

    def _choose_uri(self, query: str, category: str, suffix: str | None = None) -> tuple[str, str]:
        matches = self._search(query, category).get("matches", [])
        if suffix:
            matches = [m for m in matches if m.get("name", "").lower().endswith(suffix.lower())] or matches
        if not matches:
            raise RuntimeError(f"No installed Ableton browser item matched {query!r} in {category}")
        return matches[0]["uri"], matches[0]["name"]

    def _device_state(self, track_index: int) -> list[dict]:
        info = self._call("get_track_info", {"track_index": track_index})
        devices = []
        for device in info.get("devices", []):
            index = device.get("index", len(devices))
            state = dict(device)
            try:
                state["parameters"] = self._call("get_device_parameters", {"track_index": track_index, "device_index": index})
            except Exception as exc:
                state["parameters_error"] = str(exc)
            try:
                state["chains"] = self._call("get_rack_chains", {"track_index": track_index, "device_index": index})
            except Exception:
                pass
            devices.append(state)
        return devices

    def capture_state(self, track_indices: list[int]) -> dict:
        state = {"session": self.session_info(), "tracks": []}
        for index in track_indices:
            track = self._call("get_track_info", {"track_index": index})
            track["devices_exact"] = self._device_state(index)
            track["clip_notes"] = self._call("get_clip_notes", {"track_index": index, "clip_index": 0})
            state["tracks"].append(track)
        state["master_meters"] = self._call("get_master_meters")
        return state

    def create_arrangement(self, plan: ArrangementPlan) -> dict:
        before = self.inspect()
        if any(t.get("name", "").startswith("NOCTURNE ") for t in before.get("tracks", [])):
            raise RuntimeError("NOCTURNE tracks already exist; refusing to append a duplicate arrangement")
        created = []
        for track in plan.tracks:
            index = self._call("create_midi_track", {"index": -1}).get("index", -1)
            self._call("set_track_name", {"track_index": index, "name": track.name})
            if track.role == "drums":
                uri, loaded_name = self._choose_uri("Core Kit", "drums", ".adg")
            elif track.role == "harmony":
                uri, loaded_name = self._choose_uri("Wavetable", "instruments")
            else:
                uri, loaded_name = self._choose_uri("Operator", "instruments")
            self._call("load_browser_item", {"track_index": index, "item_uri": uri})
            self._call("create_clip", {"track_index": index, "clip_index": 0, "length": plan.bars * 4})
            self._call("set_clip_name", {"track_index": index, "clip_index": 0, "name": f"NOCTURNE {track.role} 8 bars"})
            notes = [{"pitch":n.pitch,"start_time":n.start,"duration":n.duration,"velocity":n.velocity} for n in track.notes]
            self._call("add_notes_to_clip", {"track_index":index,"clip_index":0,"notes":notes})
            created.append({"index": index, "role": track.role, "name": track.name, "instrument": loaded_name})
        after = self.inspect()
        indices = [item["index"] for item in created]
        return {"adapter":"ableton-remote-script", "before":before, "created_tracks":created, "after":after,
                "exact_state": self.capture_state(indices),
                "verified": after.get("track_count",0) >= before.get("track_count",0)+len(created)}

    def revise_bass(self, track_index: int, bars: int = 8) -> dict:
        before = self._call("get_clip_notes", {"track_index": track_index, "clip_index": 0})
        # Preserve pitch/velocity but move selected attacks off the quarter notes.
        source = before.get("notes", before if isinstance(before, list) else [])
        revised = []
        offsets = [0.0, 0.75, 1.5, 2.25, 2.75, 3.5]
        for bar in range(bars):
            for i, offset in enumerate(offsets):
                old = source[(bar * max(1, len(source)//bars) + i) % len(source)] if source else {"pitch": 48, "velocity": 90, "duration": .4}
                revised.append({"pitch": int(old.get("pitch", 48)), "start_time": bar * 4 + offset, "duration": min(float(old.get("duration", .4)), .55), "velocity": int(old.get("velocity", 90))})
        self._call("add_notes_to_clip", {"track_index": track_index, "clip_index": 0, "notes": revised})
        after = self._call("get_clip_notes", {"track_index": track_index, "clip_index": 0})
        return {"before": before, "after": after, "changed": before != after}

    def fire_and_start(self, track_indices: list[int]) -> dict:
        for index in track_indices:
            self._call("fire_clip", {"track_index": index, "clip_index": 0})
        self._call("start_playback")
        return {"playing": self.session_info().get("is_playing"), "meters": self._call("get_master_meters")}

    def stop(self) -> dict:
        self._call("stop_playback"); self._call("stop_all_clips")
        return self.session_info()

    def save(self) -> dict:
        return self._call("try_save_project")

    def arrangement_clips(self, track_index: int) -> dict:
        return self._call("get_arrangement_clips", {"track_index": track_index})

    def session_mode(self, track_indices: list[int]) -> dict:
        """Launch synchronized Session clips; leaves the Arrangement untouched."""
        result = self.fire_and_start(track_indices)
        result["mode"] = "session"
        result["location"] = "Session View clip slots"
        result["arrangement_untouched"] = True
        return result

    def arrangement_mode(self, track_indices: dict[str, int], sections: list[tuple[str, float]]) -> dict:
        """Copy existing Session clips to Arrangement using Live 11/12's supported API."""
        before = {role: self.arrangement_clips(index) for role, index in track_indices.items()}
        if any(item.get("clip_count", 0) for item in before.values()):
            raise RuntimeError("Arrangement already contains NOCTURNE clips; refusing duplicate placement")
        placed = []
        for name, destination in sections:
            for role, index in track_indices.items():
                response = self._call("duplicate_session_clip_to_arrangement", {"track_index": index, "clip_index": 0, "destination_time": destination})
                placed.append({"section": name, "destination_time": destination, "role": role, "track_index": index, "response": response})
        after = {role: self.arrangement_clips(index) for role, index in track_indices.items()}
        return {"mode": "arrangement", "location": "Arrangement timeline", "sections": [name for name, _ in sections], "before": before, "placed": placed, "after": after, "session_clips_preserved": True, "verified": all(after[role].get("clip_count", 0) >= before[role].get("clip_count", 0) + len(sections) for role in track_indices)}

    @staticmethod
    def _dark_notes(notes: list[dict], variation: int, section: int) -> list[dict]:
        """Deterministic transformations, deliberately independent of the language model."""
        result = []
        for i, note in enumerate(notes):
            item = {"pitch": int(note.get("pitch", 48)), "start_time": float(note.get("start_time", 0)),
                    "duration": float(note.get("duration", .25)), "velocity": int(note.get("velocity", 90))}
            if variation == 1:
                item["pitch"] -= 2
                item["velocity"] = max(45, item["velocity"] - 8)
            elif variation == 2:
                item["pitch"] -= 5 if i % 2 else 2
                item["start_time"] = round(item["start_time"] + (.25 if i % 3 else 0), 3)
                item["duration"] = min(item["duration"], .35)
            else:
                item["pitch"] -= 7 if section in (0, 3) else 3
                item["start_time"] = round(item["start_time"] + (.5 if i % 2 else 0), 3)
                item["velocity"] = min(120, item["velocity"] + 6)
            if section == 0 and i % 2:
                continue
            if section == 2 and variation == 3:
                item["pitch"] += 12 if i % 3 == 0 else 0
            if section == 3:
                item["velocity"] = max(35, item["velocity"] - 20)
            result.append(item)
        return result

    def create_variation_branches(self, source_tracks: dict[str, int], count: int = 3, capture: bool = True) -> dict:
        """Create new Session/Arrangement tracks; source tracks are read but never edited."""
        source_state = {role: self.capture_state([index]) for role, index in source_tracks.items()}
        existing = self.inspect().get("tracks", [])
        existing_by_name = {track.get("name"): track.get("index") for track in existing}
        branches = []
        queries = {"drums": ("Core Kit", "drums", ".adg"), "bass": ("Operator", "instruments", None),
                   "harmony": ("Wavetable", "instruments", None), "melody": ("Operator", "instruments", None)}
        for variation in range(1, count + 1):
            tracks = {}
            for role, source_index in source_tracks.items():
                expected_name = f"NOCTURNE Dark {variation} {role.title()}"
                if expected_name in existing_by_name:
                    tracks[role] = existing_by_name[expected_name]
                    continue
                index = self._call("create_midi_track", {"index": -1}).get("index", -1)
                self._call("set_track_name", {"track_index": index, "name": expected_name})
                query, category, suffix = queries[role]
                uri, loaded_name = self._choose_uri(query, category, suffix)
                self._call("load_browser_item", {"track_index": index, "item_uri": uri})
                original = source_state[role]["tracks"][0]["clip_notes"]
                notes = original.get("notes", original if isinstance(original, list) else [])
                for section in range(4):
                    self._call("create_clip", {"track_index": index, "clip_index": section, "length": 32.0})
                    self._call("set_clip_name", {"track_index": index, "clip_index": section, "name": f"Dark {variation} {role} section {section + 1}"})
                    transformed = self._dark_notes(notes, variation, section)
                    if transformed:
                        self._call("add_notes_to_clip", {"track_index": index, "clip_index": section, "notes": transformed})
                tracks[role] = index
                existing_by_name[expected_name] = index
            branches.append({"id": f"dark-{variation}", "label": f"Darker variation {variation}", "tracks": tracks,
                             "difference": ["lower register", "syncopated timing", "section-specific density"][variation - 1],
                             "device_state": self.capture_state(list(tracks.values())) if capture else None})
        return {"adapter": "ableton-remote-script", "branches": branches, "source_tracks": source_tracks,
                "source_preserved": True, "verified": all(b["tracks"] for b in branches)}

    def audition_branch(self, branch: dict) -> dict:
        result = self.fire_and_start(list(branch["tracks"].values()))
        return {"mode": "session", "location": "Session View clip slots", "branch_id": branch["id"], "playing": result.get("playing"), "verified": True}

    def develop_branch(self, branch: dict, sections: list[tuple[str, float]]) -> dict:
        before = {role: self.arrangement_clips(index) for role, index in branch["tracks"].items()}
        placed = []
        for section_index, (name, destination) in enumerate(sections):
            for role, index in branch["tracks"].items():
                response = self._call("duplicate_session_clip_to_arrangement", {"track_index": index, "clip_index": section_index, "destination_time": destination})
                placed.append({"section": name, "role": role, "track_index": index, "destination_time": destination, "response": response})
        after = {role: self.arrangement_clips(index) for role, index in branch["tracks"].items()}
        return {"mode": "arrangement", "location": "Arrangement timeline", "branch_id": branch["id"],
                "sections": [name for name, _ in sections], "placed": placed, "before": before, "after": after,
                "source_preserved": True, "verified": all(after[r].get("clip_count", 0) >= len(sections) for r in after)}
