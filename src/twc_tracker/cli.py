"""Command line: open the app, add an activity, see this week's totals, or write the log in the agency's format."""

from __future__ import annotations

import argparse
import sys
from datetime import date

from twc_tracker import __version__, applications
from twc_tracker.export import write_csv, write_docx
from twc_tracker.log import Entry, claim_week, load_entries, save_entries, weekly_summary
from twc_tracker.paths import data_dir
from twc_tracker.states import STATES, TEXAS


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="twc-tracker", description=__doc__)
    p.add_argument("--version", action="version", version=__version__)
    p.add_argument("--state", default="TX", choices=sorted(STATES))
    sub = p.add_subparsers(dest="cmd", required=True)

    ui = sub.add_parser("ui", help="open the local web app")
    ui.add_argument("--port", type=int, default=8765)
    ui.add_argument("--no-browser", action="store_true")

    add = sub.add_parser("add", help="record one work-search activity (you type every fact)")
    add.add_argument("--date", default=date.today().isoformat(), help="YYYY-MM-DD (default: today)")
    add.add_argument("--activity", required=True, help="e.g. 'Applied for job'")
    add.add_argument("--category", required=True, help="one of the state's accepted activities (see 'activities')")
    add.add_argument("--employer", default="")
    add.add_argument("--job-type", default="")
    add.add_argument("--result", default="")
    add.add_argument("--hours", default="", help="time you actually spent, e.g. 1.5")
    add.add_argument("--contact-method", default="")
    add.add_argument("--person", default="")
    add.add_argument("--phone", default="")
    add.add_argument("--email", default="")
    add.add_argument("--address", default="")
    add.add_argument("--proof", default="", help="where you keep proof: email, screenshot, notes")

    sub.add_parser("activities", help="list the activities the state's agency accepts")
    sub.add_parser("check", help="list entries that are not ready to sign, and why")

    wk = sub.add_parser("week", help="totals per claim week (Sunday to Saturday)")
    wk.add_argument("--required", type=int, help="activities required per week, from your own agency notice")

    track = sub.add_parser("applied", help="add a row to your application tracker")
    track.add_argument("company")
    track.add_argument("role")
    track.add_argument("--date", default="")
    track.add_argument("--channel", default="online")
    track.add_argument("--outcome", default="applied", choices=applications.OUTCOMES)
    track.add_argument("--notes", default="")

    sub.add_parser("import", help="turn tracker rows into log entries (dates and hours stay blank if unknown)")

    cal = sub.add_parser("calendar", help="sign in to Google Calendar, push your log, or pull events to review")
    cs = cal.add_subparsers(dest="cal_cmd", required=True)
    cs.add_parser("login", help="sign in with Google (opens your browser; needs your own OAuth client)")
    cs.add_parser("status", help="are you signed in?")
    cs.add_parser("logout", help="revoke access and delete the saved sign-in")
    cs.add_parser("push", help="create or update one private all-day event per dated log entry")
    pull = cs.add_parser("pull", help="list recent calendar events that could be work-search activity")
    pull.add_argument("--days", type=int, default=14, help="how many days back to look")
    pull.add_argument("--add", default="", help="comma-separated numbers from the list to add to your log")

    ex = sub.add_parser("export", help="write the log as CSV (and Word if python-docx is installed)")
    ex.add_argument("--name", default="")
    ex.add_argument("--required", type=int)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    cfg = STATES.get(args.state, TEXAS)
    log = data_dir() / "worksearch_log.csv"
    if args.cmd == "ui":
        from twc_tracker.web import serve

        serve(args.port, not args.no_browser)
    elif args.cmd == "add":
        e = Entry(
            date=args.date, activity=args.activity, category=args.category, employer=args.employer,
            job_type=args.job_type, result=args.result, hours=args.hours, contact_method=args.contact_method,
            person_contacted=args.person, phone=args.phone, email=args.email, address=args.address, proof=args.proof,
        )  # fmt: skip
        save_entries(log, [*load_entries(log), e])
        probs = e.problems(cfg)
        print("Saved. " + ("Ready to sign." if not probs else "Not ready to sign yet: " + "; ".join(probs)))
    elif args.cmd == "activities":
        print("\n".join(cfg.accepted_activities))
        print(f"\nSource: {cfg.source}")
    elif args.cmd == "check":
        bad = [(i, e) for i, e in enumerate(load_entries(log), 1) if e.problems(cfg)]
        for i, e in bad:
            print(f"#{i} {e.date or '(no date)'} {e.employer or e.activity}: " + "; ".join(e.problems(cfg)))
        print(f"{len(bad)} entries need attention." if bad else "Every entry is ready to sign.")
        return 1 if bad else 0
    elif args.cmd == "week":
        lines = weekly_summary(load_entries(log), args.required)
        print("\n".join(lines) if lines else "No entries yet.")
        this = claim_week(date.today().isoformat())
        print(f"\nThis claim week: {this}")
    elif args.cmd == "applied":
        applications.add(
            data_dir() / "applications.csv", company=args.company, role=args.role, channel=args.channel,
            outcome=args.outcome, notes=args.notes, when=args.date,
        )  # fmt: skip
        print("Added to your application tracker.")
    elif args.cmd == "import":
        have = {(e.employer.lower(), e.job_type.lower(), e.date) for e in load_entries(log)}
        new = [
            e for e in applications.to_entries(applications.read(data_dir() / "applications.csv"))
            if (e.employer.lower(), e.job_type.lower(), e.date) not in have
        ]  # fmt: skip
        save_entries(log, [*load_entries(log), *new])
        print(f"Added {len(new)} entries. Fill in hours, proof and any other blanks before you sign.")
    elif args.cmd == "calendar":
        return _calendar(args, log)
    elif args.cmd == "export":
        out = data_dir() / "exports"
        out.mkdir(exist_ok=True)
        entries = load_entries(log)
        stem = f"{cfg.code}_work_search_log_DRAFT"
        write_csv(out / f"{stem}.csv", entries, cfg)
        print(f"Wrote {out / (stem + '.csv')}")
        try:
            write_docx(out / f"{stem}.docx", entries, cfg, args.name or "____", args.required)
            print(f"Wrote {out / (stem + '.docx')}")
        except RuntimeError as err:
            print(f"Skipped Word file: {err}", file=sys.stderr)
        print("This is a draft. You review it and sign it yourself.")
    return 0


