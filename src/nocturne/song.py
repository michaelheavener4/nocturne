"""Full-song routing for create requests (Build 4).

The song planner itself is ArrangementPlanner.song (Stream A4):
form templates (edm 44 bars, pop 56), progression harmony, developing
melody, transitions. This module only decides whether a create
request is asking for a full song, and delegates planning to that
planner, so `nocturne song` and a song-shaped session create share one
definition of "song request" and one planning entry point.

History: Stream C4 originally shipped a fallback planner here behind
an adapter that looked for a planner method named plan_song. Stream
A4 named its method song, the adapter never matched, and the merge
briefly carried two planners and two CLI registrations. Coordinator
fix: the fallback planner is deleted; this module delegates.
"""

from __future__ import annotations

import re

from .arrangement import ArrangementPlanner
from .models import ArrangementPlan, CreativeBrief


# A create request that names one of these is a song, not an 8-bar groove.
# "build" is left out on purpose: "build a groove" is a verb, not a section.
_SONG_REQUEST_RE = re.compile(
    r"\b(?:songs?|tracks?|edm|drops?|choruses?|breakdowns?|bridges?|pre-?choruses?|intros?|verses?|outros?)\b",
    re.I,
)


def wants_full_song(text: str) -> bool:
    """True when a create request asks for a song rather than an 8-bar groove.

    The words song, track, and edm count, as do section words such as drop
    or chorus. A plain groove request stays on the 8-bar planner.
    """
    return _SONG_REQUEST_RE.search(text) is not None


def plan_song(brief: CreativeBrief) -> ArrangementPlan:
    """Plan a full song from the brief via the arrangement planner."""
    return ArrangementPlanner().song(brief)
