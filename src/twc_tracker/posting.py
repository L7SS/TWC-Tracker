"""Fill in employer and job title from a job posting you point at, so you don't retype them.

Two ways in, both started by you for one posting at a time:
  * a link: the page is read from your computer, using the posting's own machine-readable data (schema.org JobPosting,
    which employers publish for search engines) or, failing that, its page title;
  * pasted text: the browser tab title, or anything shaped like "Role at Company" / "Company hiring Role".

LinkedIn is never fetched: its terms do not allow automated access, so a LinkedIn link only yields the job number, and
you paste the tab title instead. No login, no crawling, no retries, no attempt to get around a block.
Everything found is a suggestion for you to check. Nothing is saved until you log the activity.
"""

from __future__ import annotations

import html
import ipaddress
import json
import re
import socket
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field

MAX_BYTES = 1_500_000
TIMEOUT = 15
USER_AGENT = "TWC-Tracker/0.1 (personal work-search log; one page requested by its user)"
NO_FETCH_HOSTS = ("linkedin.com",)  # terms of service forbid automated access
_SITE_SUFFIX = re.compile(
    r"\s*[|\-–—·]\s*(LinkedIn|Indeed(\.com)?|Glassdoor|ZipRecruiter|Monster|Greenhouse|Lever)\s*$", re.I
)


@dataclass
class Posting:
    employer: str = ""
    job_type: str = ""  # the job title: what TWC calls "type of work sought" for an employer contact
    location: str = ""
    url: str = ""
    source: str = ""  # how it was found: structured-data | page-title | pasted-title | link-only
    check: list[str] = field(default_factory=list)  # things to look at before you log it

    def as_dict(self) -> dict:
        return {**self.__dict__}


class PostingError(RuntimeError):
    pass


def _clean(v: object) -> str:
    return re.sub(r"\s+", " ", html.unescape(str(v or ""))).strip()


def parse_title(text: str) -> Posting:
    """Employer and title from a page title or pasted line. Ambiguous shapes are flagged, never silently guessed."""
    t = _clean(text)
    t = _SITE_SUFFIX.sub("", t)
    p = Posting(source="pasted-title")
    if m := re.match(r"^(?P<co>.+?) hiring (?P<role>.+?)(?: in (?P<loc>[^|]+?))?$", t, re.I):  # LinkedIn tab titles
        p.employer, p.job_type, p.location = _clean(m["co"]), _clean(m["role"]), _clean(m["loc"])
    elif m := re.match(r"^Job Application for (?P<role>.+) at (?P<co>.+)$", t, re.I):
        p.employer, p.job_type = _clean(m["co"]), _clean(m["role"])
    elif m := re.match(r"^(?P<role>.+?) at (?P<co>[^|]+?)(?: [|\-–—] .*)?$", t, re.I):
        p.employer, p.job_type = _clean(m["co"]), _clean(m["role"])
    elif parts := [x.strip() for x in re.split(r"\s[|\-–—]\s", t) if x.strip()]:
        p.job_type = parts[0]
        if len(parts) > 1:
            p.employer = parts[1]
            p.check.append("could not tell which part is the employer and which is the job title: check both")
    if not p.employer:
        p.check.append("employer not found: type it in")
    if not p.job_type:
        p.check.append("job title not found: type it in")
    return p


def _find_jobposting(node: object) -> dict | None:
    if isinstance(node, list):
        for n in node:
            if r := _find_jobposting(n):
                return r
    elif isinstance(node, dict):
        kind = node.get("@type")
        if kind == "JobPosting" or (isinstance(kind, list) and "JobPosting" in kind):
            return node
        for v in node.values():
            if isinstance(v, (dict, list)) and (r := _find_jobposting(v)):
                return r
    return None


