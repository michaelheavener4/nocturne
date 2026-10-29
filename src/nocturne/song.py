"""Full-song request routing and the shared arrangement planning entry point."""

from __future__ import annotations

import re

from .arrangement import ArrangementPlanner
from .models import ArrangementPlan, CreativeBrief

SONG_FORMS = ("edm", "club", "pop", "pop84")

# A create request that names one of these is a song, not an 8-bar groove.
# "build" is left out on purpose: "build a groove" is a verb, not a section.
# "club" is a form name: a create that contains it plans with form="club".
_SONG_REQUEST_RE = re.compile(
    r"\b(?:songs?|tracks?|edm|club|chart\s+pop|pop84|drops?|choruses?|breakdowns?|bridges?|pre-?choruses?|intros?|verses?|outros?)\b",
    re.I,
)
_CLUB_REQUEST_RE = re.compile(r"\bclub\b", re.I)
_CLUB_ROLES = ("intro", "build", "drop", "breakdown", "build", "drop", "outro")


def wants_full_song(text: str) -> bool:
    """True when a create request asks for a song rather than an 8-bar groove.

    The words song, track, edm, and club count, as do section words such as
    drop or chorus. A plain groove request stays on the 8-bar planner.
    """
    return _SONG_REQUEST_RE.search(text) is not None


def requested_form(text: str) -> str | None:
    """Explicit chart-pop/pop84 or club route; otherwise infer edm vs pop."""
    if re.search(r"\b(?:chart\s+pop|pop84)\b", text, re.I):
        return "pop84"
    if _CLUB_REQUEST_RE.search(text):
        return "club"
    return None


def form_used(plan: ArrangementPlan, requested: str | None = None) -> str:
    """Template name that produced this plan: edm, club, pop, or pop84."""
    if requested in SONG_FORMS:
        return requested
    roles = tuple(
        re.sub(r"[\s_]+", "-", str(section.role).strip().lower())
        for section in plan.form
    )
    if "postchorus" in roles:
        return "pop84"
    if roles == _CLUB_ROLES or int(getattr(plan, "bars", 0) or 0) == 96:
        return "club"
    if any(role in {"chorus", "pre-chorus", "bridge"} for role in roles):
        return "pop"
    return "edm"


def plan_song(brief: CreativeBrief, form: str | None = None, groove: str | None = None) -> ArrangementPlan:
    """Plan a full song, inferring form and groove when omitted."""
    return ArrangementPlanner().song(brief, form=form, groove=groove)
