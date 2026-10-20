import json
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

from twc_tracker import web


@pytest.fixture
def server(tmp_path, monkeypatch):
    monkeypatch.setenv("TWC_TRACKER_HOME", str(tmp_path))
    web.Handler.token = "tok"
    srv = ThreadingHTTPServer(("127.0.0.1", 0), web.Handler)
    web.Handler.port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{web.Handler.port}", tmp_path
    srv.shutdown()
    srv.server_close()


def call(base, path, body=None, token="tok", host=None):
    headers = {"X-Token": token}
    if body is not None:
        headers["Content-Type"] = "application/json"
    if host:
        headers["Host"] = host
    req = urllib.request.Request(base + path, json.dumps(body).encode() if body is not None else None, headers)
    try:
        with urllib.request.urlopen(req) as r:  # noqa: S310
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def test_requires_token_and_local_host(server):
    base, _ = server
    assert call(base, "/api/state", token="wrong")[0] == 403
    assert call(base, "/api/state", host="evil.example")[0] == 403
    assert call(base, "/api/state")[0] == 200


def test_log_flow_add_save_and_export(server):
    base, home = server
    assert call(base, "/api/applications", {"company": "Acme", "role": "Analyst", "date": "2026-10-08"})[0] == 200
    assert call(base, "/api/import", {})[1] == {"added": 1}
    assert call(base, "/api/import", {})[1] == {"added": 0}  # no duplicates
    state = call(base, "/api/state")[1]
    assert state["entries"][0]["employer"] == "Acme" and state["entries"][0]["hours"] == ""
    assert state["entries"][0]["problems"]  # hours/proof not typed: not ready to sign
    r = call(base, "/api/export", {})[1]
    assert "TX_work_search_log_DRAFT.csv" in r["files"] and (home / "exports" / "TX_work_search_log_DRAFT.csv").exists()
    assert call(base, "/api/settings", {"state": "ZZ"})[0] == 400
    assert call(base, "/api/nope", {})[0] == 400


def test_extra_hosts_and_codespaces_are_opt_in_and_flagged(server, monkeypatch):
    base, _ = server
    assert call(base, "/api/state", host="demo-8765.app.github.dev")[0] == 403  # not allowed by default
    web.Handler.extra_hosts = frozenset({"demo-8765.app.github.dev"})
    try:
        assert call(base, "/api/state", host="demo-8765.app.github.dev")[0] == 200
        assert call(base, "/api/state", host="other.app.github.dev")[0] == 403
    finally:
        web.Handler.extra_hosts = frozenset()
    monkeypatch.delenv("CODESPACE_NAME", raising=False)
    assert call(base, "/api/state")[1]["cloud"] is False
    monkeypatch.setenv("CODESPACE_NAME", "demo")
    monkeypatch.setenv("GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN", "app.github.dev")
    assert call(base, "/api/state")[1]["cloud"] is True
    assert web.codespace_hosts(8765) == {"demo-8765.app.github.dev"}


def test_state_carries_copy_ready_text_for_each_activity_and_week(server):
    base, _ = server
    call(base, "/api/applications", {"company": "Acme", "role": "Analyst", "date": "2026-10-06"})
    call(base, "/api/import", {})
    st = call(base, "/api/state")[1]
    assert "Employer/Agency/Service/Event Name: Acme" in st["entries"][0]["portal_text"]
    week = next(w for w in st["form_weeks"] if w["start"] == "2026-10-04")
    assert "Claim week: 2026-10-04 to 2026-10-10" in week["text"] and "Acme" in week["text"]
