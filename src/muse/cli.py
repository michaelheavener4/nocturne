from __future__ import annotations

import argparse, json, os, subprocess, sys, time
from pathlib import Path
from .analysis import analyze_arrangement
from .arrangement import ArrangementPlanner
from .daw import AbletonBridgeAdapter, MockDAW
from .humming import transcribe_wav
from .intent import IntentInterpreter
from .memory import SoundMemory
from .midi import write_midi
from .models import MemoryItem
from .taste import TasteStore
from .session import CreativeSession


def demo(args) -> int:
    root=Path(args.data)
    taste_prior = TasteStore(root / "taste").report() if (root / "taste" / "taste.sqlite3").exists() else {}
    brief=IntentInterpreter().interpret(args.prompt, "REFINE" if args.feedback else "CREATE", taste_prior=taste_prior)
    if args.feedback: brief.intent += f" [feedback: {args.feedback}]"
    plan=ArrangementPlanner().plan(brief); adapter=AbletonBridgeAdapter() if args.live else MockDAW(root/"mock_daw")
    inspection=adapter.inspect(); execution=adapter.create_arrangement(plan)
    midi=write_midi(plan, root/"projects"/"muse_sketch.mid"); report=analyze_arrangement(plan)
    root.mkdir(parents=True, exist_ok=True); (root/"projects"/"muse_sketch.json").write_text(json.dumps({"brief":brief.model_dump(),"plan":plan.model_dump(),"inspection":inspection,"execution":execution,"analysis":report.model_dump()}, indent=2))
    item_id=SoundMemory(root/"memory").store(MemoryItem(kind="arrangement",label="MUSE eight-bar sketch",description=brief.intent, path=str(midi),metadata={"tempo":plan.tempo,"key":plan.key}))
    print(json.dumps({"question":brief.proposed_questions[0] if brief.proposed_questions else None,"assumptions":brief.assumptions,"execution":execution,"analysis":report.metrics,"memory_id":item_id,"midi":str(midi)}, indent=2)); return 0


