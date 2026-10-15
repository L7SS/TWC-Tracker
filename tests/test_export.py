import pytest

from twc_tracker.export import write_csv, write_docx
from twc_tracker.log import Entry
from twc_tracker.states import TEXAS


def test_csv_leaves_unknowns_blank_for_the_user(tmp_path):
    write_csv(
        tmp_path / "w.csv", [Entry(activity="Applied for job", employer="Acme", result="Application filed")], TEXAS
    )
    text = (tmp_path / "w.csv").read_text()
    assert "FILL IN" in text and "date missing" in text and "no: " in text


def test_docx_carries_the_agency_reminders(tmp_path):
    docx = pytest.importorskip("docx")
    write_docx(tmp_path / "w.docx", [Entry(activity="a")], TEXAS, "A B")
    text = " ".join(p.text for p in docx.Document(str(tmp_path / "w.docx")).paragraphs)
    assert "True and complete" in text and "self-employment profits" in text and "never stores it" in text
