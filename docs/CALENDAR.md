# Google Calendar connector

Optional and off by default. Nothing is sent or read until you sign in **and** run a command or press a button.

## What it does

| Command | Effect |
|---|---|
| `twc-tracker calendar login` | Opens Google sign-in in your browser; the result comes back to a one-shot server on `127.0.0.1`. |
| `twc-tracker calendar push` | Creates or updates **one private, all-day, "free" event per dated log entry**. Safe to re-run: each entry has a stable id, so it updates instead of duplicating. |
| `twc-tracker calendar pull --days 14` | Lists recent events and suggests which look like interviews or networking. `--add 1,3` adds the ones you choose, with employer and result left blank. |
| `twc-tracker calendar status` / `logout` | Check sign-in / revoke access at Google and delete the saved token. |

The same push and pull buttons are on the **Calendar** tab of the web app (sign-in itself stays in the terminal).

## What leaves your computer

Only an event title (`Work search: <activity> - <employer>`), the date, hours and result. **Never** proof, phone, email, address, contact names or notes. Events are marked private and do not block your availability. Events the tool wrote are tagged and are never read back as new activity.

Think before pushing to a **shared or work calendar**: the titles reveal that you are job hunting.

## Set up your own Google OAuth client (one time, free)

There is deliberately no shared client: nobody else's account or quota is involved and no developer server ever sees your data.

1. In [Google Cloud Console](https://console.cloud.google.com/), create a project and **enable the Google Calendar API**.
2. *APIs & Services → OAuth consent screen*: choose **External**, add yourself as a **test user**. (Testing mode refresh tokens expire after 7 days; run `login` again when asked.)
3. *Credentials → Create credentials → OAuth client ID → Desktop app*. Download the JSON.
4. Save it as `~/.twc-tracker/google_client.json`, or set `TWC_GOOGLE_CLIENT_ID` and `TWC_GOOGLE_CLIENT_SECRET`.
5. `twc-tracker calendar login`.

The requested scope is `calendar.events` (events only; no calendar list, no settings). The token is stored in `~/.twc-tracker/google_token.json`, readable only by you.

## Limits

- Entries you delete from the log are **not** removed from Google Calendar (edit or delete those events there).
- Google only, primary calendar only. Other calendars can be added as providers (below). Until then, `.ics` import/export works with any calendar.
- Tested against a simulated Google API, not live in CI. Report problems you find against the real thing.

## Adding a provider (for engineers)

A provider implements `calendars.CalendarProvider`: `list_events(since, until) -> list[Appointment]` and `push(entries) -> PushResult`. Keep these rules:

1. Use `calendars.event_for` so every provider sends the same minimal data.
2. Tag what you write and skip tagged events on read.
3. Be idempotent: derive the remote id from `Entry.id`.
4. Take an injectable transport and test against a fake (see `tests/test_calendar_google.py`). No live network in tests.
5. Register it in `calendars.get_provider` and document the scope and what leaves the machine.
