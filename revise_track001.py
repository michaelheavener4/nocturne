"""Track 001 plan-level revisions, built with MUSE's own models/midi/analysis.
MUSE v1's ArrangementPlanner is hardcoded (feedback text does not change notes:
proven 2026-10-24: 4 demo runs, identical MIDI md5). These revisions apply the
feedback at the plan level so the iterations are real and measurable."""
import json, sys
from pathlib import Path
sys.path.insert(0, "src")
from muse.models import ArrangementPlan
from muse.midi import write_midi
from muse.analysis import analyze_arrangement

base = json.loads(Path("data/track001/projects/muse_sketch.json").read_text())["plan"]
out = Path("data/track001-revisions"); out.mkdir(parents=True, exist_ok=True)

def build(name, plan_dict):
    plan = ArrangementPlan(**plan_dict)
    mid = write_midi(plan, out / f"{name}.mid")
    rep = analyze_arrangement(plan)
    Path(out / f"{name}.json").write_text(json.dumps({"plan": plan.model_dump(), "analysis": rep.model_dump()}, indent=2))
    counts = {t.name: len(t.notes) for t in plan.tracks}
    print(name, "| notes:", rep.metrics["note_count"], "| per-bar:", rep.metrics["notes_per_bar"],
          "| pitch:", rep.metrics["pitch_min"], "-", rep.metrics["pitch_max"], "| tracks:", counts)
    return plan

def clone():
    return json.loads(json.dumps(base))

# V1: "make the bass less busy": bass keeps beats 0 and 2 only, notes lengthened
v1 = clone()
for t in v1["tracks"]:
    if t["role"] == "bass":
        t["notes"] = [dict(n, duration=1.6) for n in t["notes"] if (n["start"] % 4) in (0.0, 2.0)]
build("track001-v1-bass-thinned", v1)

# V2: "darker, lower register": motif + harmony down 5 semitones, bass down 3 (floor 36 drums untouched)
v2 = clone()
for t in v2["tracks"]:
    if t["role"] in ("melody", "harmony"):
        t["notes"] = [dict(n, pitch=n["pitch"] - 5) for n in t["notes"]]
    if t["role"] == "bass":
        t["notes"] = [dict(n, pitch=n["pitch"] - 3) for n in t["notes"]]
build("track001-v2-darker-lower", v2)

# V3: V1+V2 combined + final-bar variation (planner rationale: "Final-bar variation can be added during refinement"):
# motif in bar 8 gets an extra high note at beat 30.5 and 31.5
v3 = clone()
for t in v3["tracks"]:
    if t["role"] == "bass":
        t["notes"] = [dict(n, duration=1.6, pitch=n["pitch"] - 3) for n in t["notes"] if (n["start"] % 4) in (0.0, 2.0)]
    if t["role"] in ("melody", "harmony"):
        t["notes"] = [dict(n, pitch=n["pitch"] - 5) for n in t["notes"]]
    if t["role"] == "melody":
        t["notes"] += [{"pitch": 67, "start": 30.5, "duration": 0.45, "velocity": 84, "confidence": None},
                       {"pitch": 70, "start": 31.5, "duration": 0.45, "velocity": 88, "confidence": None}]
build("track001-v3-dark-thin-finalbar", v3)

b = ArrangementPlan(**base); r = analyze_arrangement(b)
print("baseline | notes:", r.metrics["note_count"], "| per-bar:", r.metrics["notes_per_bar"], "| pitch:", r.metrics["pitch_min"], "-", r.metrics["pitch_max"])
