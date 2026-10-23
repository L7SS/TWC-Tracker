import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from twc_tracker import cli
from twc_tracker.posting import PostingError, fetch_posting, linkedin_job_id, lookup, parse_page, parse_title

LD = {"@context": "https://schema.org", "@type": "JobPosting", "title": "Data Analyst",
      "hiringOrganization": {"@type": "Organization", "name": "Acme &amp; Sons"},
      "jobLocation": {"address": {"addressLocality": "Austin", "addressRegion": "TX"}}}  # fmt: skip
PAGE = f'<html><head><title>x</title><script type="application/ld+json">{json.dumps(LD)}</script></head></html>'


@pytest.mark.parametrize(
    ("text", "employer", "role"),
    [
        ("Acme hiring Data Analyst in Austin, TX | LinkedIn", "Acme", "Data Analyst"),
        ("Job Application for Data Analyst at Acme", "Acme", "Data Analyst"),
        ("Data Analyst at Acme | Greenhouse", "Acme", "Data Analyst"),
        ("Data Analyst at Acme - Indeed.com", "Acme", "Data Analyst"),
    ],
)
def test_titles_are_split_into_employer_and_role(text, employer, role):
    p = parse_title(text)
    assert (p.employer, p.job_type) == (employer, role) and p.check == []


def test_ambiguous_titles_are_flagged_not_guessed_silently():
    p = parse_title("Data Analyst | Acme")
    assert p.check and "which part" in p.check[0]
    assert parse_title("").check == ["employer not found: type it in", "job title not found: type it in"]
    assert parse_title("Acme hiring Data Analyst in Austin, TX").location == "Austin, TX"


def test_structured_job_data_is_preferred_over_the_title():
    p = parse_page(PAGE, "https://x.example/job/1")
    assert (p.employer, p.job_type, p.location, p.source) == (
        "Acme & Sons",
        "Data Analyst",
        "Austin, TX",
        "structured-data",
    )
    graph = '<script type="application/ld+json">{"@graph":[{"@type":"WebSite"},{"@type":["JobPosting"],"title":"T","hiringOrganization":"Org"}]}</script>'
    assert (parse_page(graph).employer, parse_page(graph).job_type) == ("Org", "T")
    t = parse_page("<title>Cook at Diner | Lever</title>")
    assert (t.employer, t.job_type, t.source) == ("Diner", "Cook", "page-title") and "check both" in t.check[0]


class _H(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/job":
            body = PAGE.encode()
        elif self.path == "/blocked":
            self.send_response(403)
            self.end_headers()
            return
        elif self.path == "/redir":
            self.send_response(302)
            self.send_header("Location", "https://www.linkedin.com/jobs/view/1")
            self.end_headers()
            return
        else:
            body = b"<html><title>Sign in</title></html>"
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        return


@pytest.fixture
def site():
    srv = HTTPServer(("127.0.0.1", 0), _H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()
    srv.server_close()


def test_fetch_reads_a_public_page_and_refuses_blocks_without_working_around_them(site):
    p = fetch_posting(site + "/job", allow_private=True)
    assert (p.employer, p.job_type, p.url) == ("Acme & Sons", "Data Analyst", site + "/job")
    with pytest.raises(PostingError, match="refused.*403.*does not try to get around"):
        fetch_posting(site + "/blocked", allow_private=True)
    with pytest.raises(PostingError, match="no job details|Sign in|log in"):
        fetch_posting(site + "/login", allow_private=True)
    with pytest.raises(PostingError, match="will not read"):
        fetch_posting(site + "/redir", allow_private=True)


def test_local_and_private_addresses_are_never_read(site):
    for url in (site + "/job", "http://localhost/x", "http://192.168.1.1/", "file:///etc/passwd", "ftp://x/y", "nope"):
        with pytest.raises(PostingError):
            fetch_posting(url)


def test_linkedin_is_never_fetched_and_only_the_job_number_is_kept():
    p = lookup("https://www.linkedin.com/jobs/view/4481676800/")
    assert p.source == "link-only" and p.employer == "" and any("4481676800" in c for c in p.check)
    assert any("does not allow automated access" in c for c in p.check)
    with pytest.raises(PostingError, match="LinkedIn does not allow"):
        fetch_posting("https://uk.linkedin.com/jobs/view/123456789")
    assert linkedin_job_id("https://www.linkedin.com/jobs/view/senior-analyst-at-acme-4481676800?x=1") == "4481676800"
    assert lookup("Acme hiring Data Analyst in Austin, TX | LinkedIn").employer == "Acme"  # pasted title works
    with pytest.raises(PostingError):
        lookup("   ")


def test_cli_log_from_a_pasted_title_and_from_a_link(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("TWC_TRACKER_HOME", str(tmp_path))
    assert (
        cli.main(
            [
                "log",
                "apply",
                "--from",
                "Acme hiring Data Analyst in Austin, TX | LinkedIn",
                "--hours",
                "1",
                "--date",
                "2026-10-23",
            ]
        )
        == 0
    )
    out = capsys.readouterr().out
    assert "Read: Acme / Data Analyst (Austin, TX)" in out and "Logged for 2026-10-23, 1 h." in out
    assert cli.main(["log", "apply", "--from", "https://www.linkedin.com/jobs/view/4481676800/"]) == 2
    err = capsys.readouterr()
    assert "both needed" in err.err
    assert cli.main(["log", "apply"]) == 2
