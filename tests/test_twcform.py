from datetime import date

from twc_tracker import cli
from twc_tracker.log import Entry, save_entries, week_bounds
from twc_tracker.states import TEXAS
from twc_tracker.twcform import fields, form_problems, methods, split_phone, week_view

OK = {"date": "2026-10-06", "employer": "Acme", "job_type": "Analyst", "filed_application": "yes", "hired": "no"}


def test_required_fields_match_the_agency_page():
    errs, warns = form_problems(Entry())
    assert len(errs) == 5 and "phone number is strongly preferred" in warns
    assert form_problems(Entry(**OK))[0] == []
    hired = Entry(**{**OK, "hired": "yes"})
    assert form_problems(hired)[0] == ["start date is required if you were hired"]
    assert form_problems(Entry(**{**OK, "hired": "yes", "start_date": "2026-11-02"}))[0] == []


def test_phone_is_split_for_the_three_boxes_and_bad_numbers_warn():
    assert split_phone("(512) 555-0100") == ("512", "555", "0100")
    assert split_phone("1-512-555-0100") == ("512", "555", "0100")
    assert split_phone("555-0100") is None
    assert "phone should be 10 digits with area code" in form_problems(Entry(**OK, phone="555-0100"))[1]


def test_contact_methods_follow_the_pages_order_and_accept_older_values():
    assert methods("internet, In Person") == ["In Person", "Internet"]
    assert methods("online") == ["Internet"] and methods("") == []
    assert "unknown contact method: carrier pigeon" in form_problems(Entry(**OK, contact_method="carrier pigeon"))[1]


def test_week_view_uses_the_agencys_week_and_due_date():
    # the agency's example: claim week Oct 4-10 2026, due Oct 28
    es = [Entry(**OK), Entry(**{**OK, "date": "2026-10-11"}), Entry(date="2026-10-07")]
    v = week_view(es, date(2026, 10, 8), 5, TEXAS)
    assert (v["start"], v["end"], v["due"]) == ("2026-10-04", "2026-10-10", "2026-10-28")
    assert (v["entries"], v["ready"], v["minimum_met"]) == (2, 1, False)
    assert len(v["days"]) == 7 and week_bounds(date(2026, 10, 4))[1] == date(2026, 10, 10)
    assert week_view([], date(2026, 10, 8), None, TEXAS)["minimum_met"] is None


def test_fields_come_out_in_the_pages_order_and_never_invent_values():
    f = fields(Entry(**OK, phone="5125550100"))
    assert [x.label for x in f][:3] == ["Activity Date", "Employer/Agency/Service/Event Name", "Type of Work Sought"]
    assert next(x for x in f if x.label == "Phone Number").value == "(512) 555-0100"
    blank = {x.label: x.value for x in fields(Entry())}
    assert all(v == "" for v in blank.values())


