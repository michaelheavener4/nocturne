from __future__ import annotations

import argparse, hashlib, json, os, subprocess, sys, time
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
from .render import RenderError, render_midi
from .session import CreativeSession
from .song import form_used, plan_song


def _repetition_report(plan) -> dict:
    """Contract report from analysis.repetition_report, with a local fallback.

    Stream A5 owns the canonical function. If this tree is tested before
    that merge, or A5 exports it under a different name, keep the JSON
    field present and note the import that won.
    """
    fn = None
    source = "nocturne.cli._fallback_repetition_report"
    try:
        from .analysis import repetition_report as fn
        source = "nocturne.analysis.repetition_report"
    except ImportError:
        try:
            from . import analysis as analysis_mod
        except ImportError:
            analysis_mod = None
        if analysis_mod is not None:
            fn = getattr(analysis_mod, "repetition_report", None)
            if callable(fn):
                source = "nocturne.analysis.repetition_report"
    if callable(fn):
        result = fn(plan)
        if hasattr(result, "model_dump"):
            result = result.model_dump()
        if isinstance(result, dict):
            return result
        return {
            "identical_cell_share": None,
            "range_semitones": None,
            "stepwise_only": None,
            "repetitive_flag": None,
            "value": result,
            "source": source,
        }
    return _fallback_repetition_report(plan)


def _fallback_repetition_report(plan) -> dict:
    """2-bar melody-cell report matching the Build 5 contract."""
    from collections import Counter

    melody = next((track for track in plan.tracks if track.role == "melody"), None)
    notes = sorted(melody.notes, key=lambda note: (note.start, note.pitch)) if melody else []
    pitches = [note.pitch for note in notes]
    range_semitones = (max(pitches) - min(pitches)) if pitches else 0
    stepwise_only = (
        True
        if len(pitches) < 2
        else all(abs(pitches[i] - pitches[i - 1]) <= 2 for i in range(1, len(pitches)))
    )
    bars = max(1, int(getattr(plan, "bars", 1) or 1))
    n_cells = (bars + 1) // 2
    signatures = []
    for index in range(n_cells):
        start = index * 8.0
        end = start + 8.0
        cell = tuple(
            (round(note.start - start, 6), int(note.pitch), round(note.duration, 6))
            for note in notes
            if start <= note.start < end
        )
        signatures.append(cell)
    if signatures:
        identical_cell_share = max(Counter(signatures).values()) / len(signatures)
        cadential_same = signatures[-1] == signatures[0]
    else:
        identical_cell_share = 0.0
        cadential_same = True
    repetitive_flag = (identical_cell_share > 0.75 and cadential_same) or (
        range_semitones < 5 and stepwise_only
    )
    return {
        "identical_cell_share": round(identical_cell_share, 4),
        "range_semitones": int(range_semitones),
        "stepwise_only": bool(stepwise_only),
        "repetitive_flag": bool(repetitive_flag),
    }


def demo(args) -> int:
    root=Path(args.data)
    taste_prior = TasteStore(root / "taste").report() if (root / "taste" / "taste.sqlite3").exists() else {}
    brief=IntentInterpreter().interpret(args.prompt, "REFINE" if args.feedback else "CREATE", taste_prior=taste_prior)
    if args.feedback: brief.intent += f" [feedback: {args.feedback}]"
    plan=ArrangementPlanner().plan(brief); adapter=AbletonBridgeAdapter() if args.live else MockDAW(root/"mock_daw")
    inspection=adapter.inspect(); execution=adapter.create_arrangement(plan)
    midi=write_midi(plan, root/"projects"/"nocturne_sketch.mid"); report=analyze_arrangement(plan)
    repetition=_repetition_report(plan)
    root.mkdir(parents=True, exist_ok=True); (root/"projects"/"nocturne_sketch.json").write_text(json.dumps({"brief":brief.model_dump(),"plan":plan.model_dump(),"inspection":inspection,"execution":execution,"analysis":report.model_dump(),"repetition_report":repetition}, indent=2))
    item_id=SoundMemory(root/"memory").store(MemoryItem(kind="arrangement",label="NOCTURNE eight-bar sketch",description=brief.intent, path=str(midi),metadata={"tempo":plan.tempo,"key":plan.key}))
    payload={"question":brief.proposed_questions[0] if brief.proposed_questions else None,"assumptions":brief.assumptions,"execution":execution,"analysis":report.metrics,"repetition_report":repetition,"memory_id":item_id,"midi":str(midi)}
    if args.render:
        try:
            rendered=render_midi(midi)
        except RenderError as exc:
            print(exc, file=sys.stderr); return 1
        payload["wav"]=str(rendered.wav)
    print(json.dumps(payload, indent=2)); return 0


