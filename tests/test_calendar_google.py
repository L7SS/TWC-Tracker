import json
import threading
import urllib.parse
import urllib.request
from datetime import date

import pytest

from twc_tracker import web
from twc_tracker.calendars import event_for, sendable, suggestion_to_entry
from twc_tracker.calendars.google import (
    API,
    TOKEN_URL,
    CalendarError,
    GoogleCalendar,
    load_client,
    login,
    logout,
)
from twc_tracker.ics import Appointment
from twc_tracker.log import Entry, ensure_ids, load_entries, save_entries
from twc_tracker.states import TX_IN_PERSON

CLIENT = ("cid", "csecret")


class FakeGoogle:
    """Just enough of the OAuth and Calendar endpoints to check our side of the conversation."""

    def __init__(self):
        self.events: dict[str, dict] = {}
        self.calls: list[tuple[str, str, dict | None]] = []
        self.token_form: dict | None = None
        self.fail_refresh = False
        self.pages: list[dict] | None = None

    def __call__(self, method, url, headers, body):
        form = (
            dict(urllib.parse.parse_qsl(body.decode()))
            if body and "x-www-form" in headers.get("Content-Type", "")
            else None
        )
        data = json.loads(body) if body and form is None else None
        self.calls.append((method, url, data))
        if url == TOKEN_URL:
            self.token_form = form
            if form["grant_type"] == "refresh_token":
                return (
                    (400, {"error": "invalid_grant"})
                    if self.fail_refresh
                    else (200, {"access_token": "A2", "expires_in": 3600})
                )
            return 200, {"access_token": "A1", "refresh_token": "R1", "expires_in": 3600}
        if url.startswith("https://oauth2.googleapis.com/revoke"):
            return 200, {}
        assert headers["Authorization"].startswith("Bearer ")
        if method == "POST" and url == API:
            if data["id"] in self.events:
                return 409, {"error": "exists"}
            self.events[data["id"]] = data
            return 200, data
        if method == "PATCH":
            self.events[url.rsplit("/", 1)[1]].update(data)
            return 200, {}
        if method == "GET":
            if self.pages is not None:
                return 200, self.pages.pop(0)
            return 200, {"items": list(self.events.values())}
        raise AssertionError((method, url))


def signed_in(tmp_path, fake, now=1000.0):
    (tmp_path / "t.json").write_text(
        json.dumps({"refresh_token": "R1", "access_token": "A1", "expires_at": now + 3600})
    )
    return GoogleCalendar(tmp_path / "t.json", CLIENT, fake, now=lambda: now)


def dated(i, **kw):
    return Entry(date="2026-10-1" + str(i), activity="Applied for job", employer=f"Acme{i}", id=f"id{i}", **kw)


def test_login_checks_state_uses_pkce_and_stores_a_private_token(tmp_path):
    fake = FakeGoogle()
    seen = {}

    def browser(url):
        q = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(url).query))
        seen.update(q)
        redirect = q["redirect_uri"] + "?" + urllib.parse.urlencode({"code": "CODE", "state": q["state"]})
        threading.Thread(target=lambda: urllib.request.urlopen(redirect).read()).start()  # noqa: S310

    login(tmp_path / "tok.json", CLIENT, browser=browser, transport=fake, timeout=10, now=lambda: 50.0)
    assert seen["code_challenge_method"] == "S256" and seen["scope"].endswith("calendar.events")
    assert seen["redirect_uri"].startswith("http://127.0.0.1:")
    assert fake.token_form["code_verifier"] and fake.token_form["code"] == "CODE"
    tok = json.loads((tmp_path / "tok.json").read_text())
    assert tok["refresh_token"] == "R1" and tok["expires_at"] == 3650.0
    assert (tmp_path / "tok.json").stat().st_mode & 0o077 == 0  # owner only


