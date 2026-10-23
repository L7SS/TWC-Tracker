"""Quick logging: one line per activity, with the kind of activity filling in what that kind always means.

Only facts that the kind itself states are preset (what counts as the activity, how it was done, whether an
application was filed). Hired, start date, contact details and result stay blank for you. The date is today unless you
type another, and it is shown to you before it is saved. Hours are only what you give (or what your own timer measured).
"""

from __future__ import annotations

from datetime import date

from twc_tracker.log import Entry, parse_hours
from twc_tracker.states import TX_APPLY_ONLINE, TX_IN_PERSON, TX_NETWORK, TX_RESEARCH

# Texas category names for now; make this state-aware when a second state is added (docs/ADDING_A_STATE.md).
KINDS: dict[str, dict[str, str]] = {
    "apply": {
        "activity": "Applied for job",
        "category": TX_APPLY_ONLINE,
        "contact_method": "Internet",
        "filed_application": "yes",
        "label": "Applied for a job online",
    },  # fmt: skip
    "interview": {"activity": "Interviewed", "category": TX_IN_PERSON, "label": "Interview or employer visit"},
    "networking": {
        "activity": "Attended networking event",
        "category": TX_NETWORK,
        "label": "Job club, job fair or workshop",
    },  # fmt: skip
    "research": {
        "activity": "Researched job openings online",
        "category": TX_RESEARCH,
        "contact_method": "Internet",
        "label": "Searched or researched jobs online",
    },  # fmt: skip
}


def quick_entry(
    kind: str,
    employer: str,
    job_type: str,
    hours: str = "",
    day: str = "",
    today: date | None = None,
    proof: str = "",
) -> Entry:
    if kind not in KINDS:
        raise ValueError(f"kind must be one of {sorted(KINDS)}")
    day = day or (today or date.today()).isoformat()
    try:
        date.fromisoformat(day)
    except ValueError as e:
        raise ValueError("date must be YYYY-MM-DD") from e
    if hours and parse_hours(hours) is None:
        raise ValueError("hours must be a number above 0, like 1.5")
    k = {x: v for x, v in KINDS[kind].items() if x != "label"}
    return Entry(
        date=day, employer=employer.strip(), job_type=job_type.strip(), hours=hours.strip(), proof=proof.strip(), **k
    )
