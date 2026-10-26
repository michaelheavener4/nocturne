from __future__ import annotations

from dataclasses import dataclass
import sqlite3


@dataclass(frozen=True)
class PairwiseChoice:
    item_a: int
    item_b: int
    winner: int
    question: str


class PreferenceStore:
    """Descriptive pairwise preference memory; intentionally not a trained model."""

    def __init__(self, db: sqlite3.Connection):
        self.db = db
        self.db.execute("CREATE TABLE IF NOT EXISTS pairwise_preferences (id INTEGER PRIMARY KEY, item_a INTEGER, item_b INTEGER, winner INTEGER, question TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP)")
        self.db.commit()

    def record(self, choice: PairwiseChoice) -> None:
        if choice.winner not in (choice.item_a, choice.item_b):
            raise ValueError("winner must be item_a or item_b")
        self.db.execute("INSERT INTO pairwise_preferences(item_a,item_b,winner,question) VALUES(?,?,?,?)", (choice.item_a, choice.item_b, choice.winner, choice.question))
        self.db.commit()

    def summary(self) -> dict[int, dict[str, int]]:
        rows = self.db.execute("SELECT winner, COUNT(*) FROM pairwise_preferences GROUP BY winner").fetchall()
        return {int(item): {"wins": int(wins)} for item, wins in rows}
