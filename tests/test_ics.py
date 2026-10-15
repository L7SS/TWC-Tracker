from twc_tracker.ics import parse_ics, to_ics

ICS = (
    "BEGIN:VCALENDAR\r\nBEGIN:VEVENT\r\nSUMMARY:Recruiter screen\\, Acme\r\n"
    "DTSTART:20261014T150000Z\r\nDTEND:20261014T153000Z\r\nDESCRIPTION:Call with\r\n  Sam\\nbring resume\r\n"
    "END:VEVENT\r\nBEGIN:VEVENT\r\nSUMMARY:Dentist\r\nDTSTART;VALUE=DATE:20261015\r\nEND:VEVENT\r\n"
    "BEGIN:VEVENT\r\nSUMMARY:Weekly job club\r\nDTSTART:20261016T100000\r\nDTEND:20261016T110000\r\nRRULE:FREQ=WEEKLY\r\n"
    "END:VEVENT\r\nEND:VCALENDAR\r\n"
)


def test_parse_suggests_only_job_search_events_and_computes_hours():
    ev = {e.title: e for e in parse_ics(ICS)}
    assert ev["Recruiter screen, Acme"].suggested == "interview"
    assert ev["Recruiter screen, Acme"].hours == "0.5"
    assert "Call with Sam\nbring resume" in ev["Recruiter screen, Acme"].description
    assert ev["Dentist"].suggested == "" and ev["Dentist"].hours == ""  # personal events are never pre-selected
    assert ev["Weekly job club"].suggested == "networking" and ev["Weekly job club"].recurring


def test_export_round_trips_through_the_parser():
    out = to_ics([("2026-10-14", "Applied: Acme, Analyst", "Hours: 1; proof kept")])
    assert out.endswith("\r\n") and "DTSTART;VALUE=DATE:20261014" in out
    back = parse_ics(out)
    assert back[0].title == "Applied: Acme, Analyst" and back[0].start == "2026-10-14"


def test_bad_dates_are_skipped_not_fatal():
    assert parse_ics("BEGIN:VEVENT\r\nSUMMARY:x\r\nDTSTART:20261399T250000\r\nEND:VEVENT\r\n") == []
