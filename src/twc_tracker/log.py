"""The work-search log. Every fact is typed by the user; nothing here fills in a date, an hour or a contact."""

from __future__ import annotations

import csv
from dataclasses import asdict, dataclass, field, fields
from datetime import date, timedelta
from pathlib import Path

from twc_tracker.states import StateConfig

ENTRY_COLS = [
    "date", "activity", "category", "job_type", "employer", "address", "phone", "person_contacted", "email",
    "contact_method", "result", "hours", "proof",
]  # fmt: skip


@dataclass
class Entry:
    activity: str = ""
    date: str = ""  # YYYY-MM-DD, left blank unless the user knows it
    category: str = ""  # must be one of the state's accepted activities
    job_type: str = ""
    employer: str = ""
    address: str = ""
    phone: str = ""
    person_contacted: str = ""
    email: str = ""
    contact_method: str = ""  # mail, email, fax, phone, online, in person
    result: str = ""
    hours: str = ""  # the user's own time in hours, e.g. "1.5". Never filled in by the tool.
    proof: str = ""
    notes: list[str] = field(default_factory=list)

    def problems(self, cfg: StateConfig, today: date | None = None) -> list[str]:
        """What stops this entry being ready to sign. Empty means complete."""
        out = []
        if cfg.accepted_activities and self.category not in cfg.accepted_activities:
            out.append("pick an accepted activity from the state's list")
        if not self.date:
            out.append("date missing")
        else:
            try:
                if date.fromisoformat(self.date) > (today or date.today()):
                    out.append("date is in the future")
            except ValueError:
                out.append("date must be YYYY-MM-DD")
        if not self.employer and "online" not in self.activity.lower():
            out.append("employer or agency name missing")
        if not self.result:
            out.append("result missing")
        elif self.result not in cfg.result_choices:
            out.append(f"result must be one of {list(cfg.result_choices)}")
        if parse_hours(self.hours) is None:
            out.append("hours missing: enter the time you actually spent")
        return out

    def as_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> Entry:
        keep = {f.name for f in fields(cls)} - {"notes"}
        notes = d.get("notes") or []
        if isinstance(notes, str):
            notes = [n for n in notes.split(" | ") if n]
        return cls(**{k: str(v or "") for k, v in d.items() if k in keep}, notes=[str(n) for n in notes])


def parse_hours(text: str) -> float | None:
    try:
        v = float(text)
    except (TypeError, ValueError):
        return None
    return v if v > 0 and v == v and v != float("inf") else None  # noqa: PLR0124 (NaN check)


def claim_week(day: str) -> str:
    """Claim weeks run Sunday to Saturday. Returns 'YYYY-MM-DD to YYYY-MM-DD', or '' for an unknown date."""
    try:
        d = date.fromisoformat(day)
    except ValueError:
        return ""
    start = d - timedelta(days=(d.weekday() + 1) % 7)
    return f"{start} to {start + timedelta(days=6)}"


def weekly_summary(entries: list[Entry], required: int | None = None) -> list[str]:
    """One line per claim week: activities counted, hours entered, and whether the required number is met.

    Only hours the user typed are added up; undated entries are listed apart."""
    weeks: dict[str, list[Entry]] = {}
    for e in entries:
        weeks.setdefault(claim_week(e.date) or "date unknown", []).append(e)
    lines = []
    for wk in sorted(weeks, key=lambda w: (w == "date unknown", w)):
        es = weeks[wk]
        hrs = sum(h for e in es if (h := parse_hours(e.hours)) is not None)
        missing = sum(1 for e in es if parse_hours(e.hours) is None)
        line = f"{wk}: {len(es)} activities, {hrs:g} hours entered"
        if missing:
            line += f", {missing} without hours"
        if required is not None and wk != "date unknown":
            line += f" (required {required}: {'met' if len(es) >= required else 'NOT met'})"
        lines.append(line)
    return lines


def load_entries(path: Path) -> list[Entry]:
    """The user's own log file. A missing file is an empty log."""
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as fh:
        return [Entry.from_dict(row) for row in csv.DictReader(fh)]


def save_entries(path: Path, entries: list[Entry]) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=[*ENTRY_COLS, "notes"])
        w.writeheader()
        for e in entries:
            d = e.as_dict()
            d["notes"] = " | ".join(e.notes)
            w.writerow({k: _csv_safe(d.get(k, "")) for k in w.fieldnames})


def _csv_safe(value: str) -> str:
    """Spreadsheet programs run cells that start with = + - @ as formulas; neutralise them."""
    v = str(value).replace("\n", " ").strip()
    return "'" + v if v and v[0] in "=+@" or (v[:1] == "-" and not _is_number(v)) else v


def _is_number(v: str) -> bool:
    try:
        float(v)
    except ValueError:
        return False
    return True