def render_command(args) -> int:
    try:
        rendered=render_midi(args.midi, args.out, args.soundfont)
    except RenderError as exc:
        print(exc, file=sys.stderr); return 1
    print(json.dumps({"wav":str(rendered.wav),"soundfont":str(rendered.soundfont),"duration_seconds":round(rendered.duration_seconds, 3),"size_bytes":rendered.size_bytes}, indent=2)); return 0


def song_command(args) -> int:
    """Write song.mid and song.json. --render also writes song.wav.

    The WAV is rendered at the plan tempo. A 44-bar song at 92 bpm is about
    115 seconds. A missing SoundFont or fluidsynth exits nonzero with the
    same message nocturne render prints.
    """
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    brief = IntentInterpreter().interpret(args.prompt)
    requested = getattr(args, "form", None)
    plan = plan_song(brief, form=requested)
    midi = write_midi(plan, out / "song.mid")
    plan_path = out / "song.json"
    dumped = plan.model_dump()
    dumped["repetition_report"] = _repetition_report(plan)
    plan_path.write_text(json.dumps(dumped, indent=2) + "\n")
    payload = {
        "midi": str(midi),
        "plan": str(plan_path),
        "md5": hashlib.md5(midi.read_bytes()).hexdigest(),
        "bars": plan.bars,
        "tempo": plan.tempo,
        "key": plan.key,
        "form": form_used(plan, requested),
        "progression_name": dumped.get("progression_name"),
        "repetition_report": dumped["repetition_report"],
    }
    sections = dumped.get("form") or []
    if isinstance(sections, list) and sections and isinstance(sections[0], dict):
        payload["sections"] = [section["name"] for section in sections]
    if args.render:
        try:
            rendered = render_midi(midi, out / "song.wav", args.soundfont, tempo_bpm=plan.tempo)
        except RenderError as exc:
            print(exc, file=sys.stderr)
            return 1
        payload["wav"] = str(rendered.wav)
        payload["soundfont"] = str(rendered.soundfont)
        payload["duration_seconds"] = round(rendered.duration_seconds, 3)
        payload["size_bytes"] = rendered.size_bytes
    print(json.dumps(payload, indent=2))
    return 0


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
    report = {"workflow": "real-ableton-nocturne-disposable", "started_at": time.time()}
    report["before"] = adapter.inspect()
    execution = adapter.create_arrangement(plan)
    report["creation"] = execution
    indices = [item["index"] for item in execution["created_tracks"]]
    report["playback"] = adapter.fire_and_start(indices)
    audio_out = Path(args.audio_out)
    if args.capture_audio:
        ear = Path(args.ear) if args.ear else None
        if ear is None or not ear.exists():
            report["audio_capture"] = {"error": "ear tool not configured: pass --ear PATH or set NOCTURNE_EAR_PATH"}
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
    print("NOCTURNE interactive session. Type 'exit' to finish.")
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