def test_cli_form_prints_the_week_and_does_not_claim_submission(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("TWC_TRACKER_HOME", str(tmp_path))
    save_entries(
        tmp_path / "worksearch_log.csv",
        [Entry(**OK, activity="Applied for job"), Entry(date="2026-10-07", employer="X")],
    )
    assert cli.main(["form", "--week", "2026-10-06", "--required", "5"]) == 0
    out = capsys.readouterr().out
    assert "Claim week: 2026-10-04 to 2026-10-10" in out and "Minimum work searches: 5" in out
    assert "Due (estimated" in out and "Wednesday, October 28, 2026" in out
    assert "READY" in out and "NOT READY" in out and "1 of 2 activities ready" in out
    assert "confirmation page" in out
    assert cli.main(["form", "--week", "nope"]) == 2


def test_portal_text_follows_the_pages_order_and_wording():
    from twc_tracker.twcform import activity_text, portal_lines

    e = Entry(date="2026-10-06", employer="Acme", job_type="Analyst", contact_method="internet, in person",
              phone="(512) 555-0100", ext="12", state="tx", zip="78701", filed_application="yes", hired="yes",
              start_date="2026-11-02")  # fmt: skip
    lines = portal_lines(e)
    assert lines[0] == "Activity Date (choose this day): Tuesday, October 06, 2026"
    assert "Contact Method(s) (tick): In Person, Internet" in lines
    assert "Phone Number (three boxes): 512 | 555 | 0100" in lines and "Ext: 12" in lines
    assert "State (choose): TX" in lines
    assert "Did you file an application or resume with this contact? (choose): Yes" in lines
    assert lines[-1] == "If Yes, start date: Month November | Day 2 | Year 2026"
    assert "READY" in activity_text(e).splitlines()[0]


def test_portal_text_flags_missing_required_fields_instead_of_filling_them():
    from twc_tracker.twcform import portal_lines

    lines = portal_lines(Entry(employer="Acme"))
    assert "Activity Date (choose this day): !! REQUIRED, still blank" in lines
    assert any("Did you file" in x and "REQUIRED" in x for x in lines)
    assert not any(x.startswith(("Fax", "Email", "City")) for x in lines)  # optional blanks are omitted


def test_cli_form_json_and_out_file(tmp_path, monkeypatch, capsys):
    import json

    monkeypatch.setenv("TWC_TRACKER_HOME", str(tmp_path))
    save_entries(tmp_path / "worksearch_log.csv", [Entry(**OK)])
    assert cli.main(["form", "--week", "2026-10-06", "--json", "--required", "1"]) == 0
    d = json.loads(capsys.readouterr().out)
    assert d["minimum_met"] is True and d["activities"][0]["ready"] is True
    assert d["activities"][0]["fields"]["Employer/Agency/Service/Event Name"] == "Acme"
    out = tmp_path / "week.txt"
    assert cli.main(["form", "--week", "2026-10-06", "--out", str(out)]) == 0
    assert "Acme" in out.read_text()


def test_quick_log_presets_only_what_the_kind_states_and_never_hired_or_hours():
    import pytest

    from twc_tracker.quick import quick_entry

    e = quick_entry("apply", " Acme ", "Analyst", today=date(2026, 10, 22))
    assert (e.date, e.employer, e.job_type) == ("2026-10-22", "Acme", "Analyst")
    assert e.contact_method == "Internet" and e.filed_application == "yes"
    assert e.hired == "" and e.hours == "" and e.start_date == "" and e.phone == ""
    assert quick_entry("interview", "X", "Y", "1.5", "2026-10-20").filed_application == ""
    for bad in ({"kind": "bogus"}, {"hours": "abc"}, {"hours": "0"}, {"day": "10/20"}):
        with pytest.raises(ValueError):
            quick_entry(**{"kind": "apply", "employer": "a", "job_type": "b", **bad})


def test_hours_flow_into_the_copy_text_with_daily_and_weekly_totals():
    from twc_tracker.twcform import activity_text, hours_by_day, week_text

    es = [Entry(**OK, hours="1.5"), Entry(**{**OK, "employer": "B"}, hours="0.5"),
          Entry(**{**OK, "date": "2026-10-07", "employer": "C"}), Entry(**{**OK, "employer": "D"}, hours="abc")]  # fmt: skip
    assert hours_by_day(es) == {"2026-10-06": 2.0}  # unparseable or missing hours are never counted or guessed
    assert "Hours spent: 1.5" in activity_text(es[0]) and "Hours spent" not in activity_text(es[2])
    text = week_text(es, date(2026, 10, 6), 5, TEXAS)
    assert "Tuesday, October 06, 2026: 2" in text and "Total this week: 2" in text
    assert "no hours field" in text
    assert "Hours entered" not in week_text([Entry(**OK)], date(2026, 10, 6), 5, TEXAS)


def test_hired_no_only_fills_unanswered_entries_in_that_week():
    from twc_tracker.twcform import mark_hired_no

    es = [
        Entry(**{**OK, "hired": ""}),
        Entry(**{**OK, "hired": "yes"}),
        Entry(**{**OK, "hired": "", "date": "2026-10-12"}),
    ]
    assert mark_hired_no(es, date(2026, 10, 6)) == 1
    assert [e.hired for e in es] == ["no", "yes", ""]


def test_cli_log_is_one_line_and_says_what_is_still_needed(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("TWC_TRACKER_HOME", str(tmp_path))
    assert cli.main(["log", "apply", "Acme", "Analyst", "--hours", "1.5", "--date", "2026-10-06"]) == 0
    out = capsys.readouterr().out
    assert "Logged for 2026-10-06, 1.5 h." in out and "were you hired" in out
    assert cli.main(["log", "apply", "Acme", "Analyst", "--hours", "nope"]) == 2
