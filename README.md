# TWC Tracker

A free, local-first **work-search log** for people collecting unemployment benefits. It starts with Texas (Texas Workforce Commission, Work Search Activity Log **BN900E**) and is built so other states can be added from their own official forms.

> **Not affiliated with the Texas Workforce Commission or any government agency. Not legal advice.**
> A signed work-search log is a statement to the government. This tool helps you keep accurate records; **you** decide what is true, review every entry and sign it. The agency decides what counts. Always check your own determination letter and your state's current rules.

## What it does

- Records each work-search activity: date, activity, which accepted category it counts as, employer, contact, result, **hours you actually spent**, and where you keep proof.
- Shows **totals per claim week** (Sunday to Saturday) and whether you met the number of searches your notice requires.
- Marks every entry **Ready / Needs N** and says exactly what is missing, so you can fix it before you sign.
- Keeps a simple **application tracker** and turns it into log entries for you to review.
- Reads an **.ics calendar file** to suggest interviews and networking events, and writes your log back out as an .ics.
- Optionally syncs with **Google Calendar**: push your log as private all-day events, or pull events to review ([docs/CALENDAR.md](docs/CALENDAR.md)).
- Exports the log as **CSV** and **Word (.docx)** in the agency's column layout, with the agency's own reminders attached.

## What it will not do

- Invent an application, date, hour or contact. Anything unknown prints as `FILL IN` and the entry is "not ready to sign".
- Store or print a Social Security number.
- Promise that any activity counts, or tell you how many searches you need.
- Send anything anywhere unless you opt in to the calendar connector. There is no account, no cloud, no telemetry. The web app listens on `127.0.0.1` only, with a per-run token.

## Install

Requires Python 3.10+.

```bash
pip install "git+https://github.com/L7SS/TWC-Tracker.git#egg=twc-tracker[docx]"
# or from a clone:
git clone https://github.com/L7SS/TWC-Tracker.git && cd TWC-Tracker && pip install -e ".[docx]"
```

The `docx` extra enables Word export; CSV works without it.

## Use

```bash
twc-tracker ui                 # open the local web app
```

Or from the terminal:

```bash
twc-tracker activities         # the activities Texas accepts (copy one into --category)
twc-tracker add --activity "Applied for job" \
  --category "Applying for a job online, on any site, to an employer who may reasonably have openings" \
  --employer "Acme Corp" --job-type "Analyst" --result "Application filed" --hours 1.5 --proof "confirmation email"
twc-tracker applied "Acme Corp" "Analyst"     # quick add to the application tracker
twc-tracker import                            # tracker rows -> log entries (hours stay blank for you)
twc-tracker check                             # what still blocks each entry from being ready to sign
twc-tracker week --required 5                 # totals per claim week
twc-tracker calendar login                    # optional: Google Calendar (see docs/CALENDAR.md)
twc-tracker calendar push                     # one private all-day event per dated entry
twc-tracker calendar pull --days 14 --add 1   # review recent events, add the ones you choose
twc-tracker export --name "Your Name"         # draft CSV + Word, for you to review and sign
```

Your data lives in `~/.twc-tracker/` (override with `TWC_TRACKER_HOME`), readable only by you. See [`examples/`](examples/) for sample files with made-up data.

## Privacy

Everything stays on your computer. Never commit your own `worksearch_log.csv`, `applications.csv`, exports or calendar files to a public repository: the `.gitignore` here already excludes them.

## Other states

Rules differ by state: what counts, how many contacts a week, which form. A state is a small config in [`src/twc_tracker/states.py`](src/twc_tracker/states.py), built from that state's own official form. See [docs/ADDING_A_STATE.md](docs/ADDING_A_STATE.md) — contributions welcome.

## Develop

```bash
pip install -e ".[dev]"
pytest && ruff check . && ruff format --check .
```

Architecture: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md). See [CONTRIBUTING.md](CONTRIBUTING.md). MIT licensed.