def test_login_rejects_a_forged_state(tmp_path):
    def browser(url):
        redirect = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(url).query))["redirect_uri"]
        threading.Thread(target=lambda: urllib.request.urlopen(redirect + "?code=X&state=evil").read()).start()  # noqa: S310

    with pytest.raises(CalendarError, match="state mismatch"):
        login(tmp_path / "tok.json", CLIENT, browser=browser, transport=FakeGoogle(), timeout=10)
    assert not (tmp_path / "tok.json").exists()


def test_login_times_out_when_nobody_signs_in(tmp_path):
    with pytest.raises(CalendarError, match="timed out"):
        login(tmp_path / "tok.json", CLIENT, browser=lambda u: None, transport=FakeGoogle(), timeout=0.2)


def test_push_creates_then_updates_and_never_duplicates(tmp_path):
    fake = FakeGoogle()
    g = signed_in(tmp_path, fake)
    first = g.push([dated(1, hours="1.5", result="No reply"), dated(2)])
    assert (first.created, first.updated, first.errors) == (2, 0, [])
    again = g.push([dated(1, hours="2", result="No reply"), dated(2)])
    assert (again.created, again.updated) == (0, 2) and len(fake.events) == 2
    assert "Hours: 2." in fake.events["twcid1"]["description"]


def test_push_sends_only_title_hours_and_result_as_a_private_non_blocking_event(tmp_path):
    fake = FakeGoogle()
    e = dated(1, hours="1", result="No reply", proof="SECRET-PROOF", phone="555-0100", email="a@b.c", notes=["n"])
    signed_in(tmp_path, fake).push([e])
    sent = json.dumps(fake.events["twcid1"])
    for private in ("SECRET-PROOF", "555-0100", "a@b.c"):
        assert private not in sent
    ev = fake.events["twcid1"]
    assert ev["visibility"] == "private" and ev["transparency"] == "transparent"
    assert ev["end"]["date"] == "2026-10-12" and ev["extendedProperties"]["private"]["twcTracker"] == "1"


def test_entries_without_a_valid_date_or_id_are_skipped_not_sent(tmp_path):
    fake = FakeGoogle()
    res = signed_in(tmp_path, fake).push(
        [Entry(activity="x", id="a"), Entry(date="bad", id="b"), Entry(date="2026-10-01")]
    )
    assert res.skipped == 3 and not fake.events
    assert sendable([dated(1)]) == [dated(1)] and event_for(dated(1))["id"] == "twcid1"


def test_push_reports_failures_instead_of_hiding_them(tmp_path):
    def failing(method, url, headers, body):
        return 403, {"error": "forbidden"}

    res = signed_in(tmp_path, failing).push([dated(1)])
    assert res.created == 0 and "403" in res.errors[0]


def test_expired_token_is_refreshed_and_keeps_the_refresh_token(tmp_path):
    fake = FakeGoogle()
    g = signed_in(tmp_path, fake)
    g.now = lambda: 99999.0
    g.push([dated(1)])
    assert fake.token_form["grant_type"] == "refresh_token"
    assert json.loads((tmp_path / "t.json").read_text())["refresh_token"] == "R1"


def test_revoked_sign_in_asks_you_to_log_in_again(tmp_path):
    fake = FakeGoogle()
    fake.fail_refresh = True
    g = signed_in(tmp_path, fake)
    g.now = lambda: 99999.0
    with pytest.raises(CalendarError, match="login"):
        g.push([dated(1)])
    with pytest.raises(CalendarError, match="not signed in"):
        GoogleCalendar(tmp_path / "none.json", CLIENT, fake).list_events(date(2026, 10, 1), date(2026, 10, 2))