def hum(args) -> int:
    notes=transcribe_wav(args.wav); from .models import ArrangementPlan, TrackPlan
    plan=ArrangementPlan(title="Hummed melody",tempo=120,bars=max(1, int((max((n.note.start+n.note.duration for n in notes), default=4)+3)//4)),key="C",tracks=[TrackPlan(name="Hummed Melody",role="melody",instrument="MIDI",notes=[n.note for n in notes])])
    out=write_midi(plan,args.output); print(json.dumps({"output":str(out),"notes":[n.model_dump() for n in notes]},indent=2)); return 0


def live_demo(args) -> int:
    """Run the real-DAW workflow; caller must have opened a disposable Live Set."""
    root = Path(args.data); root.mkdir(parents=True, exist_ok=True)
    brief = IntentInterpreter().interpret(args.prompt)
    plan = ArrangementPlanner().plan(brief)
    adapter = AbletonBridgeAdapter()
    report = {"workflow": "real-ableton-muse-disposable", "started_at": time.time()}
    report["before"] = adapter.inspect()
    execution = adapter.create_arrangement(plan)
    report["creation"] = execution
    indices = [item["index"] for item in execution["created_tracks"]]
    report["playback"] = adapter.fire_and_start(indices)
    audio_out = Path(args.audio_out)
    if args.capture_audio:
        ear = Path(args.ear) if args.ear else None
        if ear is None or not ear.exists():
            report["audio_capture"] = {"error": "ear tool not configured: pass --ear PATH or set MUSE_EAR_PATH"}
        else:
            capture = subprocess.run([sys.executable, str(ear), "hear", str(args.capture_seconds), "--out", str(audio_out)], text=True, capture_output=True)
            report["audio_capture"] = {"returncode": capture.returncode, "stdout": capture.stdout, "stderr": capture.stderr, "path": str(audio_out)}
    adapter.stop()
    drum = next(item["index"] for item in execution["created_tracks"] if item["role"] == "drums")
    bass = next(item["index"] for item in execution["created_tracks"] if item["role"] == "bass")
    before_drums = adapter._call("get_clip_notes", {"track_index": drum, "clip_index": 0})
    revision = adapter.revise_bass(bass, plan.bars)
    after_drums = adapter._call("get_clip_notes", {"track_index": drum, "clip_index": 0})
    report["revision"] = {"bass": revision, "drums_unchanged": before_drums == after_drums}
    report["state_after_revision"] = adapter.capture_state(indices)
    report["save"] = adapter.save()
    report["after"] = adapter.inspect()
    report["manual_save_path"] = args.expected_live_set
    (root / "real_live_workflow.json").write_text(json.dumps(report, indent=2))
    print(json.dumps({"report": str(root / "real_live_workflow.json"), "creation_verified": execution["verified"], "playing": report["playback"].get("playing"), "drums_unchanged": report["revision"]["drums_unchanged"], "save": report["save"], "audio_capture_returncode": report.get("audio_capture", {}).get("returncode")}, indent=2))
    return 0 if execution["verified"] and report["revision"]["drums_unchanged"] else 1


def create_session(args) -> int:
    session = CreativeSession(args.data, live=args.live, use_model=not args.offline)
    print("MUSE interactive session. Type 'exit' to finish.")
    if args.live:
        print("Live mode is active; only the current user-approved/disposable set may be changed.")
    while True:
        try:
            text = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            print(); break
        if not text: continue
        result = session.handle(text)
        print(json.dumps(result, indent=2, default=str))
        if result.get("status") == "session_complete": break
    (Path(args.data) / "session_context.json").write_text(json.dumps(session.context, indent=2))
    return 0


def arrangement_command(args) -> int:
    if not args.live:
        print(json.dumps({"status":"unsupported", "message":"Arrangement placement requires --live; offline mode cannot verify Ableton timeline state."}, indent=2)); return 1
    session = CreativeSession(args.data, live=True, use_model=False)
    session.started = True
    result = session.handle("put the current loops into an arrangement with intro, verse, chorus, and outro")
    report_path = Path(args.data) / "arrangement_mode.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(result, indent=2, default=str))
    result["report"] = str(report_path)
    print(json.dumps(result, indent=2, default=str)); return 0 if result.get("status") == "created" else 1


def main(argv=None):
    p=argparse.ArgumentParser(prog="muse"); sub=p.add_subparsers(dest="command",required=True)
    d=sub.add_parser("demo"); d.add_argument("--prompt",required=True); d.add_argument("--feedback"); d.add_argument("--live",action="store_true"); d.add_argument("--data",default="data"); d.set_defaults(func=demo)
    h=sub.add_parser("transcribe-hum"); h.add_argument("wav"); h.add_argument("--output",default="data/hums/melody.mid"); h.set_defaults(func=hum)
    m=sub.add_parser("memory-search"); m.add_argument("query"); m.add_argument("--data",default="data"); m.set_defaults(func=lambda a: print(json.dumps(SoundMemory(Path(a.data)/"memory").search(a.query),indent=2)) or 0)
    ti=sub.add_parser("taste-import"); ti.add_argument("source"); ti.add_argument("--data",default="data"); ti.add_argument("--exclude-channel",action="append",default=[]); ti.add_argument("--exclude-title",action="append",default=[]); ti.add_argument("--exclude-before"); ti.add_argument("--exclude-after"); ti.set_defaults(func=lambda a: print(json.dumps(TasteStore(Path(a.data)/"taste").import_takeout(a.source,set(a.exclude_channel),set(a.exclude_title),a.exclude_before,a.exclude_after),indent=2)) or 0)
    tr=sub.add_parser("taste-report"); tr.add_argument("--data",default="data"); tr.set_defaults(func=lambda a: print(json.dumps(TasteStore(Path(a.data)/"taste").report(),indent=2)) or 0)
    td=sub.add_parser("taste-delete"); td.add_argument("--data",default="data"); td.set_defaults(func=lambda a: (TasteStore(Path(a.data)/"taste").delete_all() or print("Deleted imported taste events and corrections.")) or 0)
    ld=sub.add_parser("live-demo", help="run against a verified disposable Ableton Live set")
    ld.add_argument("--prompt", default="A tense, nocturnal pulse with glassy pads")
    ld.add_argument("--data", default="data/live-test")
    ld.add_argument("--capture-audio", action="store_true")
    ld.add_argument("--ear", default=os.environ.get("MUSE_EAR_PATH"), help="path to an external ear.py capture tool")
    ld.add_argument("--capture-seconds", type=float, default=4.0)
    ld.add_argument("--audio-out", default="data/live-test/muse-capture.wav")
    ld.add_argument("--expected-live-set", default="data/live-test/MUSE_Disposable Project/MUSE_Disposable.als")
    ld.set_defaults(func=live_demo)
    c=sub.add_parser("create", help="interactive creative session")
    c.add_argument("--data", default="data/session")
    c.add_argument("--live", action="store_true", help="use the verified Ableton bridge")
    c.add_argument("--offline", action="store_true", help="use deterministic interpretation instead of OpenCode")
    c.set_defaults(func=create_session)
    a=sub.add_parser("arrange", help="copy current Session loops into Arrangement timeline")
    a.add_argument("--data", default="data/session")
    a.add_argument("--live", action="store_true")
    a.set_defaults(func=arrangement_command)
    return args_func(p, argv)


def args_func(parser, argv):
    args=parser.parse_args(argv); return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
