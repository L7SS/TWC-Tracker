from twc_tracker import applications
from twc_tracker.states import TEXAS


def test_import_skips_prepared_and_never_invents_a_date_or_hours(tmp_path):
    p = tmp_path / "a.csv"
    p.write_text(
        "date,company,role,channel,outcome,notes\n"
        "2026-10-13,Q,Lead,online,prepared,\n"
        ",T,Analyst,online,rejected,fill in\n"
        "2026-10-08,O,Lead,referral,applied,\n"
        "2026-10-09,R,Lead,online,recruiter_screen,\n"
    )
    entries = applications.to_entries(applications.read(p))
    assert [e.employer for e in entries] == ["T", "O", "R"]
    assert entries[0].date == "" and entries[0].result == "Not hired"
    assert all(e.hours == "" for e in entries)
    assert entries[2].activity == "Interviewed" and entries[2].result == "Interviewed"
    assert "hours missing: enter the time you actually spent" in entries[1].problems(TEXAS)


def test_add_neutralises_formulas_and_rejects_bad_input(tmp_path):
    p = tmp_path / "a.csv"
    applications.add(p, company="=cmd", role="Dev", when="2026-10-01")
    assert applications.read(p)[0]["company"] == "'=cmd"
    for kwargs in ({"outcome": "bogus"}, {"when": "not-a-date"}):
        try:
            applications.add(p, company="x", role="y", **kwargs)
        except ValueError:
            continue
        raise AssertionError("expected ValueError")
