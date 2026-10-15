"""Your data lives on your own computer, in one private folder."""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path


def data_dir() -> Path:
    override = os.environ.get("TWC_TRACKER_HOME")
    base = Path(override) if override else Path.home() / ".twc-tracker"
    base.mkdir(parents=True, exist_ok=True)
    if sys.platform != "win32":
        base.chmod(0o700)  # owner only
    return base


def write_private(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")
    if sys.platform != "win32":
        path.chmod(0o600)


def safe_filename(*parts: str, ext: str = "") -> str:
    """A filename built from untrusted text: letters, digits, dash and underscore only."""
    name = "_".join(re.sub(r"[^A-Za-z0-9]+", "-", p).strip("-") for p in parts if p)
    return (name[:120] or "file") + ext
