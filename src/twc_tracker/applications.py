"""Application tracker: a plain CSV of where you applied. Turn it into log entries when you are ready to review them."""

from __future__ import annotations

import csv
from datetime import date
from pathlib import Path

from twc_tracker.log import Entry
from twc_tracker.states import TX_APPLY_ONLINE, TX_IN_PERSON

FIELDS = ["date", "company", "role", "channel", "outcome", "notes"]
OUTCOMES = ("prepared", "applied", "no_response", "rejected", "recruiter_screen", "interview", "offer")

# What the user recorded, in the agency's result words. Nothing is guessed beyond this table.
_RESULT = {
    "applied": "Application filed",
    "no_response": "No reply",
    "rejected": "Not hired",
    "recruiter_screen": "Interviewed",
    "interview": "Interviewed",
    "offer": "Other",
}


def _safe(value: str) -> str:
    """Spreadsheet programs run cells that start with = + - @ as formulas; neutralise them."""
    v = str(value).replace("\n", " ").strip()
    return "'" + v if v and v[0] in "=+-@" else v


def add(path: Path, *, company: str, role: str, channel: str = "online", outcome: str = "applied",
        notes: str = "", when: str = "") -> None:  # fmt: skip
    if outcome not in OUTCOMES:
        raise ValueError(f"outcome must be one of {OUTCOMES}")
    if when:
        date.fromisoformat(when)  # raises ValueError on a bad date
    new = not path.exists()
    with path.open("a", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        if new:
            w.writeheader()
        w.writerow({"date": when or date.today().isoformat(), "company": _safe(company), "role": _safe(role),
                    "channel": _safe(channel), "outcome": outcome, "notes": _safe(notes)})  # fmt: skip


def read(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def to_entries(rows: list[dict]) -> list[Entry]:
    """Log entries from tracker rows. A date, hours or contact the tracker does not hold stays blank."""
    entries = []
    for row in rows:
        outcome = row.get("outcome", "")
        if outcome == "prepared":
            continue  # prepared is not submitted: it is not a work-search contact yet
        met_employer = outcome in {"recruiter_screen", "interview"} or row.get("channel") == "referral"
        entries.append(
            Entry(
                date=row.get("date", ""),
                activity="Interviewed" if outcome in {"recruiter_screen", "interview"} else "Applied for job",
                category=TX_IN_PERSON if met_employer else TX_APPLY_ONLINE,
                job_type=row.get("role", ""),
                employer=row.get("company", ""),
                contact_method="" if met_employer else "online",
                result=_RESULT.get(outcome, ""),
                notes=[row["notes"].lstrip("'")] if row.get("notes") else [],
            )
        )
    return entries
