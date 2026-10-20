"""A small local web app for your work-search log.

Everything stays on your computer. The server listens on 127.0.0.1 only, rejects foreign Host headers (DNS
rebinding), and requires a random per-run token on every request, so other pages open in your browser cannot talk to it.
"""

from __future__ import annotations

import json
import secrets
import webbrowser
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from twc_tracker import applications
from twc_tracker.export import write_csv, write_docx
from twc_tracker.ics import parse_ics, to_ics
from twc_tracker.log import Entry, claim_week, load_entries, save_entries, week_bounds, weekly_summary
from twc_tracker.paths import data_dir, safe_filename, write_private
from twc_tracker.states import STATES
from twc_tracker.twcform import CONTACT_METHODS, form_problems, methods, week_view

MAX_BODY = 1_000_000
_PAGE = Path(__file__).with_name("ui") / "index.html"


def _settings() -> dict:
    p = data_dir() / "settings.json"
    base = {"name": "", "required": 5, "state": "TX"}
    if p.exists():
        base.update(json.loads(p.read_text(encoding="utf-8")))
    return base


def _cfg(settings: dict):
    return STATES.get(settings.get("state", "TX"), STATES["TX"])


def _state() -> dict:
    s = _settings()
    cfg = _cfg(s)
    entries = load_entries(data_dir() / "worksearch_log.csv")
    return {
        "settings": s,
        "states": sorted(STATES),
        "applications": applications.read(data_dir() / "applications.csv"),
        "outcomes": list(applications.OUTCOMES),
        "entries": [
            {
                **e.as_dict(),
                "problems": e.problems(cfg),
                "week": claim_week(e.date),
                "contact_checked": methods(e.contact_method),
                "form_errors": form_problems(e)[0],
                "form_warnings": form_problems(e)[1],
            }
            for e in entries
        ],
        "form_weeks": [week_view(entries, d, s["required"], cfg) for d in _form_weeks(entries)],
        "contact_methods": list(CONTACT_METHODS),
        "online_form_examples": list(cfg.online_form_examples),
        "weekly": weekly_summary(entries, s["required"]),
        "activities": list(cfg.accepted_activities),
        "results": list(cfg.result_choices),
        "reminders": list(cfg.reminders),
        "agency": cfg.agency,
        "form": cfg.form,
        "source": cfg.source,
    }


def _form_weeks(entries: list[Entry]) -> list[date]:
    """The claim weeks to show: every week with an entry, plus this one, newest first."""
    starts = {week_bounds(date.today())[0]}
    for e in entries:
        try:
            starts.add(week_bounds(date.fromisoformat(e.date))[0])
        except ValueError:
            continue
    return sorted(starts, reverse=True)


def _entries_from(items: list[dict]) -> list[Entry]:
    return [Entry.from_dict(i) for i in items]


