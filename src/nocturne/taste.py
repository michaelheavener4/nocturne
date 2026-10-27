from __future__ import annotations

"""Local Google Takeout importer and transparent listening-preference model.

Only metadata is used here. No audio is downloaded and no history is sent to a
model. The report deliberately says "listening metadata suggests" rather than
claiming that a recording's acoustic properties were measured.
"""

from collections import Counter
import csv
from datetime import datetime, timezone
import hashlib, json, re, sqlite3, zipfile
from pathlib import Path


MUSIC_WORDS = re.compile(r"\b(music|official audio|official video|lyrics?|album|ep|single|records?|remix|live session|audio)\b", re.I)
VIDEO_EXTENSIONS = (".mp3", ".wav", ".flac", ".m4a")


def _utc(value: str | None) -> str | None:
    if not value:
        return None
    return value.replace("Z", "+00:00")


def is_probable_music(title: str, channel: str = "", url: str = "") -> tuple[bool, float, str]:
    """Classify metadata conservatively; this is not an audio classifier."""
    text = f"{title} {channel}"
    score = 0.0
    if MUSIC_WORDS.search(text): score += .45
    if "youtube.com/watch" in url or "youtu.be/" in url: score += .15
    if " - " in title or any(title.lower().endswith(x) for x in VIDEO_EXTENSIONS): score += .25
    if re.search(r"\b(song|track|band|singer|producer|dj|artist)\b", text, re.I): score += .2
    probable = score >= .45
    reason = "metadata keyword/format heuristic" if probable else "insufficient music metadata"
    return probable, round(min(score, 1.0), 2), reason