def parse_page(page: str, url: str = "") -> Posting:
    """From a page's HTML: structured JobPosting data if present, otherwise its title."""
    for m in re.finditer(r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', page, re.S | re.I):
        try:
            data = json.loads(m.group(1))
        except ValueError:
            continue
        if job := _find_jobposting(data):
            org = job.get("hiringOrganization")
            org = org.get("name") if isinstance(org, dict) else org
            loc = job.get("jobLocation")
            loc = loc[0] if isinstance(loc, list) and loc else loc
            addr = loc.get("address", {}) if isinstance(loc, dict) else {}
            where = ", ".join(x for x in (_clean(addr.get("addressLocality")), _clean(addr.get("addressRegion"))) if x)
            p = Posting(employer=_clean(org), job_type=_clean(job.get("title")), location=where, url=url,
                        source="structured-data")  # fmt: skip
            if not p.employer:
                p.check.append("employer not found: type it in")
            if not p.job_type:
                p.check.append("job title not found: type it in")
            return p
    title = ""
    if m := re.search(r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\'](.*?)["\']', page, re.I | re.S):
        title = m.group(1)
    elif m := re.search(r"<title[^>]*>(.*?)</title>", page, re.I | re.S):
        title = m.group(1)
    p = parse_title(title)
    p.url, p.source = url, "page-title"
    p.check.insert(0, "read from the page title, not the posting's own data: check both")
    return p


def _public_host(host: str, allow_private: bool) -> None:
    """Refuse hosts that resolve to your own machine or network: this only ever reads public job pages."""
    if allow_private:
        return
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as e:
        raise PostingError(f"could not find {host}") from e
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            raise PostingError("that address is not a public website")


class _Redirects(urllib.request.HTTPRedirectHandler):
    def __init__(self, allow_private: bool) -> None:
        self.allow_private = allow_private

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        u = urllib.parse.urlparse(newurl)
        if u.scheme not in {"http", "https"} or not u.hostname or _blocked_host(u.hostname):
            raise PostingError("redirected somewhere this tool will not read")
        _public_host(u.hostname, self.allow_private)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _blocked_host(host: str) -> bool:
    h = host.lower().rstrip(".")
    return any(h == b or h.endswith("." + b) for b in NO_FETCH_HOSTS)


def linkedin_job_id(url: str) -> str:
    m = re.search(r"/jobs/view/(?:[^/?#]*?-)?(\d{6,})", url) or re.search(r"currentJobId=(\d{6,})", url)
    return m.group(1) if m else ""


def fetch_posting(url: str, allow_private: bool = False) -> Posting:
    """Read one public job page that you pointed at. Raises PostingError with a plain reason if it cannot."""
    u = urllib.parse.urlparse(url.strip())
    if u.scheme not in {"http", "https"} or not u.hostname:
        raise PostingError("that does not look like a web link")
    if _blocked_host(u.hostname):
        raise PostingError(
            "LinkedIn does not allow automated access, so this tool does not read it. Copy the tab's title "
            "(the line in your browser tab, like 'Acme hiring Data Analyst in Austin, TX | LinkedIn') and paste that."
        )
    _public_host(u.hostname, allow_private)
    opener = urllib.request.build_opener(_Redirects(allow_private))
    req = urllib.request.Request(url.strip(), headers={"User-Agent": USER_AGENT, "Accept": "text/html"})  # noqa: S310
    try:
        with opener.open(req, timeout=TIMEOUT) as r:
            if "html" not in (r.headers.get("Content-Type") or "").lower():
                raise PostingError("that link is not a web page")
            raw = r.read(MAX_BYTES + 1)
            charset = r.headers.get_content_charset() or "utf-8"
    except urllib.error.HTTPError as e:
        raise PostingError(
            f"the site refused to show the page ({e.code}). This tool does not try to get around that: "
            "paste the page's title instead."
        ) from e
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise PostingError(f"could not read the page: {getattr(e, 'reason', e)}") from e
    if len(raw) > MAX_BYTES:
        raise PostingError("that page is too large")
    p = parse_page(raw.decode(charset, "replace"), url.strip())
    if p.source == "page-title" and not (p.employer and p.job_type):
        # a login or error page has a title too ("Sign in"): only trust a title that gives both employer and role
        raise PostingError("no job details found on that page (it may need you to log in): paste the page's title")
    if not p.employer and not p.job_type:
        raise PostingError("no job details found on that page (it may need you to log in): paste the page's title")
    return p


def lookup(text: str, allow_private: bool = False) -> Posting:
    """A link or pasted text in, a suggestion out."""
    t = text.strip()
    if re.match(r"^https?://", t, re.I):
        host = urllib.parse.urlparse(t).hostname or ""
        if _blocked_host(host):
            job = linkedin_job_id(t)
            p = Posting(url=t, source="link-only")
            p.check.append(
                "LinkedIn does not allow automated access, so it was not read. Copy the browser tab's title and paste "
                "that to fill in the employer and job title"
            )
            if job:
                p.check.append(f"LinkedIn job number {job} saved as your proof link")
            return p
        return fetch_posting(t, allow_private)
    if not t:
        raise PostingError("paste a job link or the page title")
    return parse_title(t)