class Handler(BaseHTTPRequestHandler):
    token = ""
    port = 0

    def log_message(self, *args) -> None:  # keep your job search out of the terminal log
        return

    def _ok_host(self) -> bool:
        return (self.headers.get("Host") or "") in {f"127.0.0.1:{self.port}", f"localhost:{self.port}"}

    def _send(self, code: int, body: bytes, ctype: str = "application/json", extra: dict | None = None) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'self'",
        )
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj, code: int = 200) -> None:
        self._send(code, json.dumps(obj).encode())

    def _authorised(self, query: dict) -> bool:
        given = self.headers.get("X-Token") or (query.get("t") or [""])[0]
        return self._ok_host() and secrets.compare_digest(given, self.token)

    def do_GET(self) -> None:
        u = urlparse(self.path)
        q = parse_qs(u.query)
        if not self._ok_host():
            return self._json({"error": "bad host"}, 403)
        if u.path == "/":
            page = _PAGE.read_text(encoding="utf-8").replace("__TOKEN__", self.token)
            return self._send(200, page.encode(), "text/html; charset=utf-8")
        if not self._authorised(q):
            return self._json({"error": "unauthorised"}, 403)
        if u.path == "/api/state":
            return self._json(_state())
        if u.path == "/download":
            name = (q.get("f") or [""])[0]
            folder = data_dir() / "exports"
            match = next((f for f in folder.glob("*") if f.is_file() and f.name == name), None)
            if match is None:
                return self._json({"error": "not found"}, 404)
            disposition = f'attachment; filename="{safe_filename(match.stem)}{match.suffix}"'
            return self._send(200, match.read_bytes(), "application/octet-stream", {"Content-Disposition": disposition})
        self._json({"error": "not found"}, 404)

    def do_POST(self) -> None:
        u = urlparse(self.path)
        if not self._authorised({}):
            return self._json({"error": "unauthorised"}, 403)
        if (self.headers.get("Content-Type") or "").split(";")[0] != "application/json":
            return self._json({"error": "json only"}, 415)
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            return self._json({"error": "bad length"}, 400)
        if n > MAX_BODY:
            return self._json({"error": "too large"}, 413)
        try:
            body = json.loads(self.rfile.read(n) or b"{}")
            self._json(self._route(u.path, body))
        except KeyError as e:
            self._json({"error": f"missing or unknown: {e}"}, 400)
        except (ValueError, TypeError, RuntimeError) as e:
            self._json({"error": str(e)[:300]}, 400)

    def _calendar(self, action: str, body: dict, log: Path) -> dict:
        return _calendar_route(action, body, log)

    def _route(self, path: str, body: dict) -> dict:
        log = data_dir() / "worksearch_log.csv"
        if path == "/api/settings":
            cfg = _settings()
            cfg["name"] = str(body.get("name", cfg["name"]))[:100]
            cfg["required"] = max(0, min(50, int(body.get("required", cfg["required"]))))
            if str(body.get("state", cfg["state"])) not in STATES:
                raise ValueError("unknown state")
            cfg["state"] = str(body.get("state", cfg["state"]))
            write_private(data_dir() / "settings.json", json.dumps(cfg))
        elif path == "/api/entries":
            save_entries(log, _entries_from(body["entries"]))
        elif path == "/api/import":
            have = {(e.employer.lower(), e.job_type.lower(), e.date) for e in load_entries(log)}
            new = [
                e for e in applications.to_entries(applications.read(data_dir() / "applications.csv"))
                if (e.employer.lower(), e.job_type.lower(), e.date) not in have
            ]  # fmt: skip
            save_entries(log, [*load_entries(log), *new])
            return {"added": len(new)}
        elif path == "/api/applications":
            applications.add(
                data_dir() / "applications.csv", company=str(body["company"]), role=str(body["role"]),
                channel=str(body.get("channel") or "online"), outcome=str(body.get("outcome", "applied")),
                notes=str(body.get("notes", "")), when=str(body.get("date", "")),
            )  # fmt: skip
        elif path == "/api/ics/preview":
            return {"events": [a.as_dict() for a in parse_ics(str(body["text"]))]}
        elif path == "/api/ics/export":
            items = [
                (e.date, f"Work search: {e.activity}" + (f" - {e.employer}" if e.employer else ""),
                 f"Hours: {e.hours or 'not entered'}. Result: {e.result or 'none'}.")
                for e in load_entries(log) if claim_week(e.date)
            ]  # fmt: skip
            out = data_dir() / "exports"
            out.mkdir(exist_ok=True)
            write_private(out / "work_search_calendar.ics", to_ics(items))
            return {"files": ["work_search_calendar.ics"], "count": len(items)}
        elif path.startswith("/api/calendar/"):
            return self._calendar(path.rsplit("/", 1)[1], body, log)
        elif path == "/api/export":
            s = _settings()
            cfg = _cfg(s)
            entries = load_entries(log)
            out = data_dir() / "exports"
            out.mkdir(exist_ok=True)
            stem = f"{cfg.code}_work_search_log_DRAFT"
            write_csv(out / f"{stem}.csv", entries, cfg)
            files = [f"{stem}.csv"]
            try:
                write_docx(out / f"{stem}.docx", entries, cfg, s["name"] or "____", s["required"])
                files.append(f"{stem}.docx")
            except RuntimeError as e:
                return {"files": files, "note": str(e)}
            return {"files": files}
        else:
            raise KeyError(path)
        return {"ok": True}


def _calendar_route(action: str, body: dict, log: Path, provider=None) -> dict:
    """Google Calendar actions. Signing in happens in the terminal (`twc-tracker calendar login`), never here."""
    from datetime import date, timedelta

    from twc_tracker.calendars.google import CalendarError, GoogleCalendar
    from twc_tracker.log import ensure_ids

    g = provider or GoogleCalendar()
    if action == "status":
        return {"connected": g.connected()}
    try:
        if action == "push":
            entries = load_entries(log)
            if ensure_ids(entries):
                save_entries(log, entries)
            r = g.push(entries)
            return {"created": r.created, "updated": r.updated, "skipped": r.skipped, "errors": r.errors}
        if action == "pull":
            days = max(1, min(120, int(body.get("days", 14))))
            today = date.today()
            return {"events": [a.as_dict() for a in g.list_events(today - timedelta(days=days), today)]}
    except CalendarError as e:
        raise ValueError(str(e)) from e
    raise KeyError(action)


def serve(port: int = 8765, open_browser: bool = True) -> None:
    Handler.token = secrets.token_urlsafe(24)
    Handler.port = port
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    url = f"http://127.0.0.1:{port}/"
    print(f"TWC Tracker running at {url}  (this computer only; Ctrl+C to stop)")
    print(f"Your data is in {data_dir()}")
    if open_browser:
        webbrowser.open(url)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()
