# The TWC online form view

Texas claimants enter their log on the Texas Workforce Commission's online **Add Work Search Activity** page, one activity at a time. The **TWC form** tab (and `twc-tracker form`) mirrors that page so you can keep your records here and copy each entry across.

**This tool never logs in to TWC or submits for you.** You enter, review and submit on the agency's page, and your log is not complete until it shows a confirmation page. If that page differs from what is mirrored here, follow the page.

## Fields, in the page's order (`*` = required there)

| Page field | Stored as |
|---|---|
| Activity Date * (a day in the claim week) | `date` |
| Employer/Agency/Service/Event Name * | `employer` |
| Type of Work Sought * (occupation for an employer; service for a Workforce Center; topic for a job club or workshop) | `job_type` |
| Contact Method(s): In Person, Mail, Phone, Fax, Email, Internet | `contact_method` (comma list) |
| Person Contacted, Phone (+ Ext), Fax, Email, Web Site | `person_contacted`, `phone`, `ext`, `fax`, `email`, `website` |
| Address, City, State, ZIP | `address`, `address2`, `city`, `state`, `zip` |
| Filed an application or resume with this contact? * | `filed_application` (yes/no) |
| Hired as a result? * | `hired` (yes/no) |
| If yes, start date * | `start_date` |

The page's phone number is "strongly preferred" and is split into three boxes; the tab has a copy button for each part.

## What it checks

Blocking (the page would not accept the entry): missing date, employer/agency name, type of work sought, either yes/no answer, or a start date when you were hired. Warnings: missing or malformed phone, unknown contact method. Nothing is guessed: the yes/no answers and start date stay blank until you give them. (Importing a tracker row marked applied records "filed application: yes", because that is what the row says; "hired" is always yours to answer.)

## Week header

Shows the claim week (Sunday to Saturday), your minimum (set it in Settings from your own notice), how many activities are ready, and an **estimated** due date. The estimate (18 days after the week ends) comes from a single observed example of the page, so treat the agency's own date as the real one.

## Hours

The online page has no hours field. Hours stay in this tool as your own record (and in the Word/CSV drafts); they are not needed for the page and are not part of "ready for the form".