def _calendar(args, log) -> int:
    from datetime import timedelta

    from twc_tracker.calendars import suggestion_to_entry
    from twc_tracker.calendars.google import CalendarError, GoogleCalendar, login, logout
    from twc_tracker.log import ensure_ids

    g = GoogleCalendar()
    try:
        if args.cal_cmd == "login":
            login(g.token_path)
            print("Signed in. Nothing has been sent yet: run `twc-tracker calendar push` when you are ready.")
        elif args.cal_cmd == "status":
            print("Signed in to Google Calendar." if g.connected() else "Not signed in.")
        elif args.cal_cmd == "logout":
            print("Signed out and revoked." if logout(g.token_path) else "Not signed in.")
        elif args.cal_cmd == "push":
            entries = load_entries(log)
            if ensure_ids(entries):
                save_entries(log, entries)
            r = g.push(entries)
            print(f"Created {r.created}, updated {r.updated}, skipped {r.skipped} without a valid date.")
            for err in r.errors:
                print("  failed:", err, file=sys.stderr)
            return 1 if r.errors else 0
        elif args.cal_cmd == "pull":
            today = date.today()
            events = g.list_events(today - timedelta(days=args.days), today)
            for i, a in enumerate(events, 1):
                print(f"{i:>3}. {a.start.replace('T', ' ')}  {a.title}  [{a.suggested or 'no suggestion'}]")
            picked = [int(n) for n in args.add.split(",") if n.strip()]
            if bad := [n for n in picked if not 1 <= n <= len(events)]:
                print(f"No such event number(s): {bad}", file=sys.stderr)
                return 2
            new = [suggestion_to_entry(events[n - 1], events[n - 1].suggested or "networking") for n in picked]
            if new:
                save_entries(log, [*load_entries(log), *new])
                print(f"Added {len(new)}. Fill in the employer and result, then run `check`.")
            elif not args.add:
                print("Nothing added. Re-run with --add 1,3 to add events you choose.")
    except CalendarError as e:
        print(f"Calendar: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
