"""Full-song routing for create requests (Build 5).

The song planner itself is ArrangementPlanner.song(brief, form=None):
form templates (edm 44, club 96, pop 56), progression harmony, developing
melody, transitions. This module only decides whether a create
request is asking for a full song, which form it named, and delegates
planning to that planner, so `nocturne song` and a song-shaped session
create share one definition of "song request" and one planning entry
point.

History: Stream C4 originally shipped a fallback planner here behind
an adapter that looked for a planner method named plan_song. Stream
A4 named its method song, the adapter never matched, and the merge
briefly carried two planners and two CLI registrations. Coordinator
fix: the fallback planner is deleted; this module delegates. Build 5
pins the form keyword on that same method; until Stream A5 lands the
keyword, plan_song omits it so the 8-bar suite stays green.
"""

from __future__ import annotations

import inspect
import re

from .arrangement import ArrangementPlanner
from .models import ArrangementPlan, CreativeBrief

SONG_FORMS = ("edm", "club", "pop")

# A create request that names one of these is a song, not an 8-bar groove.
# "build" is left out on purpose: "build a groove" is a verb, not a section.
# "club" is a form name: a create that contains it plans with form="club".
_SONG_REQUEST_RE = re.compile(
    r"\b(?:songs?|tracks?|edm|club|drops?|choruses?|breakdowns?|bridges?|pre-?choruses?|intros?|verses?|outros?)\b",
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
    """Form implied by the artist's words. Only 'club' is an explicit route.

    Other song requests leave form=None so the planner infers edm vs pop,
    matching Build 4 behavior.
    """
    if _CLUB_REQUEST_RE.search(text):
        return "club"
    return None


def form_used(plan: ArrangementPlan, requested: str | None = None) -> str:
    """Template name that produced this plan: edm, club, or pop."""
    if requested in SONG_FORMS:
        return requested
    roles = tuple(
        re.sub(r"[\s_]+", "-", str(section.role).strip().lower())
        for section in plan.form
    )
    if roles == _CLUB_ROLES or int(getattr(plan, "bars", 0) or 0) == 96:
        return "club"
    if any(role in {"chorus", "pre-chorus", "bridge"} for role in roles):
        return "pop"
    return "edm"


def plan_song(brief: CreativeBrief, form: str | None = None) -> ArrangementPlan:
    """Plan a full song from the brief via the arrangement planner.

    form is one of {"edm", "club", "pop", None}. None lets the planner
    infer the template from the brief. The pinned entry is
    ArrangementPlanner.song(brief, form=None).
    """
    planner = ArrangementPlanner()
    method = planner.song
    try:
        params = inspect.signature(method).parameters
    except (TypeError, ValueError):
        params = {}
    if "form" in params or any(
        parameter.kind is inspect.Parameter.VAR_KEYWORD for parameter in params.values()
    ):
        return method(brief, form=form)
    return method(brief)
