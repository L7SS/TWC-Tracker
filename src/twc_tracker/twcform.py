"""The agency's online "Add Work Search Activity" page, mirrored field by field so you can copy each entry across.

This never logs in to or submits anything for you. The agency's page is the authority: if it asks for something
different from what is mirrored here, follow the page.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, timedelta

from twc_tracker.log import Entry, week_bounds
from twc_tracker.states import StateConfig

CONTACT_METHODS = ("In Person", "Mail", "Phone", "Fax", "Email", "Internet")
_LEGACY = {"online": "Internet", "in person": "In Person", "person": "In Person", "e-mail": "Email"}


def methods(text: str) -> list[str]:
    """The checked contact methods, in the page's order. Accepts older values like 'online'."""
    parts = {p.strip().lower() for p in re.split(r"[;,|]", text or "") if p.strip()}
    chosen = {_LEGACY.get(p, p).lower() for p in parts}
    return [m for m in CONTACT_METHODS if m.lower() in chosen]


def unknown_methods(text: str) -> list[str]:
    known = {m.lower() for m in CONTACT_METHODS} | set(_LEGACY)
    return [p.strip() for p in re.split(r"[;,|]", text or "") if p.strip() and p.strip().lower() not in known]


def split_phone(text: str) -> tuple[str, str, str] | None:
    """(area, prefix, line) for the page's three phone boxes, or None if it is not a 10-digit US number."""
    digits = re.sub(r"\D", "", text or "")
    if len(digits) == 11 and digits[0] == "1":
        digits = digits[1:]
    return (digits[:3], digits[3:6], digits[6:]) if len(digits) == 10 else None


@dataclass
class Field:
    label: str
    value: str
    required: bool = False


def form_problems(e: Entry) -> tuple[list[str], list[str]]:
    """(blocking, warnings) against the page's own rules. Blocking means the page would not accept the entry."""
    errors, warns = [], []
    if not e.date:
        errors.append("activity date: pick a day in the claim week")
    if not e.employer:
        errors.append("employer/agency/service/event name is required")
    if not e.job_type:
        errors.append("type of work sought is required")
    if e.filed_application not in {"yes", "no"}:
        errors.append("answer: did you file an application or resume with this contact?")
    if e.hired not in {"yes", "no"}:
        errors.append("answer: were you hired as a result of this activity?")
    if e.hired == "yes":
        try:
            date.fromisoformat(e.start_date)
        except ValueError:
            errors.append("start date is required if you were hired")
    if e.phone and split_phone(e.phone) is None:
        warns.append("phone should be 10 digits with area code")
    if not e.phone:
        warns.append("phone number is strongly preferred")
    if bad := unknown_methods(e.contact_method):
        warns.append(f"unknown contact method: {', '.join(bad)}")
    return errors, warns


def fields(e: Entry) -> list[Field]:
    """The page's fields in the page's order, with your values."""
    ph = split_phone(e.phone)
    fx = split_phone(e.fax)
    return [
        Field("Activity Date", e.date, True),
        Field("Employer/Agency/Service/Event Name", e.employer, True),
        Field("Type of Work Sought", e.job_type, True),
        Field("Contact Method(s)", ", ".join(methods(e.contact_method))),
        Field("Person Contacted", e.person_contacted),
        Field("Phone Number", f"({ph[0]}) {ph[1]}-{ph[2]}" if ph else e.phone),
        Field("Ext", e.ext),
        Field("Fax Number", f"({fx[0]}) {fx[1]}-{fx[2]}" if fx else e.fax),
        Field("Email Address", e.email),
        Field("Web Site Address", e.website),
        Field("Address", e.address),
        Field("Address (line 2)", e.address2),
        Field("City", e.city),
        Field("State", e.state),
        Field("ZIP Code", e.zip),
        Field("Did you file an application or resume with this contact?", e.filed_application.capitalize(), True),
        Field("Were you hired as a result of this activity?", e.hired.capitalize(), True),
        Field("If yes, what is your start date?", e.start_date),
    ]


def week_for(day: date) -> tuple[date, date]:
    return week_bounds(day)


def due_date(week_end: date, cfg: StateConfig) -> date | None:
    return week_end + timedelta(days=cfg.due_days) if cfg.due_days is not None else None


def week_view(entries: list[Entry], day: date, minimum: int | None, cfg: StateConfig) -> dict:
    """One claim week the way the page frames it: the week, the minimum, the due date, and your entries."""
    start, end = week_bounds(day)
    mine = [e for e in entries if e.date and start.isoformat() <= e.date <= end.isoformat()]
    ok = [e for e in mine if not form_problems(e)[0]]
    due = due_date(end, cfg)
    return {
        "start": start.isoformat(),
        "end": end.isoformat(),
        "days": [(start + timedelta(days=i)).isoformat() for i in range(7)],
        "minimum": minimum,
        "due": due.isoformat() if due else "",
        "entries": len(mine),
        "ready": len(ok),
        "minimum_met": None if minimum is None else len(ok) >= minimum,
    }
