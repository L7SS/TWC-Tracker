from datetime import date

from twc_tracker.log import Entry, claim_week, load_entries, save_entries, weekly_summary
from twc_tracker.states import TEXAS, TX_IN_PERSON

TODAY = date(2026, 10, 15)


def test_entries_need_category_date_employer_result_and_hours_before_signing():
    assert Entry(activity="Applied for job").problems(TEXAS, TODAY) == [
        "pick an accepted activity from the state's list",
        "date missing",
        "employer or agency name missing",
        "result missing",
        "hours missing: enter the time you actually spent",
    ]
    ok = Entry(date="2026-10-08", activity="Applied for job", category=TX_IN_PERSON, employer="Acme",
               result="Application filed", hours="1.5")  # fmt: skip
    assert ok.problems(TEXAS, TODAY) == []
    bad = Entry(date="2026-10-08", employer="x", activity="a", category=TX_IN_PERSON, result="Maybe", hours="1")
    assert "result must be one of" in bad.problems(TEXAS, TODAY)[0]


def test_future_and_malformed_dates_are_flagged_not_accepted():
    base = {"activity": "a", "category": TX_IN_PERSON, "employer": "x", "result": "No reply", "hours": "1"}
    assert Entry(date="2026-10-16", **base).problems(TEXAS, TODAY) == ["date is in the future"]
    assert Entry(date="10/08/2026", **base).problems(TEXAS, TODAY) == ["date must be YYYY-MM-DD"]


def test_hours_must_be_a_positive_number():
    base = {"date": "2026-10-01", "activity": "a", "category": TX_IN_PERSON, "employer": "x", "result": "No reply"}
    for bad in ("", "0", "-1", "nan", "inf", "abc"):
        assert "hours missing" in Entry(hours=bad, **base).problems(TEXAS, TODAY)[0]


def test_claim_weeks_run_sunday_to_saturday_and_hours_are_only_what_the_user_typed():
    assert claim_week("2026-10-14") == "2026-10-11 to 2026-10-17"  # a Wednesday
    assert claim_week("2026-10-11") == "2026-10-11 to 2026-10-17"  # a Sunday starts the week
    assert claim_week("2026-10-17") == "2026-10-11 to 2026-10-17"  # a Saturday ends it
    assert claim_week("") == ""
    es = [Entry(date="2026-10-12", activity="a", hours="1.5"), Entry(date="2026-10-13", activity="b"),
          Entry(activity="c", hours="2")]  # fmt: skip
    lines = weekly_summary(es, required=5)
    assert (
        lines[0] == "2026-10-11 to 2026-10-17: 2 activities, 1.5 hours entered, 1 without hours (required 5: NOT met)"
    )
    assert lines[1].startswith("date unknown: 1 activities, 2 hours entered")


def test_save_and_load_round_trip_and_neutralise_formulas(tmp_path):
    p = tmp_path / "log.csv"
    save_entries(p, [Entry(date="2026-10-01", activity="a", employer='=HYPERLINK("x")', notes=["one", "two"])])
    got = load_entries(p)[0]
    assert got.employer.startswith("'=") and got.notes == ["one", "two"]
    assert load_entries(tmp_path / "missing.csv") == []