def test_pull_skips_our_own_events_cancelled_ones_and_follows_pages(tmp_path):
    fake = FakeGoogle()
    fake.pages = [
        {
            "items": [
                {
                    "summary": "Phone screen, Acme",
                    "start": {"dateTime": "2026-10-14T10:00:00-05:00"},
                    "end": {"dateTime": "2026-10-14T10:30:00-05:00"},
                },
                {
                    "summary": "Work search: x",
                    "start": {"date": "2026-10-14"},
                    "extendedProperties": {"private": {"twcTracker": "1"}},
                },
            ],
            "nextPageToken": "P2",
        },
        {
            "items": [
                {"summary": "Dentist", "start": {"date": "2026-10-15"}},
                {"summary": "Gone", "status": "cancelled", "start": {"date": "2026-10-15"}},
                {"summary": "Weekly job club", "start": {"date": "2026-10-16"}, "recurringEventId": "r"},
            ]
        },
    ]
    got = signed_in(tmp_path, fake).list_events(date(2026, 10, 1), date(2026, 10, 20))
    assert [a.title for a in got] == ["Phone screen, Acme", "Dentist", "Weekly job club"]
    assert got[0].suggested == "interview" and got[0].hours == "0.5"
    assert got[1].suggested == "" and got[2].suggested == "networking" and got[2].recurring
    assert "pageToken=P2" in fake.calls[1][1]


def test_logout_revokes_and_deletes(tmp_path):
    fake = FakeGoogle()
    signed_in(tmp_path, fake)
    assert logout(tmp_path / "t.json", fake) is True and not (tmp_path / "t.json").exists()
    assert logout(tmp_path / "t.json", fake) is False


def test_client_comes_from_env_or_the_downloaded_json(tmp_path, monkeypatch):
    monkeypatch.delenv("TWC_GOOGLE_CLIENT_ID", raising=False)
    with pytest.raises(CalendarError, match="OAuth client"):
        load_client(tmp_path)
    (tmp_path / "google_client.json").write_text(json.dumps({"installed": {"client_id": "i", "client_secret": "s"}}))
    assert load_client(tmp_path) == ("i", "s")
    monkeypatch.setenv("TWC_GOOGLE_CLIENT_ID", "e")
    monkeypatch.setenv("TWC_GOOGLE_CLIENT_SECRET", "es")
    assert load_client(tmp_path) == ("e", "es")


def test_entry_ids_are_stable_once_saved(tmp_path):
    p = tmp_path / "log.csv"
    es = [Entry(date="2026-10-01", activity="a"), Entry(date="2026-10-02", activity="b")]
    save_entries(p, es)
    first = [e.id for e in load_entries(p)]
    assert all(first) and len(set(first)) == 2
    save_entries(p, load_entries(p))
    assert [e.id for e in load_entries(p)] == first
    assert ensure_ids(load_entries(p)) is False


def test_calendar_suggestion_becomes_an_entry_with_blanks_left_for_you():
    a = Appointment(title="Phone screen", start="2026-10-14T10:00", end="2026-10-14T10:30", suggested="interview")
    e = suggestion_to_entry(a, "interview")
    assert e.category == TX_IN_PERSON and e.employer == "" and e.result == "" and e.hours == "0.5"
    assert e.problems(__import__("twc_tracker.states", fromlist=["TEXAS"]).TEXAS, date(2026, 10, 15)) == [
        "employer or agency name missing",
        "result missing",
    ]


def test_web_calendar_routes_push_and_pull(tmp_path):
    fake = FakeGoogle()
    g = signed_in(tmp_path, fake)
    log = tmp_path / "log.csv"
    save_entries(log, [Entry(date="2026-10-12", activity="Applied for job", employer="Acme")])
    assert web._calendar_route("status", {}, log, g) == {"connected": True}
    assert web._calendar_route("push", {}, log, g)["created"] == 1
    assert web._calendar_route("pull", {"days": 5}, log, g)["events"] == []  # our own event is filtered out
    with pytest.raises(KeyError):
        web._calendar_route("nope", {}, log, g)


def test_push_requires_sign_in_even_with_nothing_to_send(tmp_path):
    with pytest.raises(CalendarError, match="not signed in"):
        GoogleCalendar(tmp_path / "none.json", CLIENT, FakeGoogle()).push([])