class TasteStore:
    def __init__(self, root: str | Path):
        self.root = Path(root); self.root.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.root / "taste.sqlite3")
        self.db.execute("""CREATE TABLE IF NOT EXISTS listening_events (
            id INTEGER PRIMARY KEY, fingerprint TEXT UNIQUE, title TEXT NOT NULL,
            channel TEXT, url TEXT, watched_at TEXT, source_file TEXT,
            is_music INTEGER, classification_confidence REAL, classification_reason TEXT,
            duration_known INTEGER DEFAULT 0, imported_at TEXT DEFAULT CURRENT_TIMESTAMP)""")
        self.db.execute("CREATE INDEX IF NOT EXISTS idx_events_title ON listening_events(title)")
        self.db.execute("CREATE TABLE IF NOT EXISTS taste_corrections (id INTEGER PRIMARY KEY, target TEXT, label TEXT, value TEXT, note TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP)")
        self.db.commit()

    def _records(self, source: Path):
        if source.suffix.lower() == ".zip":
            with zipfile.ZipFile(source) as z:
                bad = [n for n in z.namelist() if Path(n).is_absolute() or ".." in Path(n).parts]
                if bad: raise ValueError(f"unsafe archive paths: {bad[:3]}")
                candidates = [n for n in z.namelist() if n.lower().endswith(("watch-history.json", "watch-history.jsonl", "watch-history.csv")) or "playlist" in n.lower() or "liked" in n.lower()]
                if not candidates: raise ValueError("Takeout archive has no watch-history.json")
                if sum(z.getinfo(n).file_size for n in candidates) > 500 * 1024 * 1024: raise ValueError("history file exceeds 500 MiB safety limit")
                for name in candidates:
                    raw = z.read(name).decode("utf-8-sig")
                    yield from self._decode(raw, name)
        else:
            if not source.is_file(): raise FileNotFoundError(source)
            if source.suffix.lower() not in {".json", ".jsonl", ".csv"}: raise ValueError("expected Takeout JSON/CSV or zip")
            yield from self._decode(source.read_text(encoding="utf-8-sig"), str(source))

    @staticmethod
    def _decode(raw: str, name: str):
        if name.lower().endswith(".csv"):
            for row in csv.DictReader(raw.splitlines()):
                yield {"title": row.get("title") or row.get("Title") or row.get("video_title"), "titleUrl": row.get("titleUrl") or row.get("url") or row.get("URL"), "time": row.get("time") or row.get("timestamp") or row.get("date"), "subtitles": [{"name": row.get("channel") or row.get("artist") or ""}]}
            return
        if name.lower().endswith(".jsonl"):
            records = [json.loads(line) for line in raw.splitlines() if line.strip()]
        else:
            records = json.loads(raw)
        if isinstance(records, dict):
            records = records.get("items") or records.get("videos") or records.get("entries") or []
        if not isinstance(records, list): raise ValueError("Takeout records must be a JSON array or an items object")
        yield from records

    def import_takeout(self, source: str | Path, exclude_channels: set[str] | None = None, exclude_titles: set[str] | None = None, exclude_before: str | None = None, exclude_after: str | None = None) -> dict:
        source = Path(source); exclude_channels = exclude_channels or set(); exclude_titles = exclude_titles or set()
        imported = skipped = duplicates = 0
        for record in self._records(source):
            if not isinstance(record, dict): skipped += 1; continue
            title = str(record.get("title", "")).strip()
            if title.startswith("Watched "): title = title[8:]
            channel = str(record.get("subtitles", [{}])[0].get("name", "")) if isinstance(record.get("subtitles"), list) and record.get("subtitles") else ""
            url = str(record.get("titleUrl", "")); watched_at = _utc(record.get("time"))
            if not title or channel in exclude_channels or title in exclude_titles: skipped += 1; continue
            if exclude_before and watched_at and watched_at < exclude_before: skipped += 1; continue
            if exclude_after and watched_at and watched_at > exclude_after: skipped += 1; continue
            music, confidence, reason = is_probable_music(title, channel, url)
            fingerprint = hashlib.sha256(json.dumps([title, channel, url, watched_at], ensure_ascii=False).encode()).hexdigest()
            cur = self.db.execute("INSERT OR IGNORE INTO listening_events(fingerprint,title,channel,url,watched_at,source_file,is_music,classification_confidence,classification_reason) VALUES(?,?,?,?,?,?,?,?,?)", (fingerprint,title,channel,url,watched_at,str(source),int(music),confidence,reason))
            if cur.rowcount: imported += 1
            else: duplicates += 1
        self.db.commit()
        return {"source": str(source), "imported": imported, "duplicates": duplicates, "skipped": skipped}

    def add_correction(self, target: str, label: str, value: str, note: str = "") -> None:
        self.db.execute("INSERT INTO taste_corrections(target,label,value,note) VALUES(?,?,?,?)", (target,label,value,note)); self.db.commit()

    def report(self, now: datetime | None = None) -> dict:
        rows = self.db.execute("SELECT title,channel,watched_at,is_music,classification_confidence FROM listening_events ORDER BY watched_at").fetchall()
        music = [r for r in rows if r[3]]; titles = Counter(r[0] for r in music); channels = Counter(r[1] for r in music if r[1])
        days = Counter((r[2] or "")[:10] for r in music)
        repeated = [{"title": t, "plays": n, "evidence": "repeated listening metadata", "confidence": round(min(.55 + .08*n, .9), 2)} for t,n in titles.most_common(10)]
        questions = [
            "Are the tracks you revisit for their vocal melodies, their production texture, or both?",
            "When a repeated track is played in the background, should it count as a strong preference signal?",
            "Do you want NOCTURNE to favor familiar sonic qualities or deliberately contrast them?",
            "Which matters more in your favorite music: groove, harmony, sound design, or arrangement arc?",
            "Are any recurring artists or channels useful only as references, rather than sounds to emulate?",
        ]
        return {"event_count": len(rows), "probable_music_events": len(music), "most_revisited": repeated,
                "frequent_channels": [{"channel":c,"events":n,"evidence":"metadata label frequency"} for c,n in channels.most_common(10)],
                "listening_days": len([d for d in days if d]),
                "high_confidence_preferences": [x for x in repeated if x["confidence"] >= .75],
                "possible_sonic_patterns": [{"attribute":"repetition/returning to known tracks","evidence":"listening metadata only","confidence":.65}] if music else [],
                "uncertain_conclusions":["No BPM, timbre, harmony, dynamics, or spectral balance was measured from history metadata.", "Watch history does not establish completion, duration, or dislike."],
                "five_high_value_questions": questions}

    def delete_all(self) -> None:
        self.db.execute("DELETE FROM listening_events"); self.db.execute("DELETE FROM taste_corrections"); self.db.commit()
