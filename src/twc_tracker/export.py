"""Write the log in the agency's column layout. Unknowns print as FILL IN and the entry is marked not ready to sign."""

from __future__ import annotations

import csv
from pathlib import Path

from twc_tracker.log import ENTRY_COLS, Entry, weekly_summary
from twc_tracker.states import StateConfig


def _cell(v: str) -> str:
    v = v or "FILL IN"
    return "'" + v if v[0] in "=+-@" else v


def write_csv(path: Path, entries: list[Entry], cfg: StateConfig) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow([*ENTRY_COLS, "ready_to_sign"])
        for e in entries:
            d = e.as_dict()
            probs = e.problems(cfg)
            w.writerow([_cell(d[c]) for c in ENTRY_COLS] + ["yes" if not probs else "no: " + "; ".join(probs)])


def write_docx(path: Path, entries: list[Entry], cfg: StateConfig, name: str, required: int | None = None) -> None:
    """A landscape table with the same columns as the agency form. Name, SSN and week are left for you to write."""
    try:
        from docx import Document
        from docx.enum.section import WD_ORIENT
        from docx.shared import Inches, Pt
    except ImportError as e:
        raise RuntimeError("Word export needs python-docx: pip install 'twc-tracker[docx]'") from e

    d = Document()
    s = d.sections[0]
    s.orientation = WD_ORIENT.LANDSCAPE
    s.page_width, s.page_height = s.page_height, s.page_width
    s.left_margin = s.right_margin = s.top_margin = s.bottom_margin = Inches(0.5)
    d.styles["Normal"].font.name = "Arial"
    d.styles["Normal"].font.size = Pt(9)
    d.add_heading(f"{cfg.agency} - {cfg.form} (draft)", 2)
    d.add_paragraph(f"Name: {name}     Week of: ____________ to ____________     Number of required searches: ______")
    d.add_paragraph("Social Security number: write it by hand on the form you keep. This tool never stores it.")
    t = d.add_table(rows=1, cols=4)
    t.style = "Table Grid"
    heads = ["Date / Work search activity / Type of job", "Name, location and telephone of employer or agency",
             "Contact information", "Results"]  # fmt: skip
    for i, h in enumerate(heads):
        t.rows[0].cells[i].text = h
    for e in entries:
        c = t.add_row().cells
        c[0].text = (
            f"Date: {e.date or 'FILL IN'}\nActivity: {e.activity or 'FILL IN'}\nCounts as: {e.category or 'FILL IN'}\n"
            f"Type of job: {e.job_type or 'FILL IN'}\nHours: {e.hours or 'FILL IN'}"
        )
        c[1].text = f"Name: {e.employer or 'FILL IN'}\nAddress: {e.address or 'FILL IN'}\nPhone: {e.phone or 'FILL IN'}"
        c[2].text = (
            f"Person contacted: {e.person_contacted or 'FILL IN'}\nMethod: {e.contact_method or 'FILL IN'}\n"
            f"E-mail: {e.email or 'FILL IN'}"
        )
        c[3].text = "\n".join(f"[{'x' if e.result == r else ' '}] {r}" for r in cfg.result_choices)
    d.add_paragraph("Totals by claim week (Sunday to Saturday):")
    for line in weekly_summary(entries, required):
        d.add_paragraph(line, style="List Bullet")
    d.add_paragraph(cfg.keep_note)
    d.add_paragraph("Accepted examples on the form: " + "; ".join(cfg.example_activities) + ".")
    d.add_paragraph(f"Source of the accepted-activity list: {cfg.source} The agency decides what counts.")
    if cfg.reminders:
        d.add_paragraph("Reminders from the agency's own definitions:")
        for line in cfg.reminders:
            d.add_paragraph(line, style="List Bullet")
    d.save(str(path))
