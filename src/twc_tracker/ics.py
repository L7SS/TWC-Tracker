"""Read appointments from an .ics calendar file and write the work-search log back out as one.

Works with the export/import files every calendar app has, locally. Nothing is stored unless you select it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

_MAX_BYTES = 10_000_000
INTERVIEW_WORDS = ("interview", "recruiter", "screen", "phone call", "hiring manager", "technical call")
NETWORK_WORDS = ("job fair", "career fair", "networking", "job club", "workshop", "resume review")


@dataclass
class Appointment:
    title: str
    start: str  # YYYY-MM-DD or YYYY-MM-DDTHH:MM (as written in the file)
    end: str = ""
    location: str = ""
    description: str = ""
    recurring: bool = False
    suggested: str = ""  # interview | networking | ""

    @property
    def hours(self) -> str:
        """Length of the event in hours, only when the file gives a start and end time."""
        if "T" not in self.start or "T" not in self.end:
            return ""
        delta = datetime.fromisoformat(self.end) - datetime.fromisoformat(self.start)
        return f"{delta.total_seconds() / 3600:g}" if delta > timedelta(0) else ""

    def as_dict(self) -> dict:
        return {**self.__dict__, "hours": self.hours}


def _unfold(text: str) -> list[str]:
    return re.sub(r"\r?\n[ \t]", "", text).splitlines()


def _unescape(v: str) -> str:
    return re.sub(r"\\([nN,;\\])", lambda m: "\n" if m.group(1) in "nN" else m.group(1), v)


def _when(value: str) -> str:
    v = value.strip()
    if re.fullmatch(r"\d{8}", v):
        return f"{v[:4]}-{v[4:6]}-{v[6:]}"
    m = re.fullmatch(r"(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})?(Z?)", v)
    if not m:
        return ""
    y, mo, d, h, mi, _s, z = m.groups()
    try:
        t = datetime(int(y), int(mo), int(d), int(h), int(mi), tzinfo=timezone.utc if z else None)
    except ValueError:
        return ""
    if z:
        t = t.astimezone().replace(tzinfo=None)  # shown in the computer's local time
    return t.strftime("%Y-%m-%dT%H:%M")


def parse_ics(text: str) -> list[Appointment]:
    if len(text.encode("utf-8", "ignore")) > _MAX_BYTES:
        raise ValueError("calendar file is too large")
    events: list[Appointment] = []
    cur: dict[str, str] | None = None
    for line in _unfold(text):
        if line.strip().upper() == "BEGIN:VEVENT":
            cur = {}
        elif line.strip().upper() == "END:VEVENT" and cur is not None:
            start = _when(cur.get("DTSTART", ""))
            if start:
                title = _unescape(cur.get("SUMMARY", "(no title)"))[:200]
                low = title.lower()
                suggested = (
                    "interview" if any(w in low for w in INTERVIEW_WORDS)
                    else "networking" if any(w in low for w in NETWORK_WORDS) else ""
                )  # fmt: skip
                events.append(
                    Appointment(
                        title=title,
                        start=start,
                        end=_when(cur.get("DTEND", "")),
                        location=_unescape(cur.get("LOCATION", ""))[:200],
                        description=_unescape(cur.get("DESCRIPTION", ""))[:500],
                        recurring="RRULE" in cur,
                        suggested=suggested,
                    )
                )
            cur = None
        elif cur is not None and ":" in line:
            name, _, value = line.partition(":")
            cur.setdefault(name.split(";")[0].upper(), value)
    return events


def _esc(v: str) -> str:
    return re.sub(r"([,;\\])", r"\\\1", v).replace("\n", "\\n")


def to_ics(items: list[tuple[str, str, str]]) -> str:
    """(YYYY-MM-DD, title, description) tuples to an all-day-event calendar file."""
    out = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//TWC Tracker//work search//EN", "CALSCALE:GREGORIAN"]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    for i, (day, title, desc) in enumerate(items):
        d = date.fromisoformat(day)
        out += [
            "BEGIN:VEVENT",
            f"UID:worksearch-{day}-{i}@twc-tracker.local",
            f"DTSTAMP:{stamp}",
            f"DTSTART;VALUE=DATE:{d:%Y%m%d}",
            f"DTEND;VALUE=DATE:{d + timedelta(days=1):%Y%m%d}",
            f"SUMMARY:{_esc(title)}",
            f"DESCRIPTION:{_esc(desc)}",
            "END:VEVENT",
        ]
    out.append("END:VCALENDAR")
    return "\r\n".join(out) + "\r\n"
