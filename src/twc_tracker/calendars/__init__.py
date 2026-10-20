"""Calendar connectors: sign in once, then push your log to a calendar or pull events to review.

A provider is anything with `list_events` and `push`. Google Calendar is the first one; the interface is small on
purpose so CalDAV or Microsoft providers can be added without touching the log, the CLI or the web app.
Connectors are opt-in, local, and never run unless you ask. See docs/CALENDAR.md.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Protocol

from twc_tracker.ics import Appointment
from twc_tracker.log import Entry, claim_week
from twc_tracker.states import TX_IN_PERSON, TX_NETWORK

TAG = "twcTracker"  # marks events this tool wrote, so a pull never reads them back as new activity


@dataclass
class PushResult:
    created: int = 0
    updated: int = 0
    skipped: int = 0  # entries without a valid date are never sent
    errors: list[str] = field(default_factory=list)


class CalendarProvider(Protocol):
    name: str

    def list_events(self, since: date, until: date) -> list[Appointment]: ...

    def push(self, entries: list[Entry]) -> PushResult: ...


def event_for(entry: Entry) -> dict[str, str]:
    """What leaves your computer for one entry: a title, a date, hours and result. Never proof, contacts or notes."""
    return {
        "id": "twc" + entry.id,
        "date": entry.date,
        "summary": f"Work search: {entry.activity}" + (f" - {entry.employer}" if entry.employer else ""),
        "description": f"Hours: {entry.hours or 'not entered'}. Result: {entry.result or 'none'}.",
    }


def sendable(entries: list[Entry]) -> list[Entry]:
    return [e for e in entries if e.id and claim_week(e.date)]


def suggestion_to_entry(a: Appointment, kind: str) -> Entry:
    """A reviewed calendar event as a log entry. Employer and result stay blank for you to fill in."""
    interview = kind == "interview"
    return Entry(
        date=a.start[:10],
        activity="Interviewed" if interview else "Attended networking event",
        category=TX_IN_PERSON if interview else TX_NETWORK,
        contact_method="In Person",
        hours=a.hours,
        notes=["from calendar event: " + a.title] + (["hours = event length"] if a.hours else []),
    )


def get_provider(name: str = "google") -> CalendarProvider:
    if name == "google":
        from twc_tracker.calendars.google import GoogleCalendar

        return GoogleCalendar()
    raise ValueError(f"unknown calendar provider: {name}")
