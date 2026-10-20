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
    assert "Due (estimated" in out and "2026-10-28" in out
    assert "READY" in out and "NOT READY" in out and "1 of 2 activities ready" in out
    assert "confirmation page" in out
    assert cli.main(["form", "--week", "nope"]) == 2
