# Copy-paste workflow for the TWC portal

You enter every activity on TWC's own **Add Work Search Activity** page. This tool keeps your records and gives you text to read from or paste. It never logs in to or submits to TWC.

## Easiest way: log as you go (30 seconds each)

1. **Quick log** (top of the first tab): pick what you did, type the employer or site name and the type of work, and add your hours. The date is today unless you change it. The kind you pick fills in what it always means (for example "Applied online" records the Internet contact method and that you filed an application).
2. **Hours:** type them, or press **Start timer** when you begin and **Stop timer** when you finish. It fills in the hours your own timer measured; edit if needed. Nothing is ever estimated for you.
3. From a terminal the same thing is one line: `twc-tracker log apply "Acme Corp" "Analyst" --hours 1.5` (kinds: `apply`, `interview`, `networking`, `research`).

Hours are for your own record: the portal page in the screenshots has no hours field, so the copied text lists them separately, labeled as such, with a total per day and per week.

## Per claim week

1. Keep the log here as you go (web app, `twc-tracker add`, tracker import, or a calendar pull).
2. Open the **TWC form** tab, pick the claim week, and check **"N of M ready"**. Fix anything marked "Not ready".
3. Click **Copy the whole week as text** (or run `twc-tracker form --week 2026-10-06 --out week.txt`) and keep it open next to TWC's page.
4. For each activity, enter the fields in order. On the TWC form tab every field has its own **Copy** button; the phone number has **Area / Prefix / Line** buttons for the portal's three boxes.
4b. If none of the activities were a hire, **Answer "hired?" as No for unanswered ones** fills that one answer for the whole week after you confirm. Do not use it if one of them led to a job.
5. Click **Add Another Activity** on TWC's page for the next one, then **Review Log** and submit. You are done only when TWC shows its **confirmation page**.

## What the text looks like

```
Claim week: 2026-10-04 to 2026-10-10 (Sunday, October 04, 2026 to Saturday, October 10, 2026)
Minimum work searches: 5
Due (estimated from Texas Workforce Commission's page; check the real date there): Wednesday, October 28, 2026

--- 1 of 5 ---
Activity: Acme Corp  [READY]
  Activity Date (choose this day): Tuesday, October 06, 2026
  Employer/Agency/Service/Event Name: Acme Corp
  Type of Work Sought: Analyst
  Contact Method(s) (tick): Internet
  Phone Number (three boxes): 512 | 555 | 0100
  Did you file an application or resume with this contact? (choose): Yes
  Were you hired as a result of this activity? (choose): No
```

Anything required and still blank prints as `!! REQUIRED, still blank`. Nothing is filled in for you. `--json` gives the same data for scripts.

## Why no auto-fill or bookmarklet

A script that types into a government portal while you are signed in can submit something you did not review, and a signed log is a statement to the government. Copy-paste keeps you reading every value before it goes in. Only the form's own page decides what is accepted, so if it changes, follow the page.
