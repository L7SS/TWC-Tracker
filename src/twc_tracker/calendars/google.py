"""Google Calendar connector: OAuth 2.0 for installed apps (loopback + PKCE), stdlib only.

You bring your own OAuth client (Google Cloud Console, "Desktop app"); nothing is bundled, so there is no shared
secret and no developer-run server. Tokens stay in your data folder, readable only by you. The scope is
`calendar.events`: events only, not your calendar list or settings.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from collections.abc import Callable
from datetime import date, datetime, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

from twc_tracker.calendars import TAG, PushResult, event_for, sendable
from twc_tracker.ics import INTERVIEW_WORDS, NETWORK_WORDS, Appointment
from twc_tracker.log import Entry
from twc_tracker.paths import data_dir, write_private

SCOPE = "https://www.googleapis.com/auth/calendar.events"
AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"  # noqa: S105
REVOKE_URL = "https://oauth2.googleapis.com/revoke"
API = "https://www.googleapis.com/calendar/v3/calendars/primary/events"
_FORM = {"Content-Type": "application/x-www-form-urlencoded"}

# transport(method, url, headers, body) -> (http status, parsed JSON or {}). Replaceable in tests.
Transport = Callable[[str, str, dict[str, str], "bytes | None"], tuple[int, dict[str, Any]]]


class CalendarError(RuntimeError):
    pass


def urllib_transport(method: str, url: str, headers: dict[str, str], body: bytes | None) -> tuple[int, dict]:
    if not url.startswith("https://"):
        raise CalendarError("refusing a non-https URL")
    req = urllib.request.Request(url, body, headers, method=method)  # noqa: S310
    try:
        with urllib.request.urlopen(req, timeout=30) as r:  # noqa: S310
            raw = r.read()
            return r.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            return e.code, json.loads(raw) if raw else {}
        except ValueError:
            return e.code, {"error": raw[:200].decode("utf-8", "replace")}
    except (urllib.error.URLError, TimeoutError) as e:
        raise CalendarError(f"could not reach Google: {e}") from e


def load_client(home: Path | None = None) -> tuple[str, str]:
    """Your OAuth client id and secret: env vars, or the JSON file Google lets you download."""
    cid, secret = os.environ.get("TWC_GOOGLE_CLIENT_ID"), os.environ.get("TWC_GOOGLE_CLIENT_SECRET")
    if cid and secret:
        return cid, secret
    where = (home or data_dir()) / "google_client.json"
    if where.exists():
        d = json.loads(where.read_text(encoding="utf-8"))
        d = d.get("installed") or d.get("web") or d
        if d.get("client_id") and d.get("client_secret"):
            return d["client_id"], d["client_secret"]
    raise CalendarError(
        "No Google OAuth client. Create a 'Desktop app' client (docs/CALENDAR.md), then either set "
        f"TWC_GOOGLE_CLIENT_ID and TWC_GOOGLE_CLIENT_SECRET or save the downloaded JSON as {where}"
    )


def _form(d: dict[str, str]) -> bytes:
    return urllib.parse.urlencode(d).encode()


def _pkce() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    return verifier, challenge


def build_auth_url(client_id: str, redirect: str, state: str, challenge: str) -> str:
    return AUTH_URL + "?" + urllib.parse.urlencode({
        "client_id": client_id, "redirect_uri": redirect, "response_type": "code", "scope": SCOPE,
        "state": state, "code_challenge": challenge, "code_challenge_method": "S256",
        "access_type": "offline", "prompt": "consent",
    })  # fmt: skip


def login(
    token_path: Path,
    client: tuple[str, str] | None = None,
    *,
    browser: Callable[[str], object] = webbrowser.open,
    transport: Transport = urllib_transport,
    timeout: float = 300,
    now: Callable[[], float] = time.time,
) -> None:
    """Open Google's sign-in in your browser and wait for it to come back to this computer."""
    cid, secret = client or load_client()
    verifier, challenge = _pkce()
    state = secrets.token_urlsafe(24)
    got: dict[str, str] = {}

    class Catch(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            q = {k: v[0] for k, v in urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query).items()}
            ok = "code" in q or "error" in q
            if ok:
                got.update(q)
            self.send_response(200 if ok else 404)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"Signed in. You can close this tab and return to the terminal." if ok else b"")

        def log_message(self, *args) -> None:
            return

    srv = HTTPServer(("127.0.0.1", 0), Catch)
    srv.timeout = 1
    redirect = f"http://127.0.0.1:{srv.server_address[1]}"
    try:
        browser(build_auth_url(cid, redirect, state, challenge))
        deadline = time.monotonic() + timeout
        while not got and time.monotonic() < deadline:
            srv.handle_request()
    finally:
        srv.server_close()
    if not got:
        raise CalendarError("sign-in timed out")
    if got.get("state") != state:
        raise CalendarError("sign-in was rejected: state mismatch")
    if "code" not in got:
        raise CalendarError(f"Google refused: {got.get('error')}")
    status, tok = transport("POST", TOKEN_URL, _FORM, _form({
        "code": got["code"], "client_id": cid, "client_secret": secret, "code_verifier": verifier,
        "redirect_uri": redirect, "grant_type": "authorization_code",
    }))  # fmt: skip
    if status != 200 or "refresh_token" not in tok:
        raise CalendarError(f"token exchange failed ({status}): {tok.get('error_description') or tok.get('error')}")
    _save(token_path, tok, now())