def scripted_session(args) -> int:
    session = CreativeSession(args.data, live=args.live, use_model=not args.offline)
    status = 0
    for text in args.say:
        result = session.handle(text)
        print(json.dumps(result, default=str))
        if result.get("status") in {"error", "unsupported"}:
            status = 1
    return status


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
    p=argparse.ArgumentParser(prog="nocturne"); sub=p.add_subparsers(dest="command",required=True)
    d=sub.add_parser("demo"); d.add_argument("--prompt",required=True); d.add_argument("--feedback"); d.add_argument("--live",action="store_true"); d.add_argument("--render",action="store_true",help="after writing MIDI, render a sibling WAV with fluidsynth"); d.add_argument("--data",default="data"); d.set_defaults(func=demo)
    r=sub.add_parser("render", help="render a MIDI file to WAV with fluidsynth")
    r.add_argument("midi"); r.add_argument("--out", help="WAV path (default: sibling .wav)"); r.add_argument("--soundfont", help="SoundFont .sf2 (else $NOCTURNE_SOUNDFONT, ~/.local/share/nocturne/soundfonts/*.sf2, then /usr/share/soundfonts/FluidR3_GM.sf2)"); r.set_defaults(func=render_command)
    s=sub.add_parser("song", help="write a full song (edm 44 bars, club 96, pop 56) and optionally render it")
    s.add_argument("--prompt", required=True)
    s.add_argument("--form", choices=("edm", "club", "pop"), default=None, help="form template; default infers edm vs pop from the prompt")
    s.add_argument("--out", default="data/song", help="directory for song.mid, song.json, and song.wav")
    s.add_argument("--render", action="store_true", help="render song.wav with fluidsynth at the plan tempo")
    s.add_argument("--soundfont", help="SoundFont .sf2 (else $NOCTURNE_SOUNDFONT, ~/.local/share/nocturne/soundfonts/*.sf2, then /usr/share/soundfonts/FluidR3_GM.sf2)")
    s.set_defaults(func=song_command)
    h=sub.add_parser("transcribe-hum"); h.add_argument("wav"); h.add_argument("--output",default="data/hums/melody.mid"); h.set_defaults(func=hum)
    m=sub.add_parser("memory-search"); m.add_argument("query"); m.add_argument("--data",default="data"); m.set_defaults(func=lambda a: print(json.dumps(SoundMemory(Path(a.data)/"memory").search(a.query),indent=2)) or 0)
    ti=sub.add_parser("taste-import"); ti.add_argument("source"); ti.add_argument("--data",default="data"); ti.add_argument("--exclude-channel",action="append",default=[]); ti.add_argument("--exclude-title",action="append",default=[]); ti.add_argument("--exclude-before"); ti.add_argument("--exclude-after"); ti.set_defaults(func=lambda a: print(json.dumps(TasteStore(Path(a.data)/"taste").import_takeout(a.source,set(a.exclude_channel),set(a.exclude_title),a.exclude_before,a.exclude_after),indent=2)) or 0)
    tr=sub.add_parser("taste-report"); tr.add_argument("--data",default="data"); tr.set_defaults(func=lambda a: print(json.dumps(TasteStore(Path(a.data)/"taste").report(),indent=2)) or 0)
    td=sub.add_parser("taste-delete"); td.add_argument("--data",default="data"); td.set_defaults(func=lambda a: (TasteStore(Path(a.data)/"taste").delete_all() or print("Deleted imported taste events and corrections.")) or 0)
    ld=sub.add_parser("live-demo", help="run against a verified disposable Ableton Live set")
    ld.add_argument("--prompt", default="A tense, nocturnal pulse with glassy pads")
    ld.add_argument("--data", default="data/live-test")
    ld.add_argument("--capture-audio", action="store_true")
    ld.add_argument("--ear", default=os.environ.get("NOCTURNE_EAR_PATH"), help="path to an external ear.py capture tool")
    ld.add_argument("--capture-seconds", type=float, default=4.0)
    ld.add_argument("--audio-out", default="data/live-test/nocturne-capture.wav")
    ld.add_argument("--expected-live-set", default="data/live-test/NOCTURNE_Disposable Project/NOCTURNE_Disposable.als")
    ld.set_defaults(func=live_demo)
    c=sub.add_parser("create", help="interactive creative session")
    c.add_argument("--data", default="data/session")
    c.add_argument("--live", action="store_true", help="use the verified Ableton bridge")
    c.add_argument("--offline", action="store_true", help="use deterministic interpretation instead of OpenCode")
    c.set_defaults(func=create_session)
    sc=sub.add_parser("session", help="run scripted session turns")
    sc.add_argument("--data", default="data/session")
    sc.add_argument("--say", action="append", required=True)
    sc.add_argument("--offline", action="store_true")
    sc.add_argument("--live", action="store_true")
    sc.set_defaults(func=scripted_session)
    a=sub.add_parser("arrange", help="copy current Session loops into Arrangement timeline")
    a.add_argument("--data", default="data/session")
    a.add_argument("--live", action="store_true")
    a.set_defaults(func=arrangement_command)
    return args_func(p, argv)


def args_func(parser, argv):
    args=parser.parse_args(argv); return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
