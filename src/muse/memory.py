from __future__ import annotations

import hashlib, json, sqlite3
from pathlib import Path
from .models import MemoryItem


class SoundMemory:
    def __init__(self, root: str | Path):
        self.root = Path(root); self.root.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.root / "memory.sqlite3")
        self.db.execute("CREATE TABLE IF NOT EXISTS items (id INTEGER PRIMARY KEY, kind TEXT, label TEXT, description TEXT, path TEXT, sha256 TEXT, metadata TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP)")
        self.db.execute("CREATE TABLE IF NOT EXISTS feedback (id INTEGER PRIMARY KEY, item_id INTEGER, choice TEXT, rating REAL, note TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP)")
        self.db.commit()

    def store(self, item: MemoryItem, source: str | Path | None = None) -> int:
        path = str(source) if source else item.path
        digest = None
        hash_target = source or item.path
        if hash_target and Path(hash_target).is_file():
            digest = hashlib.sha256(Path(hash_target).read_bytes()).hexdigest()
        cur = self.db.execute("INSERT INTO items(kind,label,description,path,sha256,metadata) VALUES(?,?,?,?,?,?)", (item.kind,item.label,item.description,path,digest,json.dumps(item.metadata)))
        self.db.commit(); return int(cur.lastrowid)

    def search(self, query: str) -> list[dict]:
        rows = self.db.execute("SELECT id,kind,label,description,path,sha256,metadata FROM items WHERE label LIKE ? OR description LIKE ? ORDER BY id DESC", (f"%{query}%", f"%{query}%")).fetchall()
        return [dict(zip(("id","kind","label","description","path","sha256","metadata"), r)) for r in rows]

    def add_feedback(self, item_id: int, choice: str, rating: float | None = None, note: str = "") -> None:
        self.db.execute("INSERT INTO feedback(item_id,choice,rating,note) VALUES(?,?,?,?)", (item_id,choice,rating,note)); self.db.commit()

    def preference_store(self):
        from .preferences import PreferenceStore
        return PreferenceStore(self.db)
