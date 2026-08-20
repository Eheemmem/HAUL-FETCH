"""Shared HTTP session configuration.

Used by the Downloader for the actual byte-fetching, and by
extractors that need a lightweight request outside of yt-dlp (e.g.
reading a public profile page for a profile picture). Kept on
``requests`` rather than adding an async HTTP client — HAUL's
concurrency comes from running whole per-URL pipelines in a thread
pool (spec §25, "keep the dependency tree small").
"""

from __future__ import annotations

import requests

DEFAULT_TIMEOUT = 20
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36 HAUL/0.1"
)


def build_session() -> requests.Session:
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})
    return session