def _save(path: Path, tok: dict, now: float, keep_refresh: str = "") -> None:
    write_private(path, json.dumps({
        "refresh_token": tok.get("refresh_token") or keep_refresh,
        "access_token": tok["access_token"],
        "expires_at": now + int(tok.get("expires_in", 3600)),
    }))  # fmt: skip


def logout(token_path: Path, transport: Transport = urllib_transport) -> bool:
    """Revoke the token with Google (best effort) and delete it here."""
    if not token_path.exists():
        return False
    tok = json.loads(token_path.read_text(encoding="utf-8"))
    try:
        transport("POST", REVOKE_URL, _FORM, _form({"token": tok.get("refresh_token", "")}))
    except CalendarError:
        pass
    token_path.unlink()
    return True


def _local(value: dict) -> str:
    """'YYYY-MM-DD' or 'YYYY-MM-DDTHH:MM' in this computer's local time, from a Google start/end object."""
    if "date" in value:
        return value["date"]
    t = datetime.fromisoformat(value["dateTime"].replace("Z", "+00:00"))
    return (t.astimezone() if t.tzinfo else t).replace(tzinfo=None).strftime("%Y-%m-%dT%H:%M")


class GoogleCalendar:
    name = "google"

    def __init__(
        self,
        token_path: Path | None = None,
        client: tuple[str, str] | None = None,
        transport: Transport = urllib_transport,
        now: Callable[[], float] = time.time,
    ) -> None:
        self.token_path = token_path or data_dir() / "google_token.json"
        self._client = client
        self.transport = transport
        self.now = now

    def connected(self) -> bool:
        return self.token_path.exists()

    def _access(self) -> str:
        if not self.token_path.exists():
            raise CalendarError("not signed in: run `twc-tracker calendar login`")
        tok = json.loads(self.token_path.read_text(encoding="utf-8"))
        if tok["expires_at"] - 60 > self.now():
            return tok["access_token"]
        cid, secret = self._client or load_client()
        status, new = self.transport("POST", TOKEN_URL, _FORM, _form({
            "client_id": cid, "client_secret": secret, "refresh_token": tok["refresh_token"],
            "grant_type": "refresh_token",
        }))  # fmt: skip
        if status != 200:
            raise CalendarError("Google refused to renew sign-in: run `twc-tracker calendar login` again")
        _save(self.token_path, new, self.now(), keep_refresh=tok["refresh_token"])
        return new["access_token"]

    def _call(self, method: str, url: str, body: dict | None = None) -> tuple[int, dict]:
        headers = {"Authorization": f"Bearer {self._access()}"}
        data = None
        if body is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(body).encode()
        return self.transport(method, url, headers, data)

    def list_events(self, since: date, until: date) -> list[Appointment]:
        """Your events in a date range, as suggestions. Events this tool wrote are left out."""
        out: list[Appointment] = []
        token = ""
        while True:
            q = {"timeMin": f"{since}T00:00:00Z", "timeMax": f"{until + timedelta(days=1)}T00:00:00Z",
                 "singleEvents": "true", "orderBy": "startTime", "maxResults": "250"}  # fmt: skip
            if token:
                q["pageToken"] = token
            status, page = self._call("GET", API + "?" + urllib.parse.urlencode(q))
            if status != 200:
                raise CalendarError(f"calendar read failed ({status}): {page.get('error')}")
            for ev in page.get("items", []):
                if ev.get("status") == "cancelled" or ev.get("extendedProperties", {}).get("private", {}).get(TAG):
                    continue
                title = (ev.get("summary") or "(no title)")[:200]
                low = title.lower()
                out.append(Appointment(
                    title=title, start=_local(ev["start"]), end=_local(ev["end"]) if "end" in ev else "",
                    location=(ev.get("location") or "")[:200], description=(ev.get("description") or "")[:500],
                    recurring="recurringEventId" in ev,
                    suggested="interview" if any(w in low for w in INTERVIEW_WORDS)
                    else "networking" if any(w in low for w in NETWORK_WORDS) else "",
                ))  # fmt: skip
            token = page.get("nextPageToken", "")
            if not token:
                return out

    def push(self, entries: list[Entry]) -> PushResult:
        """Create or update one all-day, private, non-blocking event per dated entry. Re-running never duplicates."""
        self._access()  # fail early and clearly if not signed in, even when there is nothing to send
        todo = sendable(entries)
        res = PushResult(skipped=len(entries) - len(todo))
        for e in todo:
            ev = event_for(e)
            body = {
                "summary": ev["summary"], "description": ev["description"], "visibility": "private",
                "transparency": "transparent", "status": "confirmed",
                "start": {"date": ev["date"]},
                "end": {"date": str(date.fromisoformat(ev["date"]) + timedelta(days=1))},
                "extendedProperties": {"private": {TAG: "1"}},
            }  # fmt: skip
            status, resp = self._call("POST", API, {**body, "id": ev["id"]})
            if status == 409:  # already there (or was deleted): make it match the log
                status, resp = self._call("PATCH", f"{API}/{ev['id']}", body)
                if status == 200:
                    res.updated += 1
                    continue
            elif status == 200:
                res.created += 1
                continue
            res.errors.append(f"{e.date} {e.employer or e.activity}: {status} {resp.get('error')}")
        return res
