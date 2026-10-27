from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, Field, ConfigDict


class Note(BaseModel):
    pitch: int = Field(ge=0, le=127)
    start: float = Field(ge=0)
    duration: float = Field(gt=0)
    velocity: int = Field(ge=1, le=127)
    confidence: float | None = Field(default=None, ge=0, le=1)


class CreativeBrief(BaseModel):
    model_config = ConfigDict(extra="forbid")
    intent: str
    emotional_dimensions: dict[str, float] = Field(default_factory=dict)
    musical_constraints: dict[str, str | float | int] = Field(default_factory=dict)
    sonic_references: list[str] = Field(default_factory=list)
    arrangement_goals: list[str] = Field(default_factory=list)
    uncertainty: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    proposed_questions: list[str] = Field(default_factory=list, max_length=1)
    proposed_execution_plan: list[str] = Field(default_factory=list)
    taste_prior: dict = Field(default_factory=dict)


class TrackPlan(BaseModel):
    name: str
    role: Literal["drums", "bass", "harmony", "melody"]
    instrument: str
    notes: list[Note]
    approved: bool = False


class SongSection(BaseModel):
    name: str
    role: str
    start_bar: int = Field(ge=0)
    bars: int = Field(ge=1)
    energy: float = Field(ge=0, le=1)


class ArrangementPlan(BaseModel):
    title: str
    tempo: float = Field(ge=20, le=300)
    bars: int = Field(default=8, ge=1, le=64)
    key: str
    tracks: list[TrackPlan]
    rationale: list[str] = Field(default_factory=list)
    form: list[SongSection] = Field(default_factory=list)


class EvidenceClaim(BaseModel):
    kind: Literal["MEASURED", "RESEARCH_SUPPORTED", "HYPOTHESIS"]
    statement: str
    value: float | str | None = None
    uncertainty: str | None = None
    source: str | None = None


class AnalysisReport(BaseModel):
    claims: list[EvidenceClaim]
    metrics: dict[str, float | int | str]


class HummedNote(BaseModel):
    note: Note
    frequency_hz: float
    confidence: float = Field(ge=0, le=1)
    needs_review: bool


class MemoryItem(BaseModel):
    kind: Literal["arrangement", "preset", "audio", "midi", "decision"]
    label: str
    description: str = ""
    path: str | None = None
    sha256: str | None = None
    metadata: dict = Field(default_factory=dict)
